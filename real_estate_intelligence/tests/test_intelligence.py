"""Unit tests for Real Estate Intelligence core modules."""

import sqlite3
import unittest
from pathlib import Path

from real_estate_intelligence.config import WORKSPACE_ROOT
from real_estate_intelligence.analytics.audit import ProjectAuditor
from real_estate_intelligence.db.database import get_connection, init_schema
from real_estate_intelligence.db.fts import index_page_text, init_fts, search_documents
from real_estate_intelligence.documents.parser import classify_document_type
from real_estate_intelligence.graph.network import KnowledgeGraph


class TestIntelligenceCore(unittest.TestCase):
    def setUp(self):
        # In-memory SQLite connection for fast isolated testing
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        init_schema(self.con)
        init_fts(self.con)

    def tearDown(self):
        self.con.close()

    def test_schema_tables_exist(self):
        cur = self.con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r[0] for r in cur.fetchall()}
        required = {
            "projects",
            "promoters",
            "professionals",
            "banks",
            "inventory_blocks",
            "quarterly_timeline",
            "finances",
            "applications",
            "form5_compliance",
            "noc_bu_records",
            "documents_catalog",
            "document_fts",
            "unit_transactions",
            "document_jobs",
            "market_listings",
        }
        self.assertTrue(required.issubset(tables), f"Missing tables: {required - tables}")

        # Check views
        cur.execute("SELECT name FROM sqlite_master WHERE type='view'")
        views = {r[0] for r in cur.fetchall()}
        self.assertIn("v_current_projects", views)
        self.assertIn("v_current_unit_transactions", views)

    def test_fts5_indexing_and_search(self):
        index_page_text(
            con=self.con,
            doc_uid_hash="hash_123",
            project_id=16562,
            doc_type="form_three_ca",
            file_name="ca_certificate.pdf",
            page_number=1,
            content="Total cost incurred and paid for THE BALCONY is Rs 1020551131 as verified by CA Niravkumar Donda.",
        )
        self.con.commit()

        results = search_documents(self.con, query="BALCONY Niravkumar", project_id=16562)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["project_id"], 16562)
        self.assertIn("BALCONY", results[0]["snippet"])

        # Test robust handling of punctuation, hyphens, and engine wrapper
        results_punct = search_documents(self.con, query="cost-incurred & paid*", project_id=16562)
        self.assertGreaterEqual(len(results_punct), 0)  # Handles without OperationalError

        from real_estate_intelligence.db.fts import DocumentSearchEngine
        engine = DocumentSearchEngine(self.con)
        results_engine = engine.search("Niravkumar Donda", project_id=16562)
        self.assertEqual(len(results_engine), 1)

    def test_document_classification(self):
        self.assertEqual(classify_document_type("data.titleReportUId", "project:16104:documents", "doc.pdf"), "title_search_report")
        self.assertEqual(classify_document_type("data.formThreeAList", "project:16562:latest_form_three", "form3.pdf"), "form_three_ca")
        self.assertEqual(classify_document_type("data.buPdfDocUId", "project:16104:noc_bu", "bu.pdf"), "bu_permission_noc")

    def test_cost_reversal_audit_lead(self):
        # Insert a project with an expenditure drop
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name)
            VALUES (16562, 'THE BALCONY', 'REG16562', 15778, 'DEVELOPER')
            """
        )
        # Old filing: ₹102 Cr
        self.con.execute(
            """
            INSERT INTO finances (project_id, filing_date, filing_type, form_three_id, incurred_and_paid)
            VALUES (16562, '2026-01-05', 'index', 101, 1020551131.0)
            """
        )
        # New filing: ₹53 Cr
        self.con.execute(
            """
            INSERT INTO finances (project_id, filing_date, filing_type, form_three_id, incurred_and_paid)
            VALUES (16562, '2026-10-02', 'latest', 202, 539871775.0)
            """
        )
        self.con.commit()

        auditor = ProjectAuditor(self.con)
        leads = auditor.audit_project(16562)
        financial_leads = [l for l in leads if l.category == "financial"]
        self.assertEqual(len(financial_leads), 1)
        self.assertEqual(financial_leads[0].severity, "HIGH")
        self.assertIn("Dropped by ₹48.07 Cr", financial_leads[0].title)

    def test_velocity_lag_audit_lead(self):
        self.con.execute(
            """
            INSERT INTO projects (
                project_id, name, registration_number, promoter_id, promoter_name,
                time_elapsed_pct, engg_score_pct, velocity_ratio, progress_status_label
            ) VALUES (17830, 'SANDALWOOD', 'REG17830', 16910, 'ASHWAMEGH', 68.7, 49.0, 0.71, 'ill')
            """
        )
        self.con.commit()

        auditor = ProjectAuditor(self.con)
        leads = auditor.audit_project(17830)
        vel_leads = [l for l in leads if "Velocity" in l.title]
        self.assertEqual(len(vel_leads), 1)
        self.assertEqual(vel_leads[0].severity, "HIGH")
        self.assertIn("0.71x", vel_leads[0].title)

    def test_escrow_liquidity_audit_lead(self):
        self.con.execute(
            """
            INSERT INTO projects (
                project_id, name, registration_number, promoter_id, promoter_name,
                engg_score_pct, booking_rate_pct
            ) VALUES (17830, 'SANDALWOOD', 'REG17830', 16910, 'ASHWAMEGH', 49.0, 68.5)
            """
        )
        self.con.execute(
            """
            INSERT INTO banks (
                project_id, bank_name, account_type, closing_bal, deposit_amt, withdrawal_amt
            ) VALUES (17830, 'ICICI Bank', 1, 0.0, 256687062.0, 256687062.0)
            """
        )
        self.con.commit()

        auditor = ProjectAuditor(self.con)
        leads = auditor.audit_project(17830)
        escrow_leads = [l for l in leads if "Escrow 70% Liquidity" in l.title]
        self.assertEqual(len(escrow_leads), 1)
        self.assertEqual(escrow_leads[0].severity, "HIGH")

        # Test Escrow Cash Runway modeling
        runway = auditor.calculate_escrow_runway(17830)
        self.assertEqual(runway["project_id"], 17830)
        self.assertEqual(runway["closing_escrow_balance_inr"], 0.0)
        self.assertIn("insolvency_risk", runway)

    def test_regulatory_alteration_and_defaults_audit_lead(self):
        self.con.execute(
            """
            INSERT INTO projects (
                project_id, name, registration_number, promoter_id, promoter_name,
                alterations_count, default_quarters_count, complaints_count
            ) VALUES (13705, 'DEV AASHISH', 'REG13705', 1888, 'ABJIBAPA', 1, 1, 0)
            """
        )
        self.con.commit()

        auditor = ProjectAuditor(self.con)
        leads = auditor.audit_project(13705)
        alt_leads = [l for l in leads if "Alteration" in l.title]
        def_leads = [l for l in leads if "QPR Defaults" in l.title]
        self.assertEqual(len(alt_leads), 1)
        self.assertEqual(len(def_leads), 1)

    def test_knowledge_graph_shared_professionals(self):
        self.con.executescript(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name)
            VALUES (16104, 'VRUNDAVAN ELYSIA', 'REG1', 10, 'PROM1');
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name)
            VALUES (16562, 'THE BALCONY', 'REG2', 20, 'PROM2');
            INSERT INTO promoters (promoter_id, name) VALUES (10, 'PROM1');
            INSERT INTO promoters (promoter_id, name) VALUES (20, 'PROM2');

            INSERT INTO professionals (project_id, role, name)
            VALUES (16104, 'architect', 'Umangkumar Baldevgiri Goswami');
            INSERT INTO professionals (project_id, role, name)
            VALUES (16562, 'architect', 'Umangkumar Baldevgiri Goswami');
            """
        )
        kg = KnowledgeGraph(self.con)
        stats = kg.build_graph()
        self.assertGreater(stats["nodes"], 0)
        self.assertGreater(stats["edges"], 0)

        shared = kg.find_shared_entities(16104)
        self.assertEqual(len(shared), 1)
        self.assertEqual(shared[0]["linked_project_id"], 16562)
        self.assertEqual(shared[0]["shared_entity_name"], "Umangkumar Baldevgiri Goswami")

    def test_claims_verification_logic(self):
        from real_estate_intelligence.analytics.claims_checker import SalesClaimVerifier
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name,
                                  booking_rate_pct, unbooked_units, completion_date)
            VALUES (999, 'TEST SCHEME', 'REG999', 1, 'TEST DEV', 60.0, 40, '2028-12-31')
            """
        )
        self.con.commit()
        verifier = SalesClaimVerifier(self.con)
        res = verifier.verify_claim(project_id=999, claimed_sold_pct=95.0, claimed_completion_date="2026-12-31")
        checks = {c["metric"]: c for c in res["verification_checks"]}
        self.assertIn("Booking & Inventory Absorption", checks)
        self.assertEqual(checks["Booking & Inventory Absorption"]["verdict"], "ARTIFICIAL SCARCITY")
        self.assertEqual(checks["Possession & Handover Deadline"]["verdict"], "AGGRESSIVE SALES PROMISE")

    def test_mcp_server_tools(self):
        from real_estate_intelligence.documents.search import DocumentSearchEngine
        from real_estate_intelligence.mcp.server import RealEstateIntelligenceMCP

        self.con.executescript(
            """
            INSERT INTO projects (
                project_id, name, registration_number, promoter_id, promoter_name,
                tp_scheme, final_plot_no, survey_no, latitude, longitude,
                google_maps_url, complaints_count, default_quarters_count
            ) VALUES (
                888, 'ALPHA RESIDENCY', 'REG888', 99, 'ALPHA DEV',
                'TPS 50', 'FP 12', 'SY 34', 23.05, 72.55,
                'https://maps.google.com/?q=23.05,72.55', 2, 1
            );
            INSERT INTO banks (
                project_id, bank_name, account_type, account_number_masked, closing_bal
            ) VALUES (888, 'HDFC BANK', 1, '****1234', 15000.0);
            INSERT INTO banks (
                project_id, bank_name, account_type, account_number_masked, closing_bal
            ) VALUES (888, 'SBI', 2, '****5678', 1200000.0);
            INSERT INTO noc_bu_records (
                project_id, block_name, bu_check, bu_date
            ) VALUES (888, 'Block A', 'YES', '2025-01-01');
            INSERT INTO form5_compliance (
                project_id, financial_year, status
            ) VALUES (888, '2023-24', 'SUBMITTED');
            """
        )
        self.con.commit()

        mcp = RealEstateIntelligenceMCP.__new__(RealEstateIntelligenceMCP)
        mcp.con = self.con
        mcp.search_engine = DocumentSearchEngine(self.con)
        mcp.graph = KnowledgeGraph(self.con)
        mcp.auditor = ProjectAuditor(self.con)

        # 1. Escrow Health
        escrow = mcp.get_escrow_health(888)
        self.assertEqual(len(escrow["escrow_70_percent_accounts"]), 1)
        self.assertEqual(len(escrow["collection_100_percent_accounts"]), 1)
        self.assertTrue(escrow["low_liquidity_flag"])  # 15,000 < 50,000

        # 2. Land Records
        land = mcp.get_land_records(888)
        self.assertEqual(land["tp_scheme"], "TPS 50")
        self.assertEqual(land["final_plot_no"], "FP 12")
        self.assertEqual(len(land["block_clearances"]), 1)
        self.assertEqual(land["block_clearances"][0]["bu_check"], "YES")

        # 3. Regulatory Radar
        radar = mcp.get_regulatory_radar(888)
        self.assertEqual(radar["complaints_count"], 2)
        self.assertEqual(len(radar["form5_annual_audits"]), 1)

        # 4. Project Comparison
        comp = mcp.compare_projects([888])
        self.assertEqual(len(comp), 1)
        self.assertEqual(comp[0]["name"], "ALPHA RESIDENCY")

    def test_pricing_intelligence_via_db(self):
        from real_estate_intelligence.analytics.pricing import PricingIntelligence
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name)
            VALUES (999, 'PRICING TOWER', 'REG999', 101, 'DEV')
            """
        )
        # Insert 3 unit transactions
        self.con.execute(
            """
            INSERT INTO unit_transactions (
                project_id, form_three_id, block_name, unit_type,
                carpet_area_sqm, carpet_area_sqft, unit_consideration,
                rate_per_sqft, rate_per_sqm, status, agreement_date
            ) VALUES
            (999, 1, 'Block A', 'Residential', 100.0, 1076.4, 5000000.0, 4645.0, 50000.0, 'BOOKED', '2026-05-01'),
            (999, 1, 'Block A', 'Residential', 100.0, 1076.4, 6000000.0, 5574.0, 60000.0, 'BOOKED', '2026-06-01'),
            (999, 1, 'Block B', 'Commercial', 50.0, 538.2, 4000000.0, 7432.0, 80000.0, 'BOOKED', '2026-07-01'),
            (999, 1, 'Block B', 'Commercial', 50.0, 538.2, 0.0, 0.0, 0.0, 'UNBOOKED', NULL)
            """
        )
        self.con.commit()

        pricing = PricingIntelligence(con_or_db=self.con)
        summary = pricing.get_project_pricing_summary(999)
        self.assertEqual(summary["project_id"], 999)
        self.assertEqual(summary["total_units_evaluated"], 4)
        self.assertEqual(summary["booked_units"], 3)
        self.assertEqual(summary["unbooked_units"], 1)

        overall = summary["overall_rate_per_sqft"]
        self.assertEqual(overall["count"], 3)
        self.assertEqual(overall["min"], 4645.0)
        self.assertEqual(overall["median"], 5574.0)
        self.assertEqual(overall["max"], 7432.0)

        # Block benchmarks
        blocks = summary["block_benchmarks"]
        self.assertIn("Block A", blocks)
        self.assertEqual(blocks["Block A"]["count"], 2)
        self.assertIn("Block B", blocks)
        self.assertEqual(blocks["Block B"]["count"], 1)

        # Asset class benchmarks & commercial premiums
        assets = summary["asset_class_benchmarks"]
        self.assertIn("Residential", assets)
        self.assertEqual(assets["Residential"]["count"], 2)
        self.assertIn("commercial_premiums", summary)

    def test_ingestion_with_fake_run_reader(self):
        import tempfile
        from real_estate_intelligence.db.reader import FakeRunReader, ProjectSnapshot, DocumentRef
        from real_estate_intelligence.db.loader import ingest_from_run

        snap = ProjectSnapshot(
            project_id=1234,
            name="SEAM TEST RESIDENCY",
            registration_number="REG1234",
            promoter_id=77,
            promoter_name="SEAM BUILDERS",
            status="complete",
            updated_at_utc="2026-11-04T12:00:00Z",
            static_filings={
                "project_details": {"projectDetail": {"distName": "Gandhinagar", "projectType": "Residential"}},
                "latest_form_three": {
                    "formThreeId": 321,
                    "numberOfUnits": 10,
                    "bookedUnit": 8,
                    "unBookedUnit": 2,
                    "formThreeBId": {
                        "totalEstimatedCostofTheRealEstateProject": 50000000.0,
                        "totalCostIncurredandPaid": 30000000.0,
                    },
                    "formThreeAList": [
                        {"blockName": "Tower 1", "status": "BOOKED", "carpetArea": 80.0, "unitConsideration": 4000000.0},
                        {"blockName": "Tower 1", "status": "BOOKED", "carpetArea": 90.0, "unitConsideration": 4500000.0},
                        {"blockName": "Tower 1", "status": "BOOKED", "carpetArea": 50.0, "unitConsideration": 5000000.0, "typeOfInventoryName": "Shop"},
                    ]
                },
                "latest_form_one": {"progressReport": 75.0},
                "locations": {"address": "Near TP Scheme 44, FP No 10", "finalPlotNo": "10", "tpScheme": "44"},
                "progress_reports": {"timeLaps": 80.0, "enggScore": 75.0, "progress": "On Track"},
                "promoter": {"promoterType": "Company", "total_projects": "5", "completed": "3", "ongoing": "2"},
                "banks": [{"bankName": "HDFC Bank", "branchName": "Kudasan", "depositAmt": 1000000.0, "closingBal": 500000.0}],
            }
        )
        doc_ref = DocumentRef(
            project_id=1234,
            request_key="req_1",
            json_path="data.doc",
            uid_hash="hash_pdf_1",
            file_path="raw/doc.pdf",
            sha256="sha_abc",
        )
        fake_reader = FakeRunReader(snapshots=[snap], document_refs=[doc_ref], run_id="run_2026_q3")
        with tempfile.TemporaryDirectory() as tmpdir:
            test_db = Path(tmpdir) / "test_ingest.sqlite"
            stats = ingest_from_run(source_run_or_reader=fake_reader, target_db_path=test_db, index_documents=False)
            self.assertEqual(stats["projects"], 1)
            self.assertEqual(stats["unit_transactions"], 3)
            self.assertEqual(stats["banks"], 1)
            self.assertEqual(stats["document_jobs_queued"], 1)

            tcon = sqlite3.connect(test_db)
            tcon.row_factory = sqlite3.Row
            prow = tcon.execute("SELECT * FROM projects WHERE project_id = 1234").fetchone()
            self.assertEqual(prow["name"], "SEAM TEST RESIDENCY")
            self.assertEqual(prow["run_id"], "run_2026_q3")
            self.assertEqual(prow["booking_rate_pct"], 80.0)
            self.assertEqual(prow["tp_scheme"], "44")
            self.assertEqual(prow["final_plot_no"], "10")

            # Verify view
            vrow = tcon.execute("SELECT * FROM v_current_projects WHERE project_id = 1234").fetchone()
            self.assertIsNotNone(vrow)
            self.assertEqual(vrow["name"], "SEAM TEST RESIDENCY")

            # Check unit_transactions and asset_class classification
            tx_rows = tcon.execute("SELECT * FROM unit_transactions WHERE project_id = 1234 ORDER BY id").fetchall()
            self.assertEqual(len(tx_rows), 3)
            self.assertEqual(tx_rows[0]["block_name"], "Tower 1")
            self.assertEqual(tx_rows[0]["asset_class"], "Residential")
            self.assertEqual(tx_rows[0]["run_id"], "run_2026_q3")
            self.assertGreater(tx_rows[0]["rate_per_sqft"], 0)

            # Commercial retail check
            self.assertEqual(tx_rows[2]["unit_type"], "Shop")
            self.assertEqual(tx_rows[2]["asset_class"], "Commercial_Retail")

            # Check document_jobs queue entry
            job = tcon.execute("SELECT * FROM document_jobs WHERE uid_hash = 'hash_pdf_1'").fetchone()
            self.assertIsNotNone(job)
            self.assertEqual(job["status"], "PENDING")
            self.assertEqual(job["run_id"], "run_2026_q3")
            self.assertEqual(job["project_id"], 1234)

            # Test DocumentWorker queue execution
            from real_estate_intelligence.documents.worker import DocumentWorker
            worker = DocumentWorker(con_or_path=tcon)
            q_status = worker.get_queue_status()
            self.assertEqual(q_status.get("PENDING"), 1)
            res = worker.process_next_job()
            self.assertIsNotNone(res)
            self.assertEqual(res["job_id"], job["id"])
            self.assertIn("error", res)

            tcon.close()

    def test_spatial_micro_market_analytics(self):
        from real_estate_intelligence.analytics.spatial import SpatialAnalytics, haversine_distance_km

        # 1. Test Haversine distance formula
        d = haversine_distance_km(23.0225, 72.5714, 23.2156, 72.6369)
        self.assertAlmostEqual(d, 22.5, delta=1.5)

        # 2. Insert mock spatial projects
        self.con.executescript(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, latitude, longitude, tp_scheme, total_units, booked_units, booking_rate_pct)
            VALUES (701, 'CENTRAL PARK', 'REG701', 10, 'DEV', 23.0500, 72.5500, 'TPS 44', 100, 80, 80.0);

            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, latitude, longitude, tp_scheme, total_units, booked_units, booking_rate_pct)
            VALUES (702, 'GREEN VALLEY', 'REG702', 10, 'DEV', 23.0550, 72.5550, 'TPS 44', 50, 25, 50.0);

            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, latitude, longitude, tp_scheme, total_units, booked_units, booking_rate_pct)
            VALUES (703, 'DISTANT HORIZON', 'REG703', 20, 'DEV2', 23.5000, 73.0000, 'TPS 99', 200, 100, 50.0);

            INSERT INTO unit_transactions (project_id, block_name, unit_type, status, rate_per_sqft)
            VALUES (702, 'Block A', 'Residential', 'BOOKED', 6200.0);
            """
        )
        self.con.commit()

        spatial = SpatialAnalytics(con_or_path=self.con)
        nearby = spatial.get_nearby_projects(project_id=701, radius_km=2.0)
        self.assertEqual(nearby["origin_project_id"], 701)
        self.assertEqual(nearby["nearby_count"], 1)
        self.assertEqual(nearby["nearby_projects"][0]["project_id"], 702)
        self.assertLess(nearby["nearby_projects"][0]["distance_km"], 1.5)
        self.assertEqual(nearby["micro_market_avg_rate_sqft"], 6200.0)

        # Test TP Scheme summary
        tp_sum = spatial.get_tp_scheme_summary("TPS 44")
        self.assertEqual(tp_sum["projects_count"], 2)
        self.assertEqual(tp_sum["total_units"], 150)
        self.assertEqual(tp_sum["booked_units"], 105)
        self.assertEqual(tp_sum["absorption_rate_pct"], 70.0)

    def test_hedonic_pricing_model_and_shap_efficiency(self):
        from real_estate_intelligence.analytics.ml_pricing import HedonicPricingModel

        # Insert synthetic training data
        self.con.executescript(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, district, latitude, longitude, latest_form_one_progress_pct, velocity_ratio)
            VALUES (901, 'MODEL PROJ', 'REG901', 50, 'TOP PROMOTER', 'Ahmedabad', 23.02, 72.50, 90.0, 1.2);

            INSERT INTO promoters (promoter_id, name, total_projects_claimed)
            VALUES (50, 'TOP PROMOTER', 10);

            INSERT INTO unit_transactions (project_id, block_name, unit_type, asset_class, carpet_area_sqft, status, rate_per_sqft)
            VALUES
                (901, 'A', 'Residential', 'Residential', 1200.0, 'BOOKED', 6000.0),
                (901, 'A', 'Residential', 'Residential', 1500.0, 'BOOKED', 6200.0),
                (901, 'B', 'Shop', 'Commercial_Retail', 600.0, 'BOOKED', 9500.0),
                (901, 'B', 'Shop', 'Commercial_Retail', 800.0, 'BOOKED', 9200.0),
                (901, 'C', 'Office', 'Commercial_Office', 1000.0, 'BOOKED', 7500.0),
                (901, 'C', 'Office', 'Commercial_Office', 1200.0, 'BOOKED', 7400.0),
                (901, 'A', 'Residential', 'Residential', 1100.0, 'BOOKED', 5900.0),
                (901, 'B', 'Shop', 'Commercial_Retail', 700.0, 'BOOKED', 9300.0);
            """
        )
        self.con.commit()

        model = HedonicPricingModel(n_estimators=10, max_depth=2, min_samples_split=2)
        model.train_from_db(self.con)

        # Test prediction and SHAP explanation
        test_unit = {"asset_class": "Commercial_Retail", "carpet_area_sqft": 750.0}
        test_proj = {"district": "Ahmedabad", "latitude": 23.02, "longitude": 72.50, "latest_form_one_progress_pct": 90.0, "velocity_ratio": 1.2, "total_projects_claimed": 10}
        feats = model.extract_features(test_unit, test_proj)

        exp = model.explain(feats)
        self.assertGreater(exp["predicted_rate_per_sqft"], 5000.0)
        self.assertTrue(exp["efficiency_check_passed"])
        self.assertAlmostEqual(
            exp["base_market_average_inr"] + sum(exp["shap_values"].values()),
            exp["predicted_rate_per_sqft"],
            delta=0.05,
        )

    def test_completion_delay_survival_model(self):
        from real_estate_intelligence.analytics.survival import CompletionDelaySurvivalModel

        self.con.executescript(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, start_date, completion_date, latest_form_one_progress_pct, velocity_ratio, estimated_cost_inr, incurred_cost_inr, complaints_count, default_quarters_count, bu_status)
            VALUES
                (910, 'FAST PROJ', 'REG910', 1, 'P1', '2023-01-01', '2025-01-01', 100.0, 1.5, 100000000.0, 100000000.0, 0, 0, 'Approved: A'),
                (911, 'MED PROJ', 'REG911', 2, 'P2', '2022-01-01', '2026-06-01', 95.0, 1.1, 100000000.0, 90000000.0, 0, 0, 'Approved: B'),
                (912, 'SLOW PROJ', 'REG912', 3, 'P3', '2021-01-01', '2027-01-01', 40.0, 0.6, 100000000.0, 30000000.0, 2, 1, 'Not Verified');
            """
        )
        self.con.commit()

        surv = CompletionDelaySurvivalModel()
        surv.train_from_db(self.con)

        c_idx = surv.calculate_concordance_index()
        self.assertGreaterEqual(c_idx, 0.5)

        # Forecast slow project
        fc = surv.forecast_project_by_id(self.con, 912)
        self.assertEqual(fc["project_id"], 912)
        self.assertIn("p50_median_expected_date", fc["forecasted_handover_dates"])
        self.assertIn(fc["delay_risk_label"], ["ON_TRACK", "MODERATE_DELAY", "HIGH_DELAY_RISK"])


if __name__ == "__main__":
    unittest.main()

