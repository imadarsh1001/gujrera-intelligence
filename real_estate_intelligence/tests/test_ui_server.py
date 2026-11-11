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


if __name__ == "__main__":
    unittest.main()
