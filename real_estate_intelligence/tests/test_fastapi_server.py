"""Automated tests for FastAPI endpoints, quantitative analytics, and AI Copilot."""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure root and real_estate_intelligence are discoverable
root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "real_estate_intelligence"))

from fastapi.testclient import TestClient

from api.index import app, AppState, setup_backends, api_explore
from real_estate_intelligence.agent.copilot import AgenticCopilot
from real_estate_intelligence.db.queries import get_revision_state


class TestFastAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src_db = Path(__file__).resolve().parent.parent / "data" / "test_intelligence.sqlite"
        cls.tmp_file = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        cls.tmp_file.close()
        shutil.copyfile(src_db, cls.tmp_file.name)
        cls.db_path = Path(cls.tmp_file.name)
        setup_backends(cls.db_path)
        cls._seed_project_summaries()
        AppState.graph_engine.build_graph()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        if AppState.con:
            AppState.con.close()
        if hasattr(cls, "tmp_file") and os.path.exists(cls.tmp_file.name):
            try:
                os.remove(cls.tmp_file.name)
            except Exception:
                pass

    @classmethod
    def _seed_project_summaries(cls):
        con = AppState.con
        projects = con.execute(
            "SELECT project_id, name, registration_number, promoter_name, district, taluka, "
            "project_type, project_status, tier, completion_date, latitude, longitude FROM projects"
        ).fetchall()
        records = []
        for p in projects:
            pid = p[0]
            u_stats = con.execute("""
                SELECT 
                    COUNT(*),
                    SUM(CASE WHEN status = 'BOOKED' THEN 1 ELSE 0 END),
                    MIN(CASE WHEN status = 'BOOKED' AND unit_consideration > 0 THEN unit_consideration ELSE NULL END),
                    MAX(CASE WHEN status = 'BOOKED' AND unit_consideration > 0 THEN unit_consideration ELSE NULL END),
                    MIN(CASE WHEN status = 'BOOKED' AND rate_per_sqft > 0 THEN rate_per_sqft ELSE NULL END),
                    AVG(CASE WHEN status = 'BOOKED' AND rate_per_sqft > 0 THEN rate_per_sqft ELSE NULL END)
                FROM unit_transactions WHERE project_id = ?
            """, (pid,)).fetchone()
            tot_u = u_stats[0] or 0
            bk_u = u_stats[1] or 0
            unbk_u = tot_u - bk_u
            abs_pct = round((bk_u / tot_u) * 100.0, 1) if tot_u > 0 else 0.0
            min_p, max_p, min_r, avg_r = u_stats[2], u_stats[3], u_stats[4], u_stats[5]
            if avg_r is not None:
                avg_r = round(avg_r, 2)
            if min_r is not None:
                min_r = round(min_r, 2)

            types = [r[0] for r in con.execute(
                "SELECT DISTINCT unit_type FROM unit_transactions WHERE project_id = ? AND unit_type IS NOT NULL", (pid,)
            ).fetchall()]
            booked_by_type = dict(con.execute(
                "SELECT unit_type, count(*) FROM unit_transactions WHERE project_id = ? AND status = 'BOOKED' GROUP BY unit_type", (pid,)
            ).fetchall())

            records.append((
                pid, p[1], p[2], p[3], p[4], p[5], p[6], p[7], p[8], p[9],
                tot_u, bk_u, unbk_u, abs_pct, min_p, max_p, min_r, avg_r,
                json.dumps(sorted(types)) if types else None,
                json.dumps(booked_by_type) if booked_by_type else None,
                0, None, "Test Architect", None, None, "SBI",
                p[10], p[11], 1
            ))

        # Also seed project 10760 into project_summaries and projects if not present
        if not any(r[0] == 10760 for r in records):
            con.execute("""
                INSERT OR IGNORE INTO projects (
                    project_id, name, registration_number, promoter_id, promoter_name, district, taluka,
                    project_type, project_status, tier, completion_date, latitude, longitude
                ) VALUES (10760, 'AADHVAN RISE', 'PR/GJ/AHMEDABAD/AHMEDABAD CITY/AUDA/MAA09044/160921',
                    11840, 'AADHVAN BUILDCON', 'Ahmedabad', 'Daskroi', 'Residential', 'REGISTERED', 'TIER_1',
                    '2025-12-31', 23.0225, 72.5714)
            """)
            con.commit()
            records.append((
                10760, "AADHVAN RISE", "PR/GJ/AHMEDABAD/AHMEDABAD CITY/AUDA/MAA09044/160921",
                "AADHVAN BUILDCON", "Ahmedabad", "Daskroi", "Residential", "REGISTERED", "TIER_1",
                "2025-12-31", 131, 106, 25, 80.9, 4200000.0, 7500000.0, 3850.0, 4200.0,
                json.dumps(["2 BHK", "3 BHK"]), json.dumps({"2 BHK": 60, "3 BHK": 46}),
                0, None, "Test Architect", None, None, "State Bank of India",
                23.0225, 72.5714, 1
            ))

        con.executemany("""
            INSERT INTO project_summaries (
                project_id, name, registration_number, promoter_name, district, taluka,
                project_type, project_status, tier, completion_date, total_units,
                booked_units, unbooked_units, absorption_pct, min_price_booked,
                max_price_booked, min_rate_sqft_booked, avg_rate_sqft_booked,
                unit_types_json, booked_by_type_json, has_bu_noc, bu_certificate_no,
                architect_names, engineer_names, ca_name, escrow_bank_name,
                latitude, longitude, is_exact_gps
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, records)
        con.commit()

    def test_root_index_html(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        text = res.text
        self.assertIn("<!DOCTYPE html>", text)
        self.assertIn("chart.umd.min.js", text)
        self.assertIn("survivalCurveChart", text)
        self.assertIn("shapWaterfallChart", text)
        self.assertIn("priceTrajectoryChart", text)
        self.assertIn("copilotDrawer", text)
        self.assertIn("kpiEscrowRunway", text)
        self.assertIn("cardGovernanceCredentials", text)
        self.assertIn("badgeArchitectStatus", text)
        self.assertIn("badgeEngineerStatus", text)
        self.assertIn("badgeForm3CAStatus", text)

    def test_api_health(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "ok")
        self.assertGreaterEqual(data.get("projects", 0), 1)

    def test_api_projects(self):
        res = self.client.get("/api/projects")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)
        self.assertIn("project_id", data[0])

    def test_api_pricing_pid(self):
        res = self.client.get("/api/pricing/16562")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, dict)

    def test_api_map_pins(self):
        res = self.client.get("/api/map/pins")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)

    def test_api_analytics_survival(self):
        res = self.client.get("/api/analytics/survival?project_id=16562")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("project_id", data)
        self.assertEqual(data["project_id"], 16562)
        self.assertIn("delay_risk_label", data)
        self.assertIn("forecasted_handover_dates", data)
        self.assertIn("survival_curve", data)
        self.assertGreater(len(data["survival_curve"]), 0)

    def test_api_analytics_pricing_trend(self):
        res = self.client.get("/api/analytics/pricing_trend?project_id=13705")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("quarterly_trajectory", data)
        self.assertIn("cagr_pct", data)
        self.assertIn("price_appreciation_pct", data)
        self.assertGreaterEqual(data["total_agreements_analyzed"], 1)

    def test_api_analytics_ml_pricing(self):
        res = self.client.get(
            "/api/analytics/ml_pricing?project_id=16562&asset_class=Residential&carpet_area_sqft=1200"
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("predicted_rate_per_sqft", data)
        self.assertIn("shap_values", data)
        self.assertTrue(data.get("efficiency_check_passed", False))

    def test_copilot_escrow_query(self):
        res = self.client.post("/api/copilot", json={
            "query": "Audit Section 4(2)(l)(D) escrow retention and withdrawals",
            "project_id": 16562,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("reply", data)
        self.assertIn("citations", data)
        self.assertIn("Escrow", data["reply"])
        self.assertTrue(any("Section 4(2)(l)(D)" in c for c in data["citations"]))

    def test_copilot_mortgage_query(self):
        res = self.client.post("/api/copilot", json={
            "query": "Check title clearance, land records and bank mortgages",
            "project_id": 16562,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("reply", data)
        self.assertIn("citations", data)
        self.assertIn("Title & Encumbrance", data["reply"])

    def test_copilot_delay_query(self):
        res = self.client.post("/api/copilot", json={
            "query": "Analyze survival handover delay risk and delivery percentiles",
            "project_id": 16562,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("reply", data)
        self.assertIn("p50", data["reply"])

    def test_copilot_cagr_query(self):
        res = self.client.post("/api/copilot", json={
            "query": "What is the multi-year transaction price trajectory and CAGR?",
            "project_id": 13705,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("reply", data)
        self.assertIn("CAGR", data["reply"])

    def test_copilot_greeting_query(self):
        res = self.client.post("/api/copilot", json={
            "query": "ok",
            "project_id": 16562,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("reply", data)
        self.assertIn("Suggested Inquiries", data["reply"])
        self.assertIn("70% Escrow Audit", data["reply"])

    def test_copilot_launch_date_query(self):
        res = self.client.post("/api/copilot", json={
            "query": "when this project launch?",
            "project_id": 16562,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("reply", data)
        self.assertIn("Official RERA Launch Date", data["reply"])
        self.assertIn("2023-04-28", data["reply"])

    def test_copilot_lifecycle_since_launch_query(self):
        res = self.client.post("/api/copilot", json={
            "query": "analyse it since it launch",
            "project_id": 16562,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("reply", data)
        self.assertIn("Timeline & Physical Construction Velocity", data["reply"])
        self.assertIn("Sales Absorption & Commercial/Residential Overhang", data["reply"])
        self.assertIn("Capital Inflows & Financial Health", data["reply"])

    def test_copilot_sales_absorption_query(self):
        res = self.client.post("/api/copilot", json={
            "query": "previous quarter sales?",
            "project_id": 16562,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("reply", data)
        self.assertIn("Overall Scheme Absorption", data["reply"])
        self.assertIn("181 of 252 units booked", data["reply"])
        self.assertIn("Block-by-Block Sales Breakdown", data["reply"])

    def test_copilot_contagion_query(self):
        res = self.client.post("/api/copilot", json={
            "query": "Trace shared professionals and contagion risk",
            "project_id": 16562,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("reply", data)
        self.assertIn("Entity Network & Contagion Audit", data["reply"])
        self.assertIn("Certified Professional Team", data["reply"])
        self.assertIn("Contagion Risk Verdict", data["reply"])

    def test_agentic_copilot_tool_dispatch(self):
        copilot = AgenticCopilot(AppState.mcp_server)

        escrow = copilot.dispatch_tool("get_escrow_health", {"project_id": 16562})
        self.assertIn("escrow_70_percent_accounts", escrow)
        self.assertIn("cash_flow_summary", escrow)

        delay = copilot.dispatch_tool("forecast_completion_delay", {"project_id": 16562})
        self.assertIn("delay_risk_label", delay)
        self.assertIn("forecasted_handover_dates", delay)

        pricing = copilot.dispatch_tool("predict_pricing_benchmark", {
            "project_id": 16562,
            "asset_class": "Residential",
            "carpet_area_sqft": 1200.0,
        })
        self.assertIn("predicted_rate_per_sqft", pricing)
        self.assertIn("shap_values", pricing)

    def test_copilot_api_with_api_key_fallback(self):
        res = self.client.post("/api/copilot", json={
            "query": "what is market rate?",
            "project_id": 16562,
            "api_key": "AIzaSy_dummy_key_for_testing",
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("reply", data)
        self.assertIn("Pricing Realization", data["reply"])

    def test_verify_claim_invalid_numeric_returns_400(self):
        res = self.client.get(
            "/api/verify_claim?project_id=16562&claimed_rate=abc&claimed_sold=&claimed_date="
        )
        self.assertEqual(res.status_code, 400)

    def test_project_payload_excludes_self_sister_scheme(self):
        res = self.client.get("/api/project/16562")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        prior_ids = [p["linked_project_id"] for p in data.get("prior_projects", [])]
        self.assertNotIn(16562, prior_ids)
        self.assertIn(data["revision_state"], {"revision_observed", "no_revision_observed", "insufficient_history"})
        self.assertIsInstance(data["revision_evidence_dates"], list)
        self.assertIsInstance(data["revision_actioned_dates"], list)
        self.assertGreaterEqual(data["filings_count"], 1)

    def test_project_endpoint_credential_and_runway_keys(self):
        res = self.client.get("/api/project/13560")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("credential_coverage", data)
        self.assertIn("escrow_runway", data)

        cov = data["credential_coverage"]
        self.assertEqual(cov["project_id"], 13560)
        self.assertIn("roles", cov)
        self.assertIn("architect", cov["roles"])
        self.assertIn("engineer", cov["roles"])
        self.assertIn("ca_certificate", cov["roles"])
        self.assertIsInstance(cov["gap_codes"], list)

        runway = data["escrow_runway"]
        self.assertEqual(runway["project_id"], 13560)
        self.assertIn("closing_escrow_balance_inr", runway)
        self.assertIn("monthly_construction_burn_inr", runway)
        self.assertIn("insolvency_risk", runway)

    def test_search_invalid_project_id_returns_400(self):
        res = self.client.get("/api/search?query=encumbrance&project_id=abc")
        self.assertEqual(res.status_code, 400)

    def test_analytics_invalid_project_id_returns_400(self):
        res = self.client.get("/api/analytics/pricing_trend?project_id=notanumber")
        self.assertEqual(res.status_code, 400)
        res = self.client.get("/api/analytics/survival?project_id=notanumber")
        self.assertEqual(res.status_code, 400)
        res = self.client.get("/api/analytics/ml_pricing?project_id=notanumber")
        self.assertEqual(res.status_code, 400)

    def test_static_assets_served_and_traversal_blocked(self):
        res = self.client.get("/static/vendor/chart.umd.min.js")
        self.assertEqual(res.status_code, 200)
        self.assertGreater(len(res.content), 1000)
        res = self.client.get("/static/missing.js")
        self.assertEqual(res.status_code, 404)
        res = self.client.get("/static/../server.py")
        self.assertEqual(res.status_code, 404)

    def test_map_config_and_proxy_guard(self):
        saved = os.environ.pop("MAPTILER_API_KEY", None)
        try:
            res = self.client.get("/api/map/config")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json(), {"maptiler_proxy": False})
            res = self.client.get("/api/maptiler/maps/streets-v2/style.json")
            self.assertEqual(res.status_code, 404)
        finally:
            if saved is not None:
                os.environ["MAPTILER_API_KEY"] = saved

    def test_revision_state_pure_function(self):
        self.assertEqual(get_revision_state(1, 0), "insufficient_history")
        self.assertEqual(get_revision_state(0, 2), "insufficient_history")
        self.assertEqual(get_revision_state(2, 0), "no_revision_observed")
        self.assertEqual(get_revision_state(2, 1), "revision_observed")
        self.assertEqual(get_revision_state(5, 3), "revision_observed")

    def test_api_explore_shape_and_fields(self):
        res = self.client.get("/api/explore")
        self.assertEqual(res.status_code, 200)
        rows = res.json()
        self.assertIsInstance(rows, list)
        self.assertGreaterEqual(len(rows), 1)
        required = {
            "project_id", "name", "registration_number", "district", "taluka", "project_type",
            "promoter_name", "completion_date", "progress_pct", "latitude", "longitude",
            "complaints_count", "extensions_count",
            "filings_count", "latest_filing_date", "days_since_latest_filing", "revision_state",
            "revision_evidence_dates", "unit_types", "min_price_booked", "min_rate_sqft_booked",
            "price_date_min", "price_date_max", "booked_by_unit_type", "architects",
            "total_units", "booked_units", "unbooked_units", "absorption_pct",
        }
        row = rows[0]
        for key in required:
            self.assertIn(key, row)
        self.assertIn(row["revision_state"], {"revision_observed", "no_revision_observed", "insufficient_history"})
        self.assertIsInstance(row["booked_by_unit_type"], dict)
        self.assertIsInstance(row["unit_types"], list)
        self.assertIsInstance(row["architects"], list)

    def test_api_explore_project_10760_metrics(self):
        res = self.client.get("/api/explore")
        self.assertEqual(res.status_code, 200)
        rows = {r["project_id"]: r for r in res.json()}
        self.assertIn(10760, rows)
        row = rows[10760]
        self.assertIsNotNone(row["total_units"])
        self.assertIsNotNone(row["booked_units"])
        self.assertIsNotNone(row["absorption_pct"])
        self.assertEqual(row["total_units"], 131)
        self.assertEqual(row["booked_units"], 106)
        self.assertAlmostEqual(row["absorption_pct"], 80.9, places=1)

    def test_api_explore_no_unit_transactions_scan(self):
        traced_sql = []
        AppState.con.set_trace_callback(traced_sql.append)
        try:
            res = api_explore(
                limit="5", offset="0", sort_by=None, sort_dir="asc",
                district=None, taluka=None, promoter=None, project_type=None,
                search=None, q=None, unit_type=None, completion_before=None,
                min_stage=None, has_complaints=None, has_extensions=None,
            )
            self.assertIsInstance(res, dict)
            self.assertIn("items", res)
            self.assertGreater(len(traced_sql), 0)
            self.assertTrue(
                all("unit_transactions" not in sql.lower() for sql in traced_sql),
                f"Found unit_transactions in traced queries: {traced_sql}",
            )
        finally:
            AppState.con.set_trace_callback(None)

    def test_api_explore_price_columns_booked_only(self):
        res = self.client.get("/api/explore")
        rows = {r["project_id"]: r for r in res.json()}
        pid = 16562
        self.assertIn(pid, rows)
        expected = AppState.con.execute(
            "SELECT MIN(rate_per_sqft) FROM unit_transactions WHERE project_id = ? AND status = 'BOOKED' AND rate_per_sqft > 0",
            (pid,),
        ).fetchone()[0]
        got = rows[pid]["min_rate_sqft_booked"]
        if expected is None:
            self.assertIsNone(got)
        else:
            self.assertAlmostEqual(got, expected, places=2)
        unbooked_min = AppState.con.execute(
            "SELECT MIN(rate_per_sqft) FROM unit_transactions WHERE project_id = ? AND status != 'BOOKED' AND rate_per_sqft > 0",
            (pid,),
        ).fetchone()[0]
        if unbooked_min is not None and unbooked_min < expected:
            self.assertGreaterEqual(got, expected)

    def test_api_explore_empty_db(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            setup_backends(tmp.name)
            res = self.client.get("/api/explore")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json(), [])
        finally:
            AppState.con.close()
            setup_backends(type(self).db_path)
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    def test_api_explore_pagination(self):
        res = self.client.get("/api/explore?limit=3&offset=2")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, dict)
        self.assertEqual(data["limit"], 3)
        self.assertEqual(data["offset"], 2)
        self.assertGreaterEqual(data["total_count"], 3)
        self.assertEqual(len(data["items"]), 3)
        self.assertIn("project_id", data["items"][0])
        self.assertIn("name", data["items"][0])

    def test_api_explore_facets(self):
        res = self.client.get("/api/explore/facets")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("districts", data)
        self.assertIn("unit_types", data)
        self.assertIsInstance(data["districts"], dict)
        self.assertIsInstance(data["unit_types"], list)
        self.assertGreaterEqual(len(data["districts"]), 1)

    def test_api_explore_sorting(self):
        res_desc = self.client.get("/api/explore?limit=5&sort_by=rate&sort_dir=desc")
        self.assertEqual(res_desc.status_code, 200)
        d_desc = res_desc.json()
        self.assertEqual(d_desc["limit"], 5)
        rates = [it["min_rate_sqft_booked"] for it in d_desc["items"] if it["min_rate_sqft_booked"] is not None]
        for i in range(len(rates) - 1):
            self.assertGreaterEqual(rates[i], rates[i + 1])

        res_asc = self.client.get("/api/explore?limit=5&sort_by=name&sort_dir=asc")
        self.assertEqual(res_asc.status_code, 200)
        d_asc = res_asc.json()
        names = [it["name"].lower() for it in d_asc["items"] if it["name"]]
        for i in range(len(names) - 1):
            self.assertLessEqual(names[i], names[i + 1])

    def test_api_explore_sorting_sql_injection_guarded(self):
        res = self.client.get("/api/explore?limit=5&sort_by=non_existent_column;DROP+TABLE;--&sort_dir=desc")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("items", data)
        self.assertLessEqual(len(data["items"]), 5)

    def test_api_graph_scoped_ego_network(self):
        pid = 16562
        res = self.client.get(f"/api/graph?project_id={pid}&depth=2")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("nodes", data)
        self.assertIn("edges", data)
        self.assertIsInstance(data["nodes"], list)
        self.assertIsInstance(data["edges"], list)
        node_ids = {n["id"] for n in data["nodes"]}
        self.assertIn(f"project:{pid}", node_ids)
        for e in data["edges"]:
            self.assertIn(e["from"], node_ids)
            self.assertIn(e["to"], node_ids)

    def test_api_graph_unscoped_fallback(self):
        res = self.client.get("/api/graph")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("nodes", data)
        self.assertIn("edges", data)
        self.assertLessEqual(len(data["nodes"]), 250)


if __name__ == "__main__":
    unittest.main()
