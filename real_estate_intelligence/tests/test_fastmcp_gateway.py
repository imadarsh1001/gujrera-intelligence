"""Comprehensive integration tests for FastMCP 4.2 Gateway, Envelope, 14 Consolidated Tools, and API Mount."""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

# Ensure root and real_estate_intelligence are discoverable
root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "real_estate_intelligence"))

import anyio
from fastapi.testclient import TestClient

from api.index import app, AppState, setup_backends
from real_estate_intelligence.mcp.envelope import wrap_tool_response, estimate_tokens
from real_estate_intelligence.mcp.fastmcp_app import mcp, get_server
from real_estate_intelligence.mcp.server import RealEstateIntelligenceMCP


class TestFastMCPGateway(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src_db = Path(__file__).resolve().parent.parent / "data" / "test_intelligence.sqlite"
        cls.tmp_file = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        cls.tmp_file.close()
        shutil.copyfile(src_db, cls.tmp_file.name)
        cls.db_path = Path(cls.tmp_file.name)
        setup_backends(cls.db_path)
        cls.mcp_server = RealEstateIntelligenceMCP(cls.db_path)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "tmp_file") and os.path.exists(cls.tmp_file.name):
            try:
                os.remove(cls.tmp_file.name)
            except Exception:
                pass

    def test_exact_path_and_redirect_elimination(self):
        """Verify POST /mcp returns 200 directly without 307 Temporary Redirect."""
        with TestClient(app) as client:
            rpc_req = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
            # POST /mcp without trailing slash (follow_redirects=False)
            res_no_slash = client.post("/mcp", json=rpc_req, follow_redirects=False)
            self.assertEqual(res_no_slash.status_code, 200)

            # POST /mcp/ with trailing slash
            res_slash = client.post("/mcp/", json=rpc_req, follow_redirects=False)
            self.assertEqual(res_slash.status_code, 200)

    def test_mcp_bearer_auth(self):
        """Verify optional Bearer auth scoped ONLY to /mcp without blocking / or /api/*."""
        test_key = "sovereign-audit-key-test-999"
        os.environ["MCP_API_KEY"] = test_key
        try:
            with TestClient(app) as client:
                rpc_req = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}

                # 1. /mcp without header should be 401
                unauth = client.post("/mcp", json=rpc_req, follow_redirects=False)
                self.assertEqual(unauth.status_code, 401)

                # 2. /mcp with wrong header should be 401
                bad_auth = client.post(
                    "/mcp",
                    headers={"Authorization": "Bearer wrong-key"},
                    json=rpc_req,
                    follow_redirects=False,
                )
                self.assertEqual(bad_auth.status_code, 401)

                # 3. /mcp with correct header should be 200
                good_auth = client.post(
                    "/mcp",
                    headers={"Authorization": f"Bearer {test_key}"},
                    json=rpc_req,
                    follow_redirects=False,
                )
                self.assertEqual(good_auth.status_code, 200)

                # 4. Standard endpoints (/api/health, /api/explore, /) are never blocked
                health = client.get("/api/health")
                self.assertEqual(health.status_code, 200)
                root_res = client.get("/")
                self.assertEqual(root_res.status_code, 200)
        finally:
            if "MCP_API_KEY" in os.environ:
                del os.environ["MCP_API_KEY"]

    def test_envelope_contract_and_pii_redaction(self):
        """Verify MCP response envelope contract, coverage detection, and PII scrubbing."""
        dummy_pii = {
            "developer_email": "test-dev@domain.org",
            "account_no": "987654321012",
            "statutory_id": "PR/GJ/GANDHINAGAR/GANDHINAGAR/GMC/MN365AA10265/191023",
            "notes": "Architect reg no CA/2018/12345 approved deed",
        }

        # 1. Deep audit project (16562)
        env_deep = wrap_tool_response(
            dummy_pii,
            project_ids=[16562],
            tables=["finances", "banks"],
            con=self.mcp_server.con,
        )
        self.assertIn("data", env_deep)
        self.assertIn("data_coverage", env_deep)
        self.assertIn("provenance", env_deep)
        self.assertIn("pagination", env_deep)
        self.assertIn("token_estimate", env_deep)

        self.assertEqual(env_deep["data_coverage"]["coverage_tier"], "pilot_deep_audit")
        self.assertEqual(env_deep["data"]["developer_email"], "[REDACTED-EMAIL]")
        self.assertEqual(env_deep["data"]["account_no"], "****1012")
        self.assertIn("PR/GJ/", env_deep["data"]["statutory_id"])
        self.assertIn("CA/2018/12345", env_deep["data"]["notes"])

        # 2. Statewide project (non-pilot)
        env_statewide = wrap_tool_response(
            {"sample": "data"},
            project_ids=[999999],
            tables=["finances"],
            con=self.mcp_server.con,
        )
        self.assertEqual(env_statewide["data_coverage"]["coverage_tier"], "statewide_core")
        self.assertTrue(len(env_statewide["data_coverage"]["caveats"]) > 0)

    def test_envelope_token_truncation(self):
        """Verify clean auto-truncation for oversized list and graph payloads."""
        # 1. Standard list payload
        big_list = [{"idx": i, "desc": "Sovereign deed transaction valuation record"} for i in range(1000)]
        res_list = wrap_tool_response(
            big_list,
            project_ids=[16562],
            tables=["unit_transactions"],
            con=self.mcp_server.con,
            max_tokens=300,
        )
        self.assertTrue(res_list["pagination"]["truncated"])
        self.assertLessEqual(res_list["token_estimate"], 300)

        # 2. Graph payload (capped at 4,000 tokens)
        graph_data = {
            "nodes": [{"id": f"node:{i}", "label": f"Entity {i}"} for i in range(500)],
            "edges": [{"src_id": "node:0", "dst_id": f"node:{i}", "relation": "DEVELOPED_BY"} for i in range(1, 500)],
        }
        res_graph = wrap_tool_response(
            graph_data,
            project_ids=[16562],
            tables=["graph_nodes", "graph_edges"],
            con=self.mcp_server.con,
            max_tokens=400,
        )
        self.assertTrue(res_graph["pagination"]["truncated"])
        self.assertLessEqual(res_graph["token_estimate"], 400)

    def test_all_14_consolidated_tools(self):
        """Verify all 14 consolidated MCP server methods execute cleanly."""
        srv = self.mcp_server
        pid = 16562

        # 1. search_projects
        s_res = srv.search_projects(district="Gandhinagar", limit=5)
        self.assertIn("projects", s_res)
        self.assertIn("total", s_res)

        # 2. get_project_dossier
        dossier = srv.get_project_dossier(pid)
        self.assertIsInstance(dossier, str)
        self.assertTrue("Due-Diligence Dossier" in dossier or "4-Quadrant" in dossier)

        # 3. compare_projects
        comp = srv.compare_projects([pid])
        self.assertEqual(len(comp), 1)
        self.assertIn("bu_status", comp[0])

        # 4. query_unit_transactions
        txs = srv.query_unit_transactions(pid, limit=10)
        self.assertIn("transactions", txs)
        self.assertIn("total", txs)

        # 5. get_spatial_pricing_benchmark
        bm = srv.get_spatial_pricing_benchmark(pid, asset_class="Residential")
        self.assertIn("benchmark_tier", bm)

        # 6. get_pricing_appreciation_trend
        trend = srv.get_pricing_appreciation_trend(pid)
        self.assertIn("cagr_pct", trend)

        # 7. verify_sales_claim
        claim = srv.verify_sales_claim(pid, claimed_rate=5000.0)
        self.assertIn("verification_checks", claim)

        # 8. get_spatial_density
        density = srv.get_spatial_density(pid, radius_km=3.0, limit=10)
        self.assertIn("nearby_projects", density)
        self.assertLessEqual(len(density["nearby_projects"]), 10)

        # 9. get_land_records
        land = srv.get_land_records(pid)
        self.assertIn("block_clearances", land)
        self.assertIn("bu_status", land)

        # 10. trace_entity_network
        net = srv.trace_entity_network(pid)
        self.assertIn("network", net)

        # 11. get_promoter_portfolio
        port = srv.get_promoter_portfolio(project_id=pid)
        self.assertIn("resolved_projects", port)

        # 12. audit_discrepancies
        audit = srv.audit_discrepancies(pid, include_skipped=True)
        self.assertIsInstance(audit, list)

        # 13. get_escrow_and_finances
        escrow_fin = srv.get_escrow_and_finances(pid)
        self.assertIn("escrow_health", escrow_fin)
        self.assertIn("runway_analysis", escrow_fin)

        # 14. get_regulatory_radar
        radar = srv.get_regulatory_radar(pid)
        self.assertIn("form5_annual_audits", radar)
        self.assertIn("bu_status", radar)

    def test_mcp_resources_and_fastmcp_app(self):
        """Verify FastMCP application tools and read-only resources."""
        pid = 16562

        async def check_resources():
            summary_res = await mcp.read_resource(f"rera://project/{pid}/summary")
            summary_json = json.loads(summary_res.contents[0].content)
            self.assertIn("data", summary_json)
            self.assertIn("name", summary_json["data"])

            pricing_res = await mcp.read_resource(f"rera://project/{pid}/pricing")
            pricing_json = json.loads(pricing_res.contents[0].content)
            self.assertIn("pricing_trend", pricing_json["data"])

            cluster_res = await mcp.read_resource(f"rera://cluster/{pid}/profile")
            cluster_json = json.loads(cluster_res.contents[0].content)
            self.assertIn("nearby_projects", cluster_json["data"])

        anyio.run(check_resources)

    def test_unit_transactions_indexing_and_explore_latency(self):
        """Verify query_unit_transactions uses index with zero full table scan and /api/explore < 0.5s."""
        # 1. Verify index usage on unit_transactions
        con = self.mcp_server.con
        plan = con.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM unit_transactions WHERE project_id = ? AND status = ? LIMIT 50",
            (16562, "BOOKED"),
        ).fetchall()
        plan_details = " ".join([dict(p)["detail"] for p in plan])
        self.assertIn("SEARCH unit_transactions USING INDEX", plan_details)
        self.assertNotIn("SCAN unit_transactions", plan_details)

        # 2. Verify /api/explore latency < 0.5s
        with TestClient(app) as client:
            t0 = time.perf_counter()
            resp = client.get("/api/explore?limit=25")
            duration = time.perf_counter() - t0
            self.assertEqual(resp.status_code, 200)
            self.assertLess(duration, 0.5, f"Explore latency {duration:.3f}s exceeded 0.5s threshold")


if __name__ == "__main__":
    unittest.main()
