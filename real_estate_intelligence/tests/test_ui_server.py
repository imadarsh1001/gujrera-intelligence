"""Automated tests for UI HTTP server endpoints, quantitative analytics, and AI Copilot."""

import io
import json
import sys
import unittest
from pathlib import Path
from urllib.parse import urlencode

# Ensure root package is discoverable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "real_estate_intelligence"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from real_estate_intelligence.ui.server import IntelligenceRequestHandler


class MockWfile(io.BytesIO):
    """In-memory sink for HTTP server response writes."""
    pass


class DummyServer:
    pass


class TestUIServerEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = Path(__file__).resolve().parent.parent / "data" / "test_intelligence.sqlite"
        IntelligenceRequestHandler.setup_backends(cls.db_path)

    def _make_get_request(self, path: str):
        handler = IntelligenceRequestHandler.__new__(IntelligenceRequestHandler)
        handler.con = IntelligenceRequestHandler.con
        handler.pricing_engine = IntelligenceRequestHandler.pricing_engine
        handler.verifier = IntelligenceRequestHandler.verifier
        handler.auditor = IntelligenceRequestHandler.auditor
        handler.search_engine = IntelligenceRequestHandler.search_engine
        handler.graph_engine = IntelligenceRequestHandler.graph_engine
        handler.mcp_server = IntelligenceRequestHandler.mcp_server

        handler.path = path
        handler.headers = {}
        handler.wfile = io.BytesIO()
        handler.rfile = io.BytesIO()

        # Capture status code and headers
        handler.response_code = 200
        handler.response_headers = {}

        def mock_send_response(code, message=None):
            handler.response_code = code

        def mock_send_header(keyword, value):
            handler.response_headers[keyword] = value

        def mock_end_headers():
            pass

        def mock_send_error(code, message=None):
            handler.response_code = code

        handler.send_response = mock_send_response
        handler.send_header = mock_send_header
        handler.end_headers = mock_end_headers
        handler.send_error = mock_send_error

        handler.do_GET()
        return handler.response_code, handler.wfile.getvalue()

    def _make_post_request(self, path: str, payload: dict):
        handler = IntelligenceRequestHandler.__new__(IntelligenceRequestHandler)
        handler.con = IntelligenceRequestHandler.con
        handler.pricing_engine = IntelligenceRequestHandler.pricing_engine
        handler.verifier = IntelligenceRequestHandler.verifier
        handler.auditor = IntelligenceRequestHandler.auditor
        handler.search_engine = IntelligenceRequestHandler.search_engine
        handler.graph_engine = IntelligenceRequestHandler.graph_engine
        handler.mcp_server = IntelligenceRequestHandler.mcp_server

        raw_body = json.dumps(payload).encode("utf-8")
        handler.path = path
        handler.headers = {"Content-Length": str(len(raw_body))}
        handler.wfile = io.BytesIO()
        handler.rfile = io.BytesIO(raw_body)

        handler.response_code = 200
        handler.response_headers = {}

        def mock_send_response(code, message=None):
            handler.response_code = code

        def mock_send_header(keyword, value):
            handler.response_headers[keyword] = value

        def mock_end_headers():
            pass

        def mock_send_error(code, message=None):
            handler.response_code = code

        handler.send_response = mock_send_response
        handler.send_header = mock_send_header
        handler.end_headers = mock_end_headers
        handler.send_error = mock_send_error

        handler.do_POST()
        return handler.response_code, handler.wfile.getvalue()

    def test_root_index_html(self):
        code, body = self._make_get_request("/")
        self.assertEqual(code, 200)
        text = body.decode("utf-8")
        self.assertIn("<!DOCTYPE html>", text)
        self.assertIn("chart.umd.min.js", text)
        self.assertIn("survivalCurveChart", text)
        self.assertIn("shapWaterfallChart", text)
        self.assertIn("priceTrajectoryChart", text)
        self.assertIn("copilotDrawer", text)

    def test_api_projects(self):
        code, body = self._make_get_request("/api/projects")
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)
        self.assertIn("project_id", data[0])

    def test_api_analytics_survival(self):
        code, body = self._make_get_request("/api/analytics/survival?project_id=16562")
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("project_id", data)
        self.assertEqual(data["project_id"], 16562)
        self.assertIn("delay_risk_label", data)
        self.assertIn("forecasted_handover_dates", data)
        self.assertIn("survival_curve", data)
        self.assertGreater(len(data["survival_curve"]), 0)

    def test_api_analytics_pricing_trend(self):
        # Test project 13705 with multi-year agreement history
        code, body = self._make_get_request("/api/analytics/pricing_trend?project_id=13705")
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("quarterly_trajectory", data)
        self.assertIn("cagr_pct", data)
        self.assertIn("price_appreciation_pct", data)
        self.assertGreaterEqual(data["total_agreements_analyzed"], 1)

    def test_api_analytics_ml_pricing(self):
        code, body = self._make_get_request("/api/analytics/ml_pricing?project_id=16562&asset_class=Residential&carpet_area_sqft=1200")
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("predicted_rate_per_sqft", data)
        self.assertIn("shap_values", data)
        self.assertTrue(data.get("efficiency_check_passed", False))

    def test_copilot_escrow_query(self):
        code, body = self._make_post_request("/api/copilot", {
            "query": "Audit Section 4(2)(l)(D) escrow retention and withdrawals",
            "project_id": 16562
        })
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("reply", data)
        self.assertIn("citations", data)
        self.assertIn("Escrow", data["reply"])
        self.assertTrue(any("Section 4(2)(l)(D)" in c for c in data["citations"]))

    def test_copilot_mortgage_query(self):
        code, body = self._make_post_request("/api/copilot", {
            "query": "Check title clearance, land records and bank mortgages",
            "project_id": 16562
        })
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("reply", data)
        self.assertIn("citations", data)
        self.assertIn("Title & Encumbrance", data["reply"])

    def test_copilot_delay_query(self):
        code, body = self._make_post_request("/api/copilot", {
            "query": "Analyze survival handover delay risk and delivery percentiles",
            "project_id": 16562
        })
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("reply", data)
        self.assertIn("p50", data["reply"])

    def test_copilot_cagr_query(self):
        code, body = self._make_post_request("/api/copilot", {
            "query": "What is the multi-year transaction price trajectory and CAGR?",
            "project_id": 13705
        })
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("reply", data)
        self.assertIn("CAGR", data["reply"])

    def test_copilot_greeting_query(self):
        code, body = self._make_post_request("/api/copilot", {
            "query": "ok",
            "project_id": 16562
        })
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("reply", data)
        self.assertIn("Suggested Inquiries", data["reply"])
        self.assertIn("70% Escrow Audit", data["reply"])

    def test_copilot_launch_date_query(self):
        code, body = self._make_post_request("/api/copilot", {
            "query": "when this project launch?",
            "project_id": 16562
        })
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("reply", data)
        self.assertIn("Official RERA Launch Date", data["reply"])
        self.assertIn("2023-04-28", data["reply"])

    def test_copilot_lifecycle_since_launch_query(self):
        code, body = self._make_post_request("/api/copilot", {
            "query": "analyse it since it launch",
            "project_id": 16562
        })
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("reply", data)
        self.assertIn("Timeline & Physical Construction Velocity", data["reply"])
        self.assertIn("Sales Absorption & Commercial/Residential Overhang", data["reply"])
        self.assertIn("Capital Inflows & Financial Health", data["reply"])

    def test_copilot_sales_absorption_query(self):
        code, body = self._make_post_request("/api/copilot", {
            "query": "previous quarter sales?",
            "project_id": 16562
        })
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("reply", data)
        self.assertIn("Overall Scheme Absorption", data["reply"])
        self.assertIn("181 of 252 units booked", data["reply"])
        self.assertIn("Block-by-Block Sales Breakdown", data["reply"])

    def test_copilot_contagion_query(self):
        code, body = self._make_post_request("/api/copilot", {
            "query": "Trace shared professionals and contagion risk",
            "project_id": 16562
        })
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("reply", data)
        self.assertIn("Entity Network & Contagion Audit", data["reply"])
        self.assertIn("Certified Professional Team", data["reply"])
        self.assertIn("Contagion Risk Verdict", data["reply"])

    def test_agentic_copilot_tool_dispatch(self):
        from real_estate_intelligence.agent.copilot import AgenticCopilot
        copilot = AgenticCopilot(IntelligenceRequestHandler.mcp_server)
        
        # Test tool dispatch directly
        escrow = copilot.dispatch_tool("get_escrow_health", {"project_id": 16562})
        self.assertIn("escrow_70_percent_accounts", escrow)
        self.assertIn("cash_flow_summary", escrow)

        delay = copilot.dispatch_tool("forecast_completion_delay", {"project_id": 16562})
        self.assertIn("delay_risk_label", delay)
        self.assertIn("forecasted_handover_dates", delay)

        pricing = copilot.dispatch_tool("predict_pricing_benchmark", {
            "project_id": 16562,
            "asset_class": "Residential",
            "carpet_area_sqft": 1200.0
        })
        self.assertIn("predicted_rate_per_sqft", pricing)
        self.assertIn("shap_values", pricing)

    def test_copilot_api_with_api_key_fallback(self):
        # Testing with a dummy key: should gracefully fall back to local engine without raising 500
        code, body = self._make_post_request("/api/copilot", {
            "query": "what is market rate?",
            "project_id": 16562,
            "api_key": "AIzaSy_dummy_key_for_testing"
        })
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("reply", data)
        self.assertIn("Pricing Realization", data["reply"])

    def test_verify_claim_invalid_numeric_returns_400(self):
        # Non-numeric claim values must return HTTP 400, not crash the connection
        code, _ = self._make_get_request(
            "/api/verify_claim?project_id=16562&claimed_rate=abc&claimed_sold=&claimed_date="
        )
        self.assertEqual(code, 400)

    def test_project_payload_excludes_self_sister_scheme(self):
        # previous_projects self-links must not surface the project as its own sister scheme
        code, body = self._make_get_request("/api/project/16562")
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        prior_ids = [p["linked_project_id"] for p in data.get("prior_projects", [])]
        self.assertNotIn(16562, prior_ids)
        # revision summary fields ride along for the Project Detail section
        self.assertIn(data["revision_state"], {"revision_observed", "no_revision_observed", "insufficient_history"})
        self.assertIsInstance(data["revision_evidence_dates"], list)
        self.assertGreaterEqual(data["filings_count"], 1)

    def test_search_invalid_project_id_returns_400(self):
        code, _ = self._make_get_request("/api/search?query=encumbrance&project_id=abc")
        self.assertEqual(code, 400)

    def test_analytics_invalid_project_id_returns_400(self):
        code, _ = self._make_get_request("/api/analytics/pricing_trend?project_id=notanumber")
        self.assertEqual(code, 400)
        code, _ = self._make_get_request("/api/analytics/survival?project_id=notanumber")
        self.assertEqual(code, 400)
        code, _ = self._make_get_request("/api/analytics/ml_pricing?project_id=notanumber")
        self.assertEqual(code, 400)

    def test_static_assets_served_and_traversal_blocked(self):
        code, body = self._make_get_request("/static/vendor/chart.umd.min.js")
        self.assertEqual(code, 200)
        self.assertGreater(len(body), 1000)
        code, _ = self._make_get_request("/static/missing.js")
        self.assertEqual(code, 404)
        # path traversal out of the static directory must be refused
        code, _ = self._make_get_request("/static/../server.py")
        self.assertEqual(code, 404)

    def test_map_config_and_proxy_guard(self):
        import os
        saved = os.environ.pop("MAPTILER_API_KEY", None)
        try:
            code, body = self._make_get_request("/api/map/config")
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(body.decode("utf-8")), {"maptiler_proxy": False})
            # without a server key the proxy is disabled entirely
            code, _ = self._make_get_request("/api/maptiler/maps/streets-v2/style.json")
            self.assertEqual(code, 404)
        finally:
            if saved is not None:
                os.environ["MAPTILER_API_KEY"] = saved

    def test_revision_state_pure_function(self):
        from real_estate_intelligence.ui.server import _revision_state
        self.assertEqual(_revision_state(1, 0), "insufficient_history")
        self.assertEqual(_revision_state(0, 2), "insufficient_history")
        self.assertEqual(_revision_state(2, 0), "no_revision_observed")
        self.assertEqual(_revision_state(2, 1), "revision_observed")
        self.assertEqual(_revision_state(5, 3), "revision_observed")

    def test_api_explore_shape_and_fields(self):
        code, body = self._make_get_request("/api/explore")
        self.assertEqual(code, 200)
        rows = json.loads(body.decode("utf-8"))
        self.assertIsInstance(rows, list)
        self.assertGreaterEqual(len(rows), 1)
        required = {"project_id", "name", "registration_number", "district", "taluka", "project_type",
                    "promoter_name", "completion_date", "progress_pct", "latitude", "longitude",
                    "complaints_count", "extensions_count",
                    "filings_count", "latest_filing_date", "days_since_latest_filing", "revision_state",
                    "revision_evidence_dates", "unit_types", "min_price_booked", "min_rate_sqft_booked",
                    "price_date_min", "price_date_max", "booked_by_unit_type", "architects"}
        row = rows[0]
        for key in required:
            self.assertIn(key, row)
        self.assertIn(row["revision_state"], {"revision_observed", "no_revision_observed", "insufficient_history"})
        self.assertIsInstance(row["booked_by_unit_type"], dict)
        self.assertIsInstance(row["unit_types"], list)
        self.assertIsInstance(row["architects"], list)

    def test_api_explore_price_columns_booked_only(self):
        code, body = self._make_get_request("/api/explore")
        rows = {r["project_id"]: r for r in json.loads(body.decode("utf-8"))}
        pid = 16562
        self.assertIn(pid, rows)
        expected = IntelligenceRequestHandler.con.execute(
            "SELECT MIN(rate_per_sqft) FROM unit_transactions WHERE project_id = ? AND status = 'BOOKED' AND rate_per_sqft > 0",
            (pid,),
        ).fetchone()[0]
        got = rows[pid]["min_rate_sqft_booked"]
        if expected is None:
            self.assertIsNone(got)
        else:
            self.assertAlmostEqual(got, expected, places=2)
        # UNBOOKED declared prices must not leak into the aggregate
        unbooked_min = IntelligenceRequestHandler.con.execute(
            "SELECT MIN(rate_per_sqft) FROM unit_transactions WHERE project_id = ? AND status != 'BOOKED' AND rate_per_sqft > 0",
            (pid,),
        ).fetchone()[0]
        if unbooked_min is not None and unbooked_min < expected:
            self.assertGreaterEqual(got, expected)

    def test_api_explore_empty_db(self):
        import os
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            IntelligenceRequestHandler.setup_backends(tmp.name)
            code, body = self._make_get_request("/api/explore")
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(body.decode("utf-8")), [])
        finally:
            IntelligenceRequestHandler.con.close()
            IntelligenceRequestHandler.setup_backends(type(self).db_path)
            try:
                os.unlink(tmp.name)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
