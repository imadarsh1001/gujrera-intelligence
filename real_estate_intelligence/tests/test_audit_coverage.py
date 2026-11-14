"""Unit tests for professional credential and statutory signer coverage auditing."""

import sqlite3
import unittest

from real_estate_intelligence.analytics.audit import ProjectAuditor
from real_estate_intelligence.db.database import init_schema


class TestAuditCoverage(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        init_schema(self.con)
        self.auditor = ProjectAuditor(self.con)

    def tearDown(self):
        self.con.close()

    def test_fully_verified_project_no_leads(self):
        """A project with verified architect, engineer, and signed Form 3 CA produces zero credential gap leads."""
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, incurred_cost_inr)
            VALUES (101, 'PRIME TOWERS', 'REG101', 1, 'ALPHA DEV', 50000000.0)
            """
        )
        self.con.execute(
            """
            INSERT INTO professionals (project_id, role, name, firm_name, license_or_reg_no)
            VALUES (101, 'architect', 'Arch. Sunita Patel', 'Patel Architects', 'CA/2012/12345')
            """
        )
        self.con.execute(
            """
            INSERT INTO professionals (project_id, role, name, firm_name, license_or_reg_no)
            VALUES (101, 'engineer', 'Eng. Rajesh Shah', 'Shah Structural', 'AUDA/SD-I/276')
            """
        )
        self.con.execute(
            """
            INSERT INTO documents_catalog (uid_hash, project_id, doc_type, file_path, raw_bytes, sha256, status)
            VALUES ('hash_f3_101', 101, 'form_three_ca', 'docs/f3_101.pdf', 10240, 'sha256_mock_f3', 'ok')
            """
        )
        self.con.commit()

        leads = self.auditor.audit_project(101)
        cred_leads = [
            l for l in leads
            if "Architect" in l.title or "Engineer" in l.title or "Form 3 CA" in l.title
        ]
        self.assertEqual(len(cred_leads), 0)

        cov = self.auditor.audit_credential_coverage(101)
        self.assertEqual(cov["project_id"], 101)
        self.assertEqual(cov["roles"]["architect"]["observed_count"], 1)
        self.assertEqual(cov["roles"]["architect"]["verified_count"], 1)
        self.assertEqual(cov["roles"]["engineer"]["observed_count"], 1)
        self.assertEqual(cov["roles"]["engineer"]["verified_count"], 1)
        self.assertEqual(cov["roles"]["ca_certificate"]["observed_count"], 1)
        self.assertEqual(cov["gap_codes"], [])

    def test_unassigned_architect_lead(self):
        """Project with no architect registration record emits a statutory lead."""
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name)
            VALUES (102, 'SOLO TOWER', 'REG102', 1, 'ALPHA DEV')
            """
        )
        self.con.commit()

        leads = self.auditor.audit_project(102)
        arch_leads = [l for l in leads if "No Statutory Architect Assigned" in l.title]
        self.assertEqual(len(arch_leads), 1)
        self.assertEqual(arch_leads[0].severity, "MEDIUM")
        self.assertEqual(arch_leads[0].category, "statutory")

        cov = self.auditor.audit_credential_coverage(102)
        self.assertIn("registration_architect_profile_unassigned", cov["gap_codes"])

    def test_unverified_architect_license_lead(self):
        """Project with architect assigned but license/registration number omitted emits unverified lead."""
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name)
            VALUES (103, 'SKYDECK', 'REG103', 1, 'ALPHA DEV')
            """
        )
        self.con.execute(
            """
            INSERT INTO professionals (project_id, role, name, firm_name, license_or_reg_no)
            VALUES (103, 'architect', 'Cunal Parmar', 'FLXBL', NULL)
            """
        )
        self.con.commit()

        leads = self.auditor.audit_project(103)
        arch_leads = [l for l in leads if "Architect Registration Unverified" in l.title]
        self.assertEqual(len(arch_leads), 1)
        self.assertEqual(arch_leads[0].severity, "MEDIUM")
        self.assertIn("Cunal Parmar", arch_leads[0].title)

        cov = self.auditor.audit_credential_coverage(103)
        self.assertIn("registration_architect_profile_unverified", cov["gap_codes"])

    def test_unassigned_engineer_lead(self):
        """Project with no structural engineer assigned emits a statutory lead."""
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name)
            VALUES (104, 'CIVIL TOWER', 'REG104', 1, 'ALPHA DEV')
            """
        )
        self.con.commit()

        leads = self.auditor.audit_project(104)
        eng_leads = [l for l in leads if "No Statutory Engineer Assigned" in l.title]
        self.assertEqual(len(eng_leads), 1)
        self.assertEqual(eng_leads[0].severity, "MEDIUM")
        self.assertEqual(eng_leads[0].category, "statutory")

        cov = self.auditor.audit_credential_coverage(104)
        self.assertIn("registration_engineer_profile_unassigned", cov["gap_codes"])

    def test_unverified_engineer_license_lead(self):
        """Project with structural engineer assigned but license omitted emits unverified lead."""
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name)
            VALUES (105, 'VISTA TOWER', 'REG105', 1, 'ALPHA DEV')
            """
        )
        self.con.execute(
            """
            INSERT INTO professionals (project_id, role, name, firm_name, license_or_reg_no)
            VALUES (105, 'engineer', 'Hardik Patel', 'Patel Engineering', '')
            """
        )
        self.con.commit()

        leads = self.auditor.audit_project(105)
        eng_leads = [l for l in leads if "Engineer Registration Unverified" in l.title]
        self.assertEqual(len(eng_leads), 1)
        self.assertEqual(eng_leads[0].severity, "MEDIUM")
        self.assertIn("Hardik Patel", eng_leads[0].title)

        cov = self.auditor.audit_credential_coverage(105)
        self.assertIn("registration_engineer_profile_unverified", cov["gap_codes"])

    def test_missing_form3_ca_certificate_with_expenditures(self):
        """Project with incurred expenditure but missing Form 3 CA certificate emits HIGH severity lead."""
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, incurred_cost_inr)
            VALUES (106, 'PROVINCE', 'REG106', 1, 'ALPHA DEV', 75000000.0)
            """
        )
        self.con.commit()

        leads = self.auditor.audit_project(106)
        f3_leads = [l for l in leads if "Form 3 CA Certificate" in l.title]
        self.assertEqual(len(f3_leads), 1)
        self.assertEqual(f3_leads[0].severity, "HIGH")
        self.assertEqual(f3_leads[0].category, "statutory")
        self.assertIn("₹7.50 Cr", f3_leads[0].detail)

        cov = self.auditor.audit_credential_coverage(106)
        self.assertIn("no_linked_signed_form_three_certificate_in_archive", cov["gap_codes"])

    def test_early_stage_project_no_false_positive_form3(self):
        """Newly registered project without incurred expenditure or finances does NOT emit false Form 3 lead."""
        self.con.execute(
            """
            INSERT INTO projects (project_id, name, registration_number, promoter_id, promoter_name, incurred_cost_inr)
            VALUES (107, 'FRESH LAUNCH', 'REG107', 1, 'ALPHA DEV', 0.0)
            """
        )
        self.con.commit()

        leads = self.auditor.audit_project(107)
        f3_leads = [l for l in leads if "Form 3 CA Certificate" in l.title]
        self.assertEqual(len(f3_leads), 0)

        cov = self.auditor.audit_credential_coverage(107)
        self.assertNotIn("no_linked_signed_form_three_certificate_in_archive", cov["gap_codes"])


if __name__ == "__main__":
    unittest.main()
