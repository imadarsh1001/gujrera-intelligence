"""Unit tests for SpatialEmpiricalPricer and enhanced ProjectAuditor audit features."""

import sqlite3
import unittest

from real_estate_intelligence.analytics.audit import ProjectAuditor
from real_estate_intelligence.analytics.spatial_pricing import SpatialEmpiricalPricer
from real_estate_intelligence.db.database import init_schema


class TestSpatialPricingAndAudit(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        init_schema(self.con)
        self.pricer = SpatialEmpiricalPricer(self.con)
        self.auditor = ProjectAuditor(self.con)

    def tearDown(self):
        self.con.close()

    def test_spatial_pricer_contract_and_tier1(self):
        """Tier 1 benchmark: projects within 2km with same (asset_class, year) when N >= 5."""
        # Insert target project at (23.000, 72.500)
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, district, taluka, latitude, longitude)
            VALUES (1, 'TARGET TOWER', 'REG1', 10, 'DEV1', 'Ahmedabad', 'CITY', 23.000, 72.500)
            """
        )
        # Insert target project units (booked @ 5000, unbooked @ 6000 -> markup +20%)
        self.con.execute(
            """
            INSERT INTO unit_transactions (project_id, block_name, status, asset_class, carpet_area_sqft, rate_per_sqft, agreement_date)
            VALUES (1, 'A', 'BOOKED', 'Residential', 1000.0, 5000.0, '2025-06-15')
            """
        )
        self.con.execute(
            """
            INSERT INTO unit_transactions (project_id, block_name, status, asset_class, carpet_area_sqft, rate_per_sqft, agreement_date)
            VALUES (1, 'A', 'UNBOOKED', 'Residential', 1000.0, 6000.0, NULL)
            """
        )

        # Insert neighbor project at 1km distance (~0.009 deg lat)
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, district, taluka, latitude, longitude)
            VALUES (2, 'NEIGHBOR TOWER', 'REG2', 20, 'DEV2', 'Ahmedabad', 'CITY', 23.008, 72.500)
            """
        )
        # Insert 5 booked deeds in 2025
        rates = [4000.0, 4500.0, 5000.0, 5500.0, 6000.0]
        for r in rates:
            self.con.execute(
                """
                INSERT INTO unit_transactions (project_id, block_name, status, asset_class, carpet_area_sqft, rate_per_sqft, agreement_date)
                VALUES (2, 'A', 'BOOKED', 'Residential', 1000.0, ?, '2025-04-10')
                """,
                (r,),
            )
        self.con.commit()

        res = self.pricer.benchmark(1, asset_class="Residential", year=2025)

        # Check contract keys
        expected_keys = {
            "median_rate_sqft",
            "p25",
            "p75",
            "iqr",
            "sample_size",
            "benchmark_tier",
            "year_used",
            "project_booked_median",
            "project_unbooked_median",
            "unbooked_markup_pct",
            "statewide_markup_baseline_pct",
        }
        self.assertTrue(expected_keys.issubset(res.keys()))
        self.assertEqual(res["benchmark_tier"], "Tier 1")
        self.assertEqual(res["year_used"], 2025)
        # Neighbor has 5 deeds + target project has 1 deed = 6 deeds
        self.assertEqual(res["sample_size"], 6)
        self.assertEqual(res["project_booked_median"], 5000.0)
        self.assertEqual(res["project_unbooked_median"], 6000.0)
        self.assertEqual(res["unbooked_markup_pct"], 20.0)
        self.assertEqual(res["statewide_markup_baseline_pct"], 12.63)

    def test_spatial_pricer_tier2_fallback(self):
        """Tier 2 fallback: within 5km and year ± 1 when 2km same-year has N < 5."""
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, district, taluka, latitude, longitude)
            VALUES (10, 'ORIGIN TOWER', 'REG10', 10, 'DEV1', 'Ahmedabad', 'CITY', 23.000, 72.500)
            """
        )
        # Neighbor at 3.5km (~0.03 deg lat) with transactions in 2024 (year - 1)
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, district, taluka, latitude, longitude)
            VALUES (11, 'MID_DIST TOWER', 'REG11', 20, 'DEV2', 'Ahmedabad', 'CITY', 23.030, 72.500)
            """
        )
        for r in [4200.0, 4400.0, 4600.0, 4800.0, 5000.0]:
            self.con.execute(
                """
                INSERT INTO unit_transactions (project_id, block_name, status, asset_class, carpet_area_sqft, rate_per_sqft, agreement_date)
                VALUES (11, 'A', 'BOOKED', 'Residential', 900.0, ?, '2024-08-20')
                """,
                (r,),
            )
        self.con.commit()

        res = self.pricer.benchmark(10, asset_class="Residential", year=2025)
        self.assertEqual(res["benchmark_tier"], "Tier 2")
        self.assertEqual(res["sample_size"], 5)
        self.assertEqual(res["median_rate_sqft"], 4600.0)

    def test_spatial_pricer_tier3_district_taluka_fallback(self):
        """Tier 3 fallback: (district, taluka, asset_class, year) when coordinates are missing."""
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, district, taluka, latitude, longitude)
            VALUES (20, 'NO_GPS TOWER', 'REG20', 10, 'DEV1', 'Surat', 'CHORASI', NULL, NULL)
            """
        )
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, district, taluka, latitude, longitude)
            VALUES (21, 'SURAT TOWER', 'REG21', 20, 'DEV2', 'Surat', 'CHORASI', 21.170, 72.831)
            """
        )
        for r in [3000.0, 3200.0, 3400.0, 3600.0, 3800.0]:
            self.con.execute(
                """
                INSERT INTO unit_transactions (project_id, block_name, status, asset_class, carpet_area_sqft, rate_per_sqft, agreement_date)
                VALUES (21, 'A', 'BOOKED', 'Commercial', 500.0, ?, '2025-03-15')
                """,
                (r,),
            )
        self.con.commit()

        res = self.pricer.benchmark(20, asset_class="Commercial", year=2025)
        self.assertEqual(res["benchmark_tier"], "Tier 3")
        self.assertEqual(res["sample_size"], 5)
        self.assertEqual(res["median_rate_sqft"], 3400.0)

    def test_bu_status_check_and_expired_completion_lead(self):
        """Project with valid BU NOC does NOT trigger expired completion lead."""
        # Project 30 expired in 2024, but has BU NOC in project_summaries
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, district, completion_date)
            VALUES (30, 'COMPLETED TOWER', 'REG30', 1, 'ALPHA', 'Ahmedabad', '2024-05-30')
            """
        )
        self.con.execute(
            """
            INSERT INTO project_summaries (project_id, name, registration_number, promoter_name, district, tier, has_bu_noc, bu_certificate_no)
            VALUES (30, 'COMPLETED TOWER', 'REG30', 'ALPHA', 'Ahmedabad', 'deep_audit', 1, 'BU-2024-999')
            """
        )
        self.con.commit()

        bu = self.auditor.check_bu_status(30)
        self.assertTrue(bu["has_bu_noc"])
        self.assertEqual(bu["evidence_source"], "project_summaries.has_bu_noc")

        leads = self.auditor.audit_project(30)
        expired_leads = [l for l in leads if "Expired" in l.title]
        self.assertEqual(len(expired_leads), 0)

    def test_cohort_flags_legacy_and_govt(self):
        """Test is_legacy_grandfathered and is_govt_authority detection."""
        # Legacy grandfathered project
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, district, completion_date)
            VALUES (40, 'OLD TOWER', 'REG40', 1, 'REGULAR DEV', 'Ahmedabad', '2018-12-31')
            """
        )
        flags_40 = self.auditor.get_cohort_flags(40)
        self.assertTrue(flags_40["is_legacy_grandfathered"])
        self.assertFalse(flags_40["is_govt_authority"])

        # Govt authority project (AUDA)
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, district, completion_date)
            VALUES (41, 'EWS HOUSING', 'REG41', 2, 'AHMEDABAD URBAN DEVELOPMENT AUTHORITY', 'Ahmedabad', '2026-12-31')
            """
        )
        flags_41 = self.auditor.get_cohort_flags(41)
        self.assertFalse(flags_41["is_legacy_grandfathered"])
        self.assertTrue(flags_41["is_govt_authority"])

    def test_section_4_2_l_d_formula_land_cost(self):
        """Section 4(2)(l)(D) formula does not falsely accuse developer when land cost is accounted for."""
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, district, engg_score_pct)
            VALUES (50, 'PRIME ESTATE', 'REG50', 1, 'DEV', 'Ahmedabad', 10.0)
            """
        )
        # Estimated cost: 100 Cr, Incurred: 40 Cr (Land)
        self.con.execute(
            """
            INSERT INTO finances (project_id, filing_date, filing_type, form_three_id, estimated_cost, incurred_and_paid)
            VALUES (50, '2025-01-01', 'latest', 101, 1000000000.0, 400000000.0)
            """
        )
        # Deposits: 50 Cr, Withdrawn: 40 Cr
        # With 35% land cost baseline: eligible = 35% + 65% * 10% = 41.5% of 50 Cr = 20.75 Cr (if capped by deposits)
        # Or if withdrawn <= allowed, verify behavior
        self.con.execute(
            """
            INSERT INTO banks (project_id, bank_name, account_type, closing_bal, deposit_amt, withdrawal_amt)
            VALUES (50, 'HDFC Bank', 1, 100000000.0, 500000000.0, 200000000.0)
            """
        )
        self.con.commit()

        leads = self.auditor.audit_project(50)
        escrow_breach = [l for l in leads if "Statutory 70% Escrow Over-Withdrawal" in l.title]
        # ₹20 Cr withdrawn on ₹50 Cr deposits with eligible fraction 41.5% (allowable = ₹20.75 Cr) -> NOT a breach!
        self.assertEqual(len(escrow_breach), 0)

    def test_skipped_uningested_reporting(self):
        """When include_skipped=True, uningested tables are explicitly surfaced as SKIPPED_UNINGESTED."""
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, district)
            VALUES (60, 'RAW STATEWIDE TOWER', 'REG60', 1, 'DEV', 'Ahmedabad')
            """
        )
        self.con.commit()

        leads_without_skipped = self.auditor.audit_project(60, include_skipped=False)
        self.assertTrue(all(l.severity != "SKIPPED_UNINGESTED" for l in leads_without_skipped))

        leads_with_skipped = self.auditor.audit_project(60, include_skipped=True)
        skipped = [l for l in leads_with_skipped if l.severity == "SKIPPED_UNINGESTED"]
        self.assertGreaterEqual(len(skipped), 3)

        # Verify audit_rule_coverage helper
        cov = self.auditor.audit_rule_coverage(60)
        self.assertEqual(cov["project_id"], 60)
        self.assertGreaterEqual(cov["total_skipped_rules"], 3)


if __name__ == "__main__":
    unittest.main()
