"""Phase 1.5 Polish Regression and Verification Tests.

Validates the 3 critical Phase 1.5 data-interpretation and reporting fixes:
1. Promoter Portfolio Composite Key (c) clustering (SHREEJI ASSOCIATES partitioning into disjoint clusters).
2. Trailing 4-quarter price realization & asset-class parity (Project 9036 SHALIGRAM PRIME).
3. Dossier BU ground-truth & overdue precision (BU verified vs. modern expired vs. legacy grandfathered vs. govt).
4. Shared anchors PII sanitation and scrubbing.
"""

import sqlite3
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "real_estate_intelligence"))

from real_estate_intelligence.analytics.claims_checker import SalesClaimVerifier
from real_estate_intelligence.analytics.investor_dossier import generate_investor_dossier
from real_estate_intelligence.analytics.pricing import PricingIntelligence
from real_estate_intelligence.config import DEFAULT_DB_PATH
from real_estate_intelligence.db.database import get_connection, init_schema
from real_estate_intelligence.db.redaction import redact_payload, redact_record, redact_value
from real_estate_intelligence.graph.network import resolve_promoter_portfolio
from real_estate_intelligence.mcp.server import RealEstateIntelligenceMCP


class TestPhase15Polish(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = DEFAULT_DB_PATH
        cls.has_live_db = Path(cls.db_path).exists()
        if cls.has_live_db:
            cls.live_con = sqlite3.connect(cls.db_path)
            cls.live_con.row_factory = sqlite3.Row
            cls.mcp_server = RealEstateIntelligenceMCP(cls.db_path)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "has_live_db", False) and getattr(cls, "live_con", None):
            cls.live_con.close()

    def test_promoter_portfolio_clustering_shreeji(self):
        """Test that SHREEJI ASSOCIATES partitions into distinct clusters, preventing Rajkot, Vadodara, and Gandhinagar from conflating into one HIGH group."""
        if not self.has_live_db:
            self.skipTest("Live database not available")

        res = resolve_promoter_portfolio(self.live_con, promoter_name="SHREEJI ASSOCIATES")
        self.assertEqual(res["portfolio_count"], 10)
        self.assertGreaterEqual(res["cluster_count"], 3)
        self.assertEqual(res["linkage_confidence"], "PARTITIONED_MULTI_CLUSTER")
        self.assertTrue(res["homonym_warning"])
        self.assertIn("clusters", res)

        # Inspect clusters
        clusters = res["clusters"]
        # Find Rajkot clusters
        rajkot_clusters = [c for c in clusters if "Rajkot" in c["districts"]]
        vadodara_clusters = [c for c in clusters if any("VADODARA" in d.upper() for d in c["districts"])]
        gandhinagar_clusters = [c for c in clusters if "Gandhinagar" in c["districts"]]

        self.assertGreaterEqual(len(rajkot_clusters), 1)
        self.assertGreaterEqual(len(vadodara_clusters), 1)
        self.assertGreaterEqual(len(gandhinagar_clusters), 1)

        # Verify that Rajkot Saffron Wing A & B (4509, 4517) share verified anchors and have HIGH confidence
        saffron_wing_cl = next(
            (c for c in clusters if 4509 in c["project_ids"] and 4517 in c["project_ids"]),
            None,
        )
        self.assertIsNotNone(saffron_wing_cl, "Projects 4509 and 4517 must be in the same cluster")
        self.assertEqual(saffron_wing_cl["linkage_confidence"], "HIGH")
        self.assertIn("RMCLNO77", saffron_wing_cl["shared_anchors"]["shared_licenses"])
        self.assertIn("IFSC:YESB0000475", saffron_wing_cl["shared_anchors"]["shared_banks"])

        # Verify that Vadodara and Gandhinagar project IDs are strictly disjoint from saffron_wing_cl
        vadodara_pids = {4639, 8323, 8562, 21100}
        gandhinagar_pids = {1376}
        self.assertTrue(set(saffron_wing_cl["project_ids"]).isdisjoint(vadodara_pids))
        self.assertTrue(set(saffron_wing_cl["project_ids"]).isdisjoint(gandhinagar_pids))

        # Test querying with anchor project_id=4509
        res_4509 = resolve_promoter_portfolio(self.live_con, project_id=4509)
        self.assertEqual(res_4509["linkage_confidence"], "HIGH")
        self.assertIsNotNone(res_4509["target_cluster_id"])
        resolved_pids_4509 = [p["project_id"] for p in res_4509["resolved_projects"]]
        self.assertIn(4509, resolved_pids_4509)
        self.assertIn(4517, resolved_pids_4509)
        self.assertTrue(set(resolved_pids_4509).isdisjoint(vadodara_pids))

    def test_sales_claim_trailing_4q_project_9036(self):
        """Test Project 9036 SHALIGRAM PRIME: Rs. 8,200 quote must be VERIFIED IN MARKET RANGE against trailing 4Q median, not EXAGGERATED against 5-year lifetime median."""
        if not self.has_live_db:
            self.skipTest("Live database not available")

        scv = SalesClaimVerifier(self.live_con)
        res = scv.verify_claim(9036, claimed_rate_sqft=8200.0, asset_class="Residential")
        self.assertEqual(res["project_id"], 9036)
        self.assertIn("verification_checks", res)
        checks = res["verification_checks"]
        self.assertEqual(len(checks), 1)
        check = checks[0]

        # Verify verdict is IN MARKET RANGE
        self.assertEqual(check["verdict"], "VERIFIED IN MARKET RANGE")
        self.assertEqual(check["benchmark_type"], "Trailing 4-Quarter Booked Median")
        self.assertIn("Rs. 8,200", check["claimed"])
        self.assertIn("Trailing 4Q Median", check["statutory_actual"])
        self.assertIsNotNone(check["trailing_window_start"])
        self.assertIsNotNone(check["trailing_window_end"])
        self.assertIn("historical_context", check)
        self.assertGreaterEqual(check["historical_context"]["lifetime_total_deeds"], 900)

        # Test with asset_class='All'
        res_all = scv.verify_claim(9036, claimed_rate_sqft=8200.0, asset_class="All")
        self.assertEqual(res_all["verification_checks"][0]["verdict"], "VERIFIED IN MARKET RANGE")

        # Test longitudinal trend with asset_class='Residential' excludes commercial spikes
        trend_res = self.mcp_server.get_pricing_appreciation_trend(9036, asset_class="Residential")
        self.assertEqual(trend_res["asset_class"], "Residential")
        # Ensure commercial rate spikes (up to 15688) are filtered out from residential trajectory
        traj = trend_res["quarterly_trajectory"]
        self.assertGreater(len(traj), 0)
        for q in traj:
            self.assertLess(q["max_rate_sqft"], 15000.0, f"Residential trajectory in {q['quarter']} contained commercial rate spike")

    def test_dossier_bu_clarity_project_9036(self):
        """Test Project 9036 dossier: displays GRANTED / VERIFIED with certificate, not Pending."""
        if not self.has_live_db:
            self.skipTest("Live database not available")

        dossier = generate_investor_dossier(self.live_con, 9036)
        self.assertIn("✅ BU GRANTED / VERIFIED", dossier)
        self.assertIn("4095612", dossier)
        self.assertNotIn("BU Status: **Pending**", dossier)

    def test_dossier_synthetic_overdue_and_badging(self):
        """Test synthetic overdue projects: modern private expired without BU gets red alert badge, legacy and govt get informative labels."""
        mem_con = sqlite3.connect(":memory:")
        mem_con.row_factory = sqlite3.Row
        init_schema(mem_con)

        # 1. Modern Private Expired Without BU (comp 2022-01-01, has_bu_noc=0)
        mem_con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_name, district, completion_date, start_date)
            VALUES (7001, 'MODERN DELAYED TOWERS', 'PR/GJ/AHMEDABAD/7001', 'SUN DEVELOPERS', 'Ahmedabad', '2022-01-01', '2019-01-01')
            """
        )
        mem_con.execute(
            """
            INSERT INTO project_summaries (project_id, name, registration_number, promoter_name, district, completion_date, has_bu_noc, tier)
            VALUES (7001, 'MODERN DELAYED TOWERS', 'PR/GJ/AHMEDABAD/7001', 'SUN DEVELOPERS', 'Ahmedabad', '2022-01-01', 0, 'TIER_1')
            """
        )

        # 2. Legacy Grandfathered Expired Without BU (comp 2018-01-01, has_bu_noc=0)
        mem_con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_name, district, completion_date, start_date)
            VALUES (7002, 'LEGACY OLD SCHEME', 'PR/GJ/AHMEDABAD/7002', 'VINTAGE BUILDERS', 'Ahmedabad', '2018-01-01', '2015-01-01')
            """
        )
        mem_con.execute(
            """
            INSERT INTO project_summaries (project_id, name, registration_number, promoter_name, district, completion_date, has_bu_noc, tier)
            VALUES (7002, 'LEGACY OLD SCHEME', 'PR/GJ/AHMEDABAD/7002', 'VINTAGE BUILDERS', 'Ahmedabad', '2018-01-01', 0, 'TIER_1')
            """
        )

        # 3. Government Authority Scheme (AUDA, comp 2022-01-01, has_bu_noc=0)
        mem_con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_name, district, completion_date, start_date)
            VALUES (7003, 'AUDA HOUSING SCHEME', 'PR/GJ/AHMEDABAD/7003', 'AUDA', 'Ahmedabad', '2022-01-01', '2019-01-01')
            """
        )
        mem_con.execute(
            """
            INSERT INTO project_summaries (project_id, name, registration_number, promoter_name, district, completion_date, has_bu_noc, tier)
            VALUES (7003, 'AUDA HOUSING SCHEME', 'PR/GJ/AHMEDABAD/7003', 'AUDA', 'Ahmedabad', '2022-01-01', 0, 'TIER_1')
            """
        )
        mem_con.commit()

        try:
            # Check Modern Private
            d_modern = generate_investor_dossier(mem_con, 7001)
            self.assertIn("🔴 EXPIRED_WITHOUT_BU", d_modern)
            self.assertIn("Statutory Delivery Default Alert", d_modern)

            # Check Legacy Pre-2020
            d_legacy = generate_investor_dossier(mem_con, 7002)
            self.assertIn("Legacy Pre-2020 Grandfathered", d_legacy)
            self.assertNotIn("🔴 EXPIRED_WITHOUT_BU", d_legacy)
            self.assertNotIn("Statutory Delivery Default Alert", d_legacy)

            # Check Govt Authority
            d_govt = generate_investor_dossier(mem_con, 7003)
            self.assertIn("Govt Authority Scheme", d_govt)
            self.assertNotIn("🔴 EXPIRED_WITHOUT_BU", d_govt)
            self.assertNotIn("Statutory Delivery Default Alert", d_govt)
        finally:
            mem_con.close()

    def test_shared_anchors_pii_sanitation(self):
        """Test that raw licenses with PII (PAN, Aadhaar, Email) are redacted and never enter shared_anchors or form edges."""
        mem_con = sqlite3.connect(":memory:")
        mem_con.row_factory = sqlite3.Row
        init_schema(mem_con)

        # Insert two projects that attempt to link on a raw PAN string as license_or_reg_no
        mem_con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_name, district, completion_date)
            VALUES (9501, 'LEAK TEST 1', 'REG9501', 'SENSITIVE CORP', 'Ahmedabad', '2024-01-01')
            """
        )
        mem_con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_name, district, completion_date)
            VALUES (9502, 'LEAK TEST 2', 'REG9502', 'SENSITIVE CORP', 'Ahmedabad', '2024-01-01')
            """
        )
        # PAN formatted license
        mem_con.execute(
            """
            INSERT INTO professionals (project_id, role, name, license_or_reg_no)
            VALUES (9501, 'architect', 'Test Arch', 'ABCDE1234F')
            """
        )
        mem_con.execute(
            """
            INSERT INTO professionals (project_id, role, name, license_or_reg_no)
            VALUES (9502, 'architect', 'Test Arch', 'ABCDE1234F')
            """
        )
        mem_con.commit()

        try:
            res = resolve_promoter_portfolio(mem_con, promoter_name="SENSITIVE CORP")
            # The PAN must be dropped, so projects do NOT form an edge on PAN
            self.assertNotIn("ABCDE1234F", str(res["shared_anchors"]))
            self.assertNotIn("[REDACTED", str(res["shared_anchors"]))
            # Both remain independent singletons
            self.assertEqual(res["cluster_count"], 2)
            self.assertEqual(res["clusters"][0]["shared_anchors"]["shared_licenses"], [])
            self.assertEqual(res["clusters"][1]["shared_anchors"]["shared_licenses"], [])
        finally:
            mem_con.close()

    def test_insights_endpoints_and_pii_safety(self):
        """Test /api/insights/ endpoints for response validity, caching speed, and zero PII leaks."""
        from fastapi.testclient import TestClient
        from api.index import app
        import time
        import re

        client = TestClient(app)

        # 1. Zombie Radar
        resp_z = client.get("/api/insights/zombie_radar?limit=25")
        self.assertEqual(resp_z.status_code, 200)
        z_data = resp_z.json()
        self.assertIsInstance(z_data, list)
        if z_data:
            first_z = z_data[0]
            self.assertIn("months_overdue", first_z)
            self.assertIn("status_badge", first_z)
            self.assertIn("🔴 EXPIRED_WITHOUT_BU", first_z["status_badge"])
            self.assertNotIn("progress_pct", first_z)

        # 2. Markup Spread
        resp_m = client.get("/api/insights/markup_spread")
        self.assertEqual(resp_m.status_code, 200)
        m_data = resp_m.json()
        self.assertEqual(m_data["statewide_baseline_markup_pct"], 12.63)
        self.assertIn("empirical_markup_pct", m_data)
        self.assertIn("top_districts_breakdown", m_data)

        # Warm latency check
        t0 = time.time()
        resp_m_warm = client.get("/api/insights/markup_spread")
        warm_ms = (time.time() - t0) * 1000
        self.assertEqual(resp_m_warm.status_code, 200)
        self.assertLess(warm_ms, 200.0, f"Warm markup spread latency exceeded 200ms: {warm_ms:.2f}ms")

        # 3. Developer Clusters Overview
        resp_d_overview = client.get("/api/insights/developer_clusters")
        self.assertEqual(resp_d_overview.status_code, 200)
        d_over = resp_d_overview.json()
        self.assertEqual(d_over["mode"], "statewide_developer_overview")
        self.assertIn("frequent_brand_names", d_over)

        # 4. Developer Clusters Targeted (SHREEJI ASSOCIATES)
        resp_d_query = client.get("/api/insights/developer_clusters?promoter_name=SHREEJI%20ASSOCIATES")
        self.assertEqual(resp_d_query.status_code, 200)
        d_q = resp_d_query.json()
        self.assertIn("clusters", d_q)
        self.assertIn(d_q["linkage_confidence"], ("PARTITIONED_MULTI_CLUSTER", "HIGH", "MEDIUM", "LOW"))

        # Warm cluster query latency check
        t0 = time.time()
        resp_d_warm = client.get("/api/insights/developer_clusters?promoter_name=SHREEJI%20ASSOCIATES")
        warm_d_ms = (time.time() - t0) * 1000
        self.assertEqual(resp_d_warm.status_code, 200)
        self.assertLess(warm_d_ms, 200.0, f"Warm developer clusters latency exceeded 200ms: {warm_d_ms:.2f}ms")

        # 5. PII Scrubbing Audit across all responses
        all_json_texts = [resp_z.text, resp_m.text, resp_d_overview.text, resp_d_query.text]
        pan_regex = re.compile(r"\b[A-Za-z]{5}\d{4}[A-Za-z]\b")
        aadhaar_regex = re.compile(r"(?<![\d.])\b\d{4}\s?\d{4}\s?\d{4}\b(?![\d.])")
        email_regex = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
        bank_account_regex = re.compile(r"(?i)\b(?:a/c(?:\s*no)?|account(?:\s*no)?\.?)\s*[:#-]?\s*(\d{8,18})\b")

        for txt in all_json_texts:
            pans = [p for p in pan_regex.findall(txt) if not p.startswith("REDACT")]
            self.assertEqual(pans, [], f"Leaked PAN found in insights responses: {pans}")

            aadhaars = [a for a in aadhaar_regex.findall(txt) if not a.startswith("REDACT")]
            self.assertEqual(aadhaars, [], f"Leaked Aadhaar found in insights responses: {aadhaars}")

            emails = [e for e in email_regex.findall(txt) if not e.startswith("REDACT")]
            self.assertEqual(emails, [], f"Leaked Email found in insights responses: {emails}")

            bank_leaks = bank_account_regex.findall(txt)
            self.assertEqual(bank_leaks, [], f"Leaked bank account found in insights responses: {bank_leaks}")


if __name__ == "__main__":
    unittest.main()
