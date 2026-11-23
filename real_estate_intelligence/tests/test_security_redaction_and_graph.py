"""Unit tests for PII Redaction, Turso Sync sanitization, and Knowledge Graph Composite Linkage."""

import json
import sqlite3
import unittest
from typing import Dict, Any

from real_estate_intelligence.db.database import init_schema
from real_estate_intelligence.db.queries import get_project_detail, get_graph_data
from real_estate_intelligence.db.redaction import (
    is_whitelisted,
    mask_bank_account,
    redact_payload,
    redact_record,
    redact_value,
)
from real_estate_intelligence.graph.network import (
    KnowledgeGraph,
    resolve_promoter_portfolio,
    _enforce_token_cap_list,
    MAX_GRAPH_TOKENS,
)


class TestSecurityRedactionAndGraph(unittest.TestCase):
    def setUp(self):
        # In-memory SQLite for complete isolation - never touches production data
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        init_schema(self.con)

    def tearDown(self):
        self.con.close()

    def test_pii_redaction_pan(self):
        # Synthetic dummy PANs
        dummy_pan = "ABCDE1234F"
        dummy_pan_st = "XYZAB5678CST001"
        self.assertEqual(redact_value("license_or_reg_no", dummy_pan), "[REDACTED-PAN]")
        self.assertEqual(redact_value("license_or_reg_no", dummy_pan_st), "[REDACTED-PAN]")
        self.assertEqual(
            redact_value("remarks", f"Verified PAN {dummy_pan} for director"),
            "Verified PAN [REDACTED-PAN] for director",
        )

    def test_pii_redaction_email(self):
        # Synthetic dummy emails
        dummy_email = "engineer.dummy@example.com"
        dummy_yahoo = "architect_test123@mockmail.org"
        self.assertEqual(redact_value("email", dummy_email), "[REDACTED-EMAIL]")
        self.assertEqual(redact_value("license_or_reg_no", dummy_yahoo), "[REDACTED-EMAIL]")
        self.assertEqual(
            redact_value("name", f"Test Engineer {dummy_email}"),
            "Test Engineer [REDACTED-EMAIL]",
        )

    def test_pii_redaction_aadhaar_id(self):
        # Synthetic dummy 12-digit national IDs
        dummy_id_spaced = "9876 5432 1098"
        dummy_id_continuous = "987654321098"
        self.assertEqual(redact_value("detail", f"Aadhaar: {dummy_id_spaced}"), "Aadhaar: [REDACTED-ID]")
        self.assertEqual(redact_value("snippet", f"National ID {dummy_id_continuous}"), "National ID [REDACTED-ID]")

    def test_pii_redaction_bank_account(self):
        # Synthetic dummy bank account
        dummy_acct = "123456789012"
        self.assertEqual(redact_value("account_no", dummy_acct), "****9012")
        self.assertEqual(redact_value("bank_account", int(dummy_acct)), "****9012")
        self.assertEqual(redact_value("account_number_masked", "****6485"), "****6485")
        self.assertEqual(
            redact_value("remarks", "Disbursed to A/C: 987654321"),
            "Disbursed to A/C: ****4321",
        )

    def test_statutory_license_whitelists(self):
        # GujRERA and CoA licenses must NEVER be redacted
        rera_reg = "PR/GJ/AHMEDABAD/AHMEDABAD CITY/AUDA/MAA09044/160921"
        coa_lic = "CA/2012/12345"
        coa_short = "CA/99/54321"

        self.assertTrue(is_whitelisted(rera_reg))
        self.assertTrue(is_whitelisted(coa_lic))
        self.assertTrue(is_whitelisted(coa_short))

        self.assertEqual(redact_value("registration_number", rera_reg), rera_reg)
        self.assertEqual(redact_value("license_or_reg_no", coa_lic), coa_lic)
        self.assertEqual(redact_value("license_or_reg_no", coa_short), coa_short)

    def test_redact_record_and_payload_recursive(self):
        payload = {
            "project_id": 1001,
            "name": "TEST HARBOR",
            "registration_number": "PR/GJ/SURAT/123",
            "professionals": [
                {"role": "architect", "name": "Test Architect", "license_or_reg_no": "CA/2015/99999"},
                {"role": "engineer", "name": "Fake Name", "license_or_reg_no": "ABCDE1234F"},
                {"role": "engineer", "name": "Eng test@example.com", "license_or_reg_no": "engineer@mock.com"},
            ],
            "banks": [
                {"bank_name": "Test Bank", "account_no": "555566667777"}
            ],
            "detail": "Director Aadhaar is 1234 5678 9012",
        }
        redacted = redact_payload(payload)

        # Non-sensitive keys intact
        self.assertEqual(redacted["project_id"], 1001)
        self.assertEqual(redacted["name"], "TEST HARBOR")
        self.assertEqual(redacted["registration_number"], "PR/GJ/SURAT/123")

        # Whitelisted CoA intact
        self.assertEqual(redacted["professionals"][0]["license_or_reg_no"], "CA/2015/99999")

        # PAN redacted
        self.assertEqual(redacted["professionals"][1]["license_or_reg_no"], "[REDACTED-PAN]")

        # Emails redacted
        self.assertEqual(redacted["professionals"][2]["name"], "Eng [REDACTED-EMAIL]")
        self.assertEqual(redacted["professionals"][2]["license_or_reg_no"], "[REDACTED-EMAIL]")

        # Bank account masked
        self.assertEqual(redacted["banks"][0]["account_no"], "****7777")

        # Detail Aadhaar redacted
        self.assertEqual(redacted["detail"], "Director Aadhaar is [REDACTED-ID]")

    def test_queries_read_paths_redact_pii(self):
        # Insert a project with sensitive professional and bank data
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, district)
            VALUES (5001, 'SECURE HEIGHTS', 'REG5001', 101, 'ALPHA DEV', 'Ahmedabad')
            """
        )
        self.con.execute(
            """
            INSERT INTO professionals (project_id, role, name, firm_name, license_or_reg_no)
            VALUES (5001, 'engineer', 'Er. John Doe john.doe@mock.com', 'Doe Engineering', 'ABCDE1234F')
            """
        )
        self.con.execute(
            """
            INSERT INTO banks (project_id, bank_name, branch_name, account_type, account_name, account_number_masked)
            VALUES (5001, 'HDFC BANK', 'Bodakdev', 1, 'ALPHA ESCROW', '998877665544')
            """
        )
        self.con.commit()

        detail = get_project_detail(self.con, 5001)
        self.assertIsNotNone(detail)

        # Check professionals redacted in get_project_detail
        prof = detail["professionals"][0]
        self.assertIn("[REDACTED-EMAIL]", prof["name"])
        self.assertEqual(prof["license_or_reg_no"], "[REDACTED-PAN]")

        # Check bank account masked in get_project_detail
        bank = detail["banks"][0]
        self.assertEqual(bank["account_number_masked"], "****5544")

    def test_knowledge_graph_composite_key_no_promoter_none(self):
        # Project without promoter_id (NULL)
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, district)
            VALUES (6001, 'LOTUS GREENS', 'REG6001', NULL, 'LOTUS INFRACON', 'Ahmedabad')
            """
        )
        self.con.execute(
            """
            INSERT INTO professionals (project_id, role, name, license_or_reg_no)
            VALUES (6001, 'engineer', 'Er. Shah', 'AUDA/ENG/101')
            """
        )
        self.con.commit()

        kg = KnowledgeGraph(self.con)
        kg.build_graph()

        # Check that NO node or edge exists with 'promoter:None'
        cur = self.con.cursor()
        none_nodes = cur.execute("SELECT node_id FROM graph_nodes WHERE node_id LIKE 'promoter:None%'").fetchall()
        none_edges = cur.execute("SELECT src_id, dst_id FROM graph_edges WHERE dst_id LIKE 'promoter:None%' OR src_id LIKE 'promoter:None%'").fetchall()
        self.assertEqual(len(none_nodes), 0, "Found forbidden promoter:None nodes")
        self.assertEqual(len(none_edges), 0, "Found forbidden promoter:None edges")

        # Check composite key promoter node was created
        comp_edges = cur.execute(
            "SELECT dst_id FROM graph_edges WHERE src_id = 'project:6001' AND relation = 'DEVELOPED_BY'"
        ).fetchall()
        self.assertEqual(len(comp_edges), 1)
        self.assertTrue(comp_edges[0][0].startswith("promoter:comp:LOTUS_INFRACON"))

    def test_query_time_ignores_legacy_promoter_none(self):
        kg = KnowledgeGraph(self.con)
        # Manually seed a legacy corrupted promoter:None edge
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, district)
            VALUES (7001, 'PROJECT ONE', 'REG7001', 'Ahmedabad');
            """
        )
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, district)
            VALUES (7002, 'PROJECT TWO', 'REG7002', 'Vadodara');
            """
        )
        self.con.execute("INSERT OR REPLACE INTO graph_nodes (node_id, kind, label) VALUES ('promoter:None', 'Promoter', 'None')")
        self.con.execute("INSERT OR REPLACE INTO graph_edges (src_id, relation, dst_id) VALUES ('project:7001', 'DEVELOPED_BY', 'promoter:None')")
        self.con.execute("INSERT OR REPLACE INTO graph_edges (src_id, relation, dst_id) VALUES ('project:7002', 'DEVELOPED_BY', 'promoter:None')")
        self.con.commit()

        kg = KnowledgeGraph(self.con)
        # find_shared_entities must ignore the promoter:None cross-connection
        shared = kg.find_shared_entities(7001)
        self.assertEqual(len(shared), 0, "Query time failed to ignore legacy promoter:None edge")

        # get_ego_network must ignore promoter:None
        ego = kg.get_ego_network(7001)
        node_ids = {n["id"] for n in ego["nodes"]}
        self.assertNotIn("promoter:None", node_ids)

    def test_resolve_promoter_portfolio_homonym_warning(self):
        # Insert projects with common Gujarat brand prefix
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_name, district, completion_date)
            VALUES (8001, 'SHREEJI HEIGHTS', 'REG8001', 'SHREEJI ASSOCIATES', 'Ahmedabad', '2024-12-31')
            """
        )
        self.con.execute(
            """
            INSERT INTO project_summaries (project_id, name, registration_number, promoter_name, district, completion_date, has_bu_noc, tier)
            VALUES (8001, 'SHREEJI HEIGHTS', 'REG8001', 'SHREEJI ASSOCIATES', 'Ahmedabad', '2024-12-31', 0, 'TIER_1')
            """
        )
        self.con.commit()

        res = resolve_promoter_portfolio(self.con, promoter_name="SHREEJI ASSOCIATES")
        self.assertTrue(res["homonym_warning"])
        self.assertIn("common Gujarat brand prefix", res["warning_message"])
        self.assertEqual(res["portfolio_count"], 1)

    def test_resolve_promoter_portfolio_modern_expired_no_bu(self):
        # Project 1: Modern expired no BU (completion 2022, has_bu_noc=0) -> Should count
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_name, district, completion_date)
            VALUES (9001, 'TEST TOWERS 1', 'REG9001', 'MEGA DEVELOPERS', 'Ahmedabad', '2022-06-30')
            """
        )
        self.con.execute(
            """
            INSERT INTO project_summaries (project_id, name, registration_number, promoter_name, district, completion_date, has_bu_noc, tier)
            VALUES (9001, 'TEST TOWERS 1', 'REG9001', 'MEGA DEVELOPERS', 'Ahmedabad', '2022-06-30', 0, 'TIER_1')
            """
        )

        # Project 2: Pre-2020 grandfathered (completion 2018) -> Excluded from modern expired count
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_name, district, completion_date)
            VALUES (9002, 'TEST TOWERS 2', 'REG9002', 'MEGA DEVELOPERS', 'Ahmedabad', '2018-06-30')
            """
        )
        self.con.execute(
            """
            INSERT INTO project_summaries (project_id, name, registration_number, promoter_name, district, completion_date, has_bu_noc, tier)
            VALUES (9002, 'TEST TOWERS 2', 'REG9002', 'MEGA DEVELOPERS', 'Ahmedabad', '2018-06-30', 0, 'TIER_1')
            """
        )

        # Project 3: Has BU permission (has_bu_noc=1) -> Excluded
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_name, district, completion_date)
            VALUES (9003, 'TEST TOWERS 3', 'REG9003', 'MEGA DEVELOPERS', 'Ahmedabad', '2023-01-01')
            """
        )
        self.con.execute(
            """
            INSERT INTO project_summaries (project_id, name, registration_number, promoter_name, district, completion_date, has_bu_noc, tier)
            VALUES (9003, 'TEST TOWERS 3', 'REG9003', 'MEGA DEVELOPERS', 'Ahmedabad', '2023-01-01', 1, 'TIER_1')
            """
        )

        # Project 4: Govt authority scheme (AUDA) -> Excluded
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_name, district, completion_date)
            VALUES (9004, 'AUDA AFFORDABLE HOUSING', 'REG9004', 'AUDA', 'Ahmedabad', '2022-01-01')
            """
        )
        self.con.execute(
            """
            INSERT INTO project_summaries (project_id, name, registration_number, promoter_name, district, completion_date, has_bu_noc, tier)
            VALUES (9004, 'AUDA AFFORDABLE HOUSING', 'REG9004', 'AUDA', 'Ahmedabad', '2022-01-01', 0, 'TIER_1')
            """
        )
        self.con.commit()

        res_mega = resolve_promoter_portfolio(self.con, promoter_name="MEGA DEVELOPERS")
        self.assertEqual(res_mega["portfolio_count"], 3)
        self.assertEqual(res_mega["modern_expired_no_bu_count"], 1)

        res_auda = resolve_promoter_portfolio(self.con, promoter_name="AUDA")
        self.assertEqual(res_auda["modern_expired_no_bu_count"], 0)

    def test_token_cap_enforcement(self):
        # Create a large list of 500 items that would exceed 4,000 tokens (16,000 chars)
        large_items = [{"index": i, "description": "A" * 100} for i in range(500)]
        capped = _enforce_token_cap_list(large_items, max_tokens=100)
        self.assertTrue(capped.truncated)
        self.assertLessEqual(len(json.dumps(capped)) // 4, 100)


if __name__ == "__main__":
    unittest.main()
