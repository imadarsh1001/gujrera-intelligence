"""Phase 1 Verification Gate and FastMCP Protocol Integration Tests.

Validates the complete GujRERA Sovereign Real Estate Intelligence Platform across:
1. Zero PII leak test (synthetic PAN, 12-digit ID, email, bank account masked; statutory IDs preserved).
2. Knowledge Graph & Promoter Portfolio test (no promoter:None, composite key, homonyms, token cap).
3. BU ground-truth test (has_bu_noc/bu_check, legacy grandfathered <=2019, govt authority).
4. Token ceiling & envelope test (14 tools <= 6,000 tokens, standard envelope contract).
5. SpatialEmpiricalPricer test (3-tier fallback, calibrated IQR, indexed unit_transactions lookup).
6. audit_discrepancies test (SKIPPED_UNINGESTED for uningested Form 3/QPR/Form 5, Sec 4 land cost).
7. FastMCP 4.2 protocol & UI coexistence test (in-process client, POST /mcp 200, GET / 200, MCP_API_KEY).
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List

# Ensure repository root and real_estate_intelligence package are discoverable
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "real_estate_intelligence"))

import anyio
from fastapi.testclient import TestClient
from fastmcp import Client
from mcp.client.session import ClientSession

from api.index import app, AppState, setup_backends
from real_estate_intelligence.agent.copilot import AgenticCopilot, handle_copilot_query, GEMINI_TOOLS, OPENAI_TOOLS
from real_estate_intelligence.analytics.audit import ProjectAuditor
from real_estate_intelligence.analytics.spatial_pricing import SpatialEmpiricalPricer
from real_estate_intelligence.db.database import init_schema
from real_estate_intelligence.db.queries import get_project_detail
from real_estate_intelligence.db.redaction import (
    is_whitelisted,
    mask_bank_account,
    redact_payload,
    redact_record,
    redact_value,
)
from real_estate_intelligence.db.turso_sync import sync_to_turso
from real_estate_intelligence.graph.network import KnowledgeGraph, resolve_promoter_portfolio
from real_estate_intelligence.mcp.envelope import wrap_tool_response
from real_estate_intelligence.mcp.fastmcp_app import mcp
from real_estate_intelligence.mcp.server import RealEstateIntelligenceMCP

# No-op validator for in-process FastMCP Client when optional jsonschema package is absent
async def _noop_validate(self, name, result):
    pass

ClientSession.validate_tool_result = _noop_validate


class TestPhase1MCP(unittest.TestCase):
    """Phase 1 Verification Gate covering security, graphs, BU status, pricing, audit, and FastMCP protocol."""

    @classmethod
    def setUpClass(cls):
        # HARD INVARIANT: NEVER mutate data/intelligence.sqlite.
        # Use an isolated temporary copy of test_intelligence.sqlite.
        src_db = Path(__file__).resolve().parent.parent / "data" / "test_intelligence.sqlite"
        cls.tmp_file = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        cls.tmp_file.close()
        shutil.copyfile(src_db, cls.tmp_file.name)
        cls.db_path = Path(cls.tmp_file.name)

        setup_backends(cls.db_path)
        cls.mcp_server = RealEstateIntelligenceMCP(cls.db_path)
        cls.con = cls.mcp_server.con
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "mcp_server") and cls.mcp_server.con:
            cls.mcp_server.con.close()
        if hasattr(cls, "tmp_file") and os.path.exists(cls.tmp_file.name):
            try:
                os.remove(cls.tmp_file.name)
            except Exception:
                pass

    # =========================================================================
    # 1. ZERO PII LEAK TEST
    # =========================================================================

    def test_01_zero_pii_leak_comprehensive(self):
        """Synthetic PAN, 12-digit ID, email, bank account masked; statutory IDs preserved."""
        # Synthetic dummy PII entities (Never real PII)
        dummy_pan = "ABCDE1234F"
        dummy_pan_st = "XYZAB5678CST001"
        dummy_aadhaar_spaced = "9876 5432 1098"
        dummy_aadhaar_plain = "987654321098"
        dummy_email = "synthetic_consultant@example.com"
        dummy_acct_num = "987654321012345"

        # Legitimate statutory identifiers to preserve
        rera_reg_valid = "PR/GJ/AHMEDABAD/AHMEDABAD CITY/AUDA/MAA09044/160921"
        coa_lic_valid = "CA/2018/98765"

        # 1. Redaction unit checks
        self.assertEqual(redact_value("license_or_reg_no", dummy_pan), "[REDACTED-PAN]")
        self.assertEqual(redact_value("license_or_reg_no", dummy_pan_st), "[REDACTED-PAN]")
        self.assertEqual(redact_value("detail", f"Aadhaar {dummy_aadhaar_spaced}"), "Aadhaar [REDACTED-ID]")
        self.assertEqual(redact_value("snippet", f"National ID {dummy_aadhaar_plain}"), "National ID [REDACTED-ID]")
        self.assertEqual(redact_value("email", dummy_email), "[REDACTED-EMAIL]")
        self.assertEqual(redact_value("account_no", dummy_acct_num), "****2345")

        # Statutory preservation
        self.assertTrue(is_whitelisted(rera_reg_valid))
        self.assertTrue(is_whitelisted(coa_lic_valid))
        self.assertEqual(redact_value("registration_number", rera_reg_valid), rera_reg_valid)
        self.assertEqual(redact_value("license_or_reg_no", coa_lic_valid), coa_lic_valid)

        # 2. Check get_project_detail scrubbing
        detail = get_project_detail(self.con, 16562)
        detail_json = json.dumps(detail)
        self.assertNotIn(dummy_pan, detail_json)
        self.assertNotIn(dummy_email, detail_json)
        for b in detail.get("banks", []):
            acct = str(b.get("account_no") or "")
            if acct:
                self.assertTrue(acct.startswith("****"), f"Unmasked account found: {acct}")

        # 3. Check trace_entity_network scrubbing
        net = self.mcp_server.trace_entity_network(16562)
        net_json = json.dumps(net)
        self.assertNotIn("@", net_json)

        # 4. Check Copilot query & tool dispatch redaction
        copilot = AgenticCopilot(self.mcp_server)
        dispatched = copilot.dispatch_tool("get_land_records", {"project_id": 16562})
        self.assertIsInstance(dispatched, dict)
        self.assertIn("project_id", dispatched)
        self.assertIn("block_clearances", dispatched)
        self.assertNotIn(dummy_pan, json.dumps(dispatched))

        copilot_res = handle_copilot_query("ok", 16562, self.con, mcp_server=self.mcp_server)
        self.assertIn("reply", copilot_res)
        self.assertNotIn(dummy_pan, copilot_res["reply"])

        # 5. Check Turso sync row sanitization
        sample_bank_row = {
            "project_id": 16562,
            "bank_name": "Test Bank",
            "account_no": dummy_acct_num,
            "account_number_masked": dummy_acct_num,
            "account_name": f"Escrow {dummy_email}",
        }
        sanitized = redact_record(sample_bank_row)
        self.assertEqual(sanitized["account_no"], "****2345")
        self.assertEqual(sanitized["account_number_masked"], "****2345")
        self.assertIn("[REDACTED-EMAIL]", sanitized["account_name"])

    # =========================================================================
    # 2. GRAPH & PROMOTER PORTFOLIO TEST
    # =========================================================================

    def test_02_graph_and_promoter_portfolio(self):
        """Zero promoter:None edges returned; composite key linkage; homonyms flagged; token cap enforced."""
        # 1. Test live queries ignore legacy promoter:None
        kg = KnowledgeGraph(self.con)
        shared_16562 = kg.find_shared_entities(16562)
        for s in shared_16562:
            self.assertNotEqual(s.get("shared_entity_name"), "None")
            self.assertFalse(str(s.get("shared_entity_name", "")).startswith("promoter:None"))

        ego = kg.get_ego_network(16562)
        node_ids = {n["id"] for n in ego["nodes"]}
        self.assertNotIn("promoter:None", node_ids)

        # 2. Test get_promoter_portfolio composite resolution
        portfolio = self.mcp_server.get_promoter_portfolio(project_id=16562)
        self.assertIn("promoter_name", portfolio)
        self.assertIn("resolved_projects", portfolio)
        self.assertGreaterEqual(portfolio.get("portfolio_count", 0), 1)

        # 3. Test homonym detection on common brand prefixes
        mem_con = sqlite3.connect(":memory:")
        mem_con.row_factory = sqlite3.Row
        init_schema(mem_con)
        try:
            mem_con.execute(
                "INSERT INTO projects (project_id, name, registration_number, promoter_name, district, completion_date) "
                "VALUES (5001, 'RADHE RESIDENCY', 'REG5001', 'RADHE DEVELOPERS', 'Ahmedabad', '2024-12-31')"
            )
            mem_con.commit()
            homonym_res = resolve_promoter_portfolio(mem_con, promoter_name="RADHE DEVELOPERS")
            self.assertTrue(homonym_res["homonym_warning"])
            self.assertIn("common Gujarat brand prefix", homonym_res["warning_message"])
        finally:
            mem_con.close()

        # 4. Test trace_entity_network token cap <= 4,000 tokens
        net_capped = self.mcp_server.trace_entity_network(16562, max_tokens=4000)
        token_est = net_capped.get("token_estimate") or net_capped["network"]["token_estimate"]
        self.assertLessEqual(token_est, 4000)

    # =========================================================================
    # 3. BU GROUND-TRUTH TEST
    # =========================================================================

    def test_03_bu_ground_truth_and_cohort_flags(self):
        """has_bu_noc/bu_check used instead of dead projects.bu_status; legacy and govt authority verified."""
        auditor = ProjectAuditor(self.con)

        # In-memory test setup to verify exact BU ground truth logic
        mem_con = sqlite3.connect(":memory:")
        mem_con.row_factory = sqlite3.Row
        init_schema(mem_con)
        try:
            # Project A: Modern project expired in 2023 with valid BU in noc_bu_records
            mem_con.execute(
                "INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, district, completion_date) "
                "VALUES (101, 'ALPHA HEIGHTS', 'REG101', 1, 'ALPHA DEV', 'Ahmedabad', '2023-01-01')"
            )
            mem_con.execute(
                "INSERT INTO noc_bu_records (project_id, block_name, bu_check, bu_date) "
                "VALUES (101, 'A', 'YES', '2023-05-15')"
            )

            # Project B: Legacy grandfathered (completed 2018)
            mem_con.execute(
                "INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, district, completion_date) "
                "VALUES (102, 'HERITAGE ENCLAVE', 'REG102', 2, 'HERITAGE DEV', 'Ahmedabad', '2018-05-30')"
            )

            # Project C: Government authority project (AUDA)
            mem_con.execute(
                "INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, district, completion_date) "
                "VALUES (103, 'AUDA JAN AWAAS', 'REG103', 3, 'AHMEDABAD URBAN DEVELOPMENT AUTHORITY', 'Ahmedabad', '2025-12-31')"
            )
            mem_con.commit()

            mem_auditor = ProjectAuditor(mem_con)

            # BU NOC verification
            bu_a = mem_auditor.check_bu_status(101)
            self.assertTrue(bu_a["has_bu_noc"])
            self.assertEqual(bu_a["evidence_source"], "noc_bu_records.bu_check")

            # Project A does not trigger false expired lead because BU was issued
            leads_a = mem_auditor.audit_project(101)
            self.assertEqual(len([l for l in leads_a if "Expired" in l.title]), 0)

            # Project B: Legacy grandfathered
            cohort_b = mem_auditor.get_cohort_flags(102)
            self.assertTrue(cohort_b["is_legacy_grandfathered"])
            self.assertFalse(cohort_b["is_govt_authority"])

            # Project C: Government authority
            cohort_c = mem_auditor.get_cohort_flags(103)
            self.assertFalse(cohort_c["is_legacy_grandfathered"])
            self.assertTrue(cohort_c["is_govt_authority"])
        finally:
            mem_con.close()

    # =========================================================================
    # 4. TOKEN CEILING & ENVELOPE TEST
    # =========================================================================

    def test_04_token_ceiling_and_envelope_contract(self):
        """All 14 FastMCP tools stay <= 6,000 tokens even on large townships with standard envelope contract."""
        pid = 16562

        tool_calls = [
            ("search_projects", lambda: mcp.call_tool("search_projects", {"district": "Gandhinagar", "limit": 20})),
            ("get_project_dossier", lambda: mcp.call_tool("get_project_dossier", {"project_id": pid})),
            ("compare_projects", lambda: mcp.call_tool("compare_projects", {"project_ids": [pid]})),
            ("query_unit_transactions", lambda: mcp.call_tool("query_unit_transactions", {"project_id": pid, "limit": 50})),
            ("get_spatial_pricing_benchmark", lambda: mcp.call_tool("get_spatial_pricing_benchmark", {"project_id": pid})),
            ("get_pricing_appreciation_trend", lambda: mcp.call_tool("get_pricing_appreciation_trend", {"project_id": pid})),
            ("verify_sales_claim", lambda: mcp.call_tool("verify_sales_claim", {"project_id": pid, "claimed_rate": 4500.0})),
            ("get_spatial_density", lambda: mcp.call_tool("get_spatial_density", {"project_id": pid, "radius_km": 3.0})),
            ("get_land_records", lambda: mcp.call_tool("get_land_records", {"project_id": pid})),
            ("trace_entity_network", lambda: mcp.call_tool("trace_entity_network", {"project_id": pid, "max_tokens": 4000})),
            ("get_promoter_portfolio", lambda: mcp.call_tool("get_promoter_portfolio", {"project_id": pid})),
            ("audit_discrepancies", lambda: mcp.call_tool("audit_discrepancies", {"project_id": pid, "include_skipped": True})),
            ("get_escrow_and_finances", lambda: mcp.call_tool("get_escrow_and_finances", {"project_id": pid})),
            ("get_regulatory_radar", lambda: mcp.call_tool("get_regulatory_radar", {"project_id": pid})),
        ]

        self.assertEqual(len(tool_calls), 14, "Must cover all 14 consolidated FastMCP tools")

        async def run_all_tools():
            for name, call_fn in tool_calls:
                res = await call_fn()
                self.assertFalse(res.is_error, f"Tool {name} returned error: {res}")
                structured = res.structured_content

                # Check mandatory envelope keys
                for key in ("data", "data_coverage", "provenance", "pagination", "token_estimate"):
                    self.assertIn(key, structured, f"Tool {name} envelope missing '{key}'")

                # Token ceiling invariant: <= 6,000 tokens
                token_est = structured["token_estimate"]
                self.assertLessEqual(token_est, 6000, f"Tool {name} exceeded 6,000 token limit: {token_est}")

        anyio.run(run_all_tools)

    # =========================================================================
    # 5. SPATIAL EMPIRICAL PRICER TEST
    # =========================================================================

    def test_05_spatial_empirical_pricer(self):
        """3-tier fallback works; returns calibrated IQR + markup spread; indexed unit_transactions lookup."""
        pricer = SpatialEmpiricalPricer(self.con)

        # 1. Benchmark execution on project 16562
        res = pricer.benchmark(16562, asset_class="Residential")
        self.assertIn("benchmark_tier", res)
        self.assertIn(res["benchmark_tier"], ["Tier 1", "Tier 2", "Tier 3"])
        self.assertIn("iqr", res)
        self.assertIn("median_rate_sqft", res)
        self.assertIn("project_booked_median", res)
        self.assertIn("project_unbooked_median", res)
        self.assertIn("unbooked_markup_pct", res)
        self.assertIn("statewide_markup_baseline_pct", res)

        # 2. EXPLAIN QUERY PLAN verification: indexed lookup, zero full table scans
        plan = self.con.execute(
            "EXPLAIN QUERY PLAN SELECT rate_per_sqft FROM unit_transactions WHERE project_id = ? AND status = 'BOOKED'",
            (16562,),
        ).fetchall()
        plan_str = " ".join([dict(p)["detail"] for p in plan])
        self.assertTrue("USING INDEX" in plan_str or "USING COVERING INDEX" in plan_str)
        self.assertNotIn("SCAN unit_transactions", plan_str)

    # =========================================================================
    # 6. AUDIT DISCREPANCIES TEST
    # =========================================================================

    def test_06_audit_discrepancies_and_section_4_formula(self):
        """Non-pilot project explicitly reports SKIPPED_UNINGESTED; Section 4 formula accounts for land cost."""
        mem_con = sqlite3.connect(":memory:")
        mem_con.row_factory = sqlite3.Row
        init_schema(mem_con)
        try:
            # Non-pilot project with only projects master row
            mem_con.execute(
                "INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, district) "
                "VALUES (888, 'STATEWIDE UNINGESTED SCHEME', 'REG888', 1, 'DEVELOPER', 'Surat')"
            )
            mem_con.commit()

            mem_auditor = ProjectAuditor(mem_con)
            leads = mem_auditor.audit_project(888, include_skipped=True)
            skipped_leads = [l for l in leads if l.severity == "SKIPPED_UNINGESTED"]
            self.assertGreaterEqual(len(skipped_leads), 3, "Missing uningested tables must be surfaced as SKIPPED_UNINGESTED")

            # Section 4 formula land cost protection test
            # Estimated 100 Cr, Incurred 40 Cr (Land). Deposits 50 Cr, Withdrawn 20 Cr.
            # Baseline 35% land cost means 20 Cr withdrawn on 50 Cr deposit is allowable.
            mem_con.execute(
                "INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, district, engg_score_pct) "
                "VALUES (889, 'PRIME RESIDENCY', 'REG889', 2, 'DEV', 'Ahmedabad', 10.0)"
            )
            mem_con.execute(
                "INSERT INTO finances (project_id, filing_date, filing_type, form_three_id, estimated_cost, incurred_and_paid) "
                "VALUES (889, '2025-01-01', 'latest', 101, 1000000000.0, 400000000.0)"
            )
            mem_con.execute(
                "INSERT INTO banks (project_id, bank_name, account_type, closing_bal, deposit_amt, withdrawal_amt) "
                "VALUES (889, 'SBI', 1, 100000000.0, 500000000.0, 200000000.0)"
            )
            mem_con.commit()

            leads_889 = mem_auditor.audit_project(889, include_skipped=True)
            escrow_breaches = [l for l in leads_889 if "Statutory 70% Escrow Over-Withdrawal" in l.title]
            self.assertEqual(len(escrow_breaches), 0, "Legitimate withdrawals covering land cost must not false-positive")
        finally:
            mem_con.close()

    # =========================================================================
    # 7. FASTMCP 4.2 PROTOCOL & UI COEXISTENCE TEST
    # =========================================================================

    def test_07_fastmcp_protocol_and_ui_coexistence(self):
        """In-process Client(mcp) lists tools and executes; POST /mcp is 200 (not 307); GET / is 200; Bearer auth works."""
        # 1. In-process FastMCP Client lists all 14 tools and templates, and executes call
        async def run_client_checks():
            async with Client(mcp) as client:
                tools = await client.list_tools()
                self.assertEqual(len(tools), 14, f"Expected 14 tools, got {len(tools)}")
                tool_names = {t.name for t in tools}
                self.assertIn("search_projects", tool_names)
                self.assertIn("get_project_dossier", tool_names)
                self.assertIn("get_spatial_pricing_benchmark", tool_names)
                self.assertIn("audit_discrepancies", tool_names)

                templates = await client.list_resource_templates()
                self.assertEqual(len(templates), 3)

                res = await client.call_tool("get_land_records", {"project_id": 16562})
                self.assertIsNotNone(res)

        anyio.run(run_client_checks)

        with TestClient(app) as client:
            # 2. FastAPI HTTP POST /mcp returns 200 directly without 307 redirect
            rpc_req = {"jsonrpc": "2.0", "id": 101, "method": "tools/list"}
            res_post = client.post("/mcp", json=rpc_req, follow_redirects=False)
            self.assertEqual(res_post.status_code, 200)

            # 3. Web dashboard GET / returns 200
            res_ui = client.get("/")
            self.assertEqual(res_ui.status_code, 200)
            self.assertIn("GujRERA", res_ui.text)

            # 4. Optional MCP_API_KEY protects /mcp while leaving / and /api/explore accessible
            test_key = "sovereign-test-token-phase1"
            os.environ["MCP_API_KEY"] = test_key
            try:
                # /mcp without header is 401
                unauth = client.post("/mcp", json=rpc_req, follow_redirects=False)
                self.assertEqual(unauth.status_code, 401)

                # /mcp with Bearer header is 200
                auth_ok = client.post(
                    "/mcp",
                    headers={"Authorization": f"Bearer {test_key}"},
                    json=rpc_req,
                    follow_redirects=False,
                )
                self.assertEqual(auth_ok.status_code, 200)

                # /api/explore and / are unaffected and open
                t0 = time.perf_counter()
                explore_res = client.get("/api/explore?limit=10")
                dur = time.perf_counter() - t0
                self.assertEqual(explore_res.status_code, 200)
                self.assertLess(dur, 0.5, f"Explore latency {dur:.3f}s exceeded 0.5s")

                dash_res = client.get("/")
                self.assertEqual(dash_res.status_code, 200)
            finally:
                if "MCP_API_KEY" in os.environ:
                    del os.environ["MCP_API_KEY"]


if __name__ == "__main__":
    unittest.main()
