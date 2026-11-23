"""Discrepancy and statutory commitment audit engine."""

import re
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..models.schema import DiscrepancyLead


class ProjectAuditor:
    def __init__(self, con: sqlite3.Connection):
        self.con = con

    def check_bu_status(self, project_id: int) -> Dict[str, Any]:
        """Check whether project has received municipal Building Use (BU) permission / NOC.

        Uses project_summaries.has_bu_noc and noc_bu_records.bu_check rather than
        the unpopulated projects.bu_status column.
        """
        has_bu = False
        source = None
        cert_no = None

        # 1. Check project_summaries (populated statewide)
        srow = self.con.execute(
            "SELECT has_bu_noc, bu_certificate_no FROM project_summaries WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if srow and srow["has_bu_noc"] == 1:
            has_bu = True
            source = "project_summaries.has_bu_noc"
            cert_no = srow["bu_certificate_no"]

        # 2. Check noc_bu_records (46.9k rows statewide)
        if not has_bu:
            bu_row = self.con.execute(
                """
                SELECT bu_check, bu_date FROM noc_bu_records
                WHERE project_id = ? AND UPPER(COALESCE(bu_check, '')) = 'YES'
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            if bu_row:
                has_bu = True
                source = "noc_bu_records.bu_check"

        # 3. Fallback: projects.bu_status
        if not has_bu:
            prow = self.con.execute(
                "SELECT bu_status FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if prow and prow["bu_status"] and "Approved" in str(prow["bu_status"]):
                has_bu = True
                source = "projects.bu_status"

        return {
            "has_bu_noc": has_bu,
            "evidence_source": source,
            "bu_certificate_no": cert_no,
        }

    def get_cohort_flags(self, project_id: int) -> Dict[str, bool]:
        """Compute cohort and statutory entity classification flags for a project.

        Flags:
            is_legacy_grandfathered: scheduled_completion_year <= 2019 (pre-RERA full rollout).
            is_govt_authority: promoted/developed by VUDA, AUDA, SUDA, RUDA, GIDC, PMAY, or GHB.
        """
        prow = self.con.execute(
            "SELECT name, promoter_name, completion_date FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if not prow:
            return {"is_legacy_grandfathered": False, "is_govt_authority": False}

        is_legacy = False
        if prow["completion_date"]:
            try:
                comp_year = int(str(prow["completion_date"])[:4])
                if comp_year <= 2019:
                    is_legacy = True
            except (ValueError, TypeError):
                pass

        is_govt = False
        gov_pattern = re.compile(
            r"\b(VUDA|AUDA|SUDA|RUDA|GIDC|PMAY|GHB|GUJARAT HOUSING BOARD|URBAN DEVELOPMENT AUTHORITY)\b",
            re.IGNORECASE,
        )
        pname = str(prow["promoter_name"] or "")
        proj_name = str(prow["name"] or "")
        if gov_pattern.search(pname) or gov_pattern.search(proj_name):
            is_govt = True

        return {
            "is_legacy_grandfathered": is_legacy,
            "is_govt_authority": is_govt,
        }

    def audit_project(self, project_id: int, include_skipped: bool = False) -> List[DiscrepancyLead]:
        """Run deterministic audit checks for a project across statutory filings.

        Parameters:
            project_id: GujRERA project primary key.
            include_skipped: If True, explicitly report SKIPPED_UNINGESTED leads when
                             underlying tables have 0 rows for this project.
        """
        leads: List[DiscrepancyLead] = []

        # Fetch enriched project facts
        prow = self.con.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
        if not prow:
            return leads

        cohort = self.get_cohort_flags(project_id)
        is_legacy = cohort["is_legacy_grandfathered"]
        is_govt = cohort["is_govt_authority"]
        bu_info = self.check_bu_status(project_id)
        has_bu = bu_info["has_bu_noc"]

        # Check whether this is an uningested statewide cohort project
        is_statewide_unscraped = False
        try:
            total_projs = self.con.execute("SELECT COUNT(1) FROM projects").fetchone()[0]
            if total_projs > 1000:
                DEEP_AUDIT_IDS = {13560, 13705, 16104, 16562, 17255, 17830, 17855, 20523, 24508}
                if project_id not in DEEP_AUDIT_IDS:
                    is_statewide_unscraped = True
        except Exception:
            pass

        # 1. Financial Expenditure Drop / Cost Reversal
        fin_rows = self.con.execute(
            """
            SELECT filing_type, filing_date, estimated_cost, incurred_and_paid
            FROM finances WHERE project_id = ? ORDER BY id ASC
            """,
            (project_id,),
        ).fetchall()

        if len(fin_rows) >= 2:
            old_fin = fin_rows[0]
            new_fin = fin_rows[-1]
            old_inc = old_fin["incurred_and_paid"]
            new_inc = new_fin["incurred_and_paid"]
            if old_inc and new_inc and new_inc < old_inc:
                diff_cr = (old_inc - new_inc) / 10_000_000.0
                leads.append(
                    DiscrepancyLead(
                        project_id=project_id,
                        category="financial",
                        severity="HIGH",
                        title=f"Reported Incurred Cost Dropped by ₹{diff_cr:.2f} Cr Across Filings",
                        detail=(
                            f"In the filing dated {str(old_fin['filing_date'])[:10]}, incurred & paid cost was reported as "
                            f"₹{old_inc / 10_000_000:.2f} Cr. In the subsequent filing dated {str(new_fin['filing_date'])[:10]}, "
                            f"reported incurred cost decreased to ₹{new_inc / 10_000_000:.2f} Cr."
                        ),
                        evidence_source="Form 3 JSON (Filing 1 vs Filing 2)",
                        reconciliation_guidance=(
                            "Inspect signed Form 3 CA certificates in PDF archive. Check whether newer filing entered "
                            "current-year incremental spend or net withdrawal balance instead of cumulative incurred cost."
                        ),
                    )
                )
        elif len(fin_rows) == 0 and include_skipped:
            leads.append(
                DiscrepancyLead(
                    project_id=project_id,
                    category="financial",
                    severity="SKIPPED_UNINGESTED",
                    title="Form 3 Financial Filings Uningested (Cost Reversal Audit Skipped)",
                    detail=f"Table finances contains 0 rows for project {project_id} in current database.",
                    evidence_source="finances table (0 rows)",
                    reconciliation_guidance="Verify CA Form 3 filings manually in GujRERA portal.",
                )
            )

        # 2. Construction Velocity & Delay Risk Ratio
        vel_ratio = prow["velocity_ratio"]
        time_elapsed = prow["time_elapsed_pct"]
        engg_score = prow["engg_score_pct"]
        pr_status = prow["progress_status_label"]

        if vel_ratio is not None and time_elapsed and time_elapsed > 10.0:
            if vel_ratio < 0.75:
                leads.append(
                    DiscrepancyLead(
                        project_id=project_id,
                        category="schedule",
                        severity="HIGH",
                        title=f"Severe Construction Velocity Deficit: {vel_ratio:.2f}x (Lagging Schedule)",
                        detail=(
                            f"Project has consumed {time_elapsed:.1f}% of its total scheduled calendar duration, "
                            f"but engineer-certified physical progress is only {engg_score:.1f}% (Portal Status: {pr_status})."
                        ),
                        evidence_source="progress_reports endpoint (enggScore / timeLaps)",
                        reconciliation_guidance=(
                            "Review quarterly QPR progress curve in qpr_progress for multi-quarter stalls. "
                            "Assess whether developer can realistically finish before the registered completion deadline."
                        ),
                    )
                )
            elif vel_ratio < 0.90:
                leads.append(
                    DiscrepancyLead(
                        project_id=project_id,
                        category="schedule",
                        severity="MEDIUM",
                        title=f"Moderate Construction Velocity Deficit: {vel_ratio:.2f}x",
                        detail=(
                            f"{time_elapsed:.1f}% of scheduled time has elapsed, while certified physical progress is {engg_score:.1f}%."
                        ),
                        evidence_source="progress_reports endpoint",
                        reconciliation_guidance="Monitor next QPR filing to verify if monthly construction pace has accelerated.",
                    )
                )
        elif vel_ratio is None and include_skipped:
            leads.append(
                DiscrepancyLead(
                    project_id=project_id,
                    category="schedule",
                    severity="SKIPPED_UNINGESTED",
                    title="QPR Construction Velocity Data Uningested (Velocity Audit Skipped)",
                    detail=f"Quarterly engineering score and velocity ratio are unpopulated for project {project_id}.",
                    evidence_source="projects.velocity_ratio (NULL)",
                    reconciliation_guidance="Inspect quarterly QPR Form 1 / Form 2 filings in portal.",
                )
            )

        # 3. Escrow Account Liquidity Depletion
        escrow_rows = self.con.execute(
            """
            SELECT bank_name, closing_bal, deposit_amt, withdrawal_amt
            FROM banks WHERE project_id = ? AND account_type = 1
            """,
            (project_id,),
        ).fetchall()

        valid_balances = [
            float(r["closing_bal"]) for r in escrow_rows if r["closing_bal"] is not None
        ]

        if valid_balances:
            cl_bal = sum(valid_balances)
            bank_names = ", ".join(set(r["bank_name"] for r in escrow_rows if r["bank_name"]))
            if cl_bal < 50_000.0 and engg_score and engg_score < 90.0 and not is_govt:
                leads.append(
                    DiscrepancyLead(
                        project_id=project_id,
                        category="financial",
                        severity="HIGH",
                        title=f"Escrow 70% Liquidity Depleted: Closing Balance ₹{cl_bal:,.0f}",
                        detail=(
                            f"The 70% designated RERA retention escrow account at {bank_names} "
                            f"holds only ₹{cl_bal:,.0f} in closing liquidity, while {100.0 - engg_score:.1f}% of construction remains."
                        ),
                        evidence_source="banks endpoint (Account Type 1 / 70% Retention)",
                        reconciliation_guidance=(
                            "Compare outstanding buyer receivables against remaining civil liabilities. Ensure the developer "
                            "is not facing a liquidity squeeze that could stall site operations."
                        ),
                    )
                )
        elif not escrow_rows and include_skipped:
            leads.append(
                DiscrepancyLead(
                    project_id=project_id,
                    category="financial",
                    severity="SKIPPED_UNINGESTED",
                    title="Escrow Account Balances Uningested (Liquidity Audit Skipped)",
                    detail=f"Table banks holds 0 balance records for project {project_id}.",
                    evidence_source="banks table (0 rows)",
                    reconciliation_guidance="Request certified bank statement for designated RERA account.",
                )
            )

        # 3b. Statutory Section 4(2)(l)(D) Escrow Over-Withdrawal Audit
        # Statutory Rule: Allowed cumulative withdrawal from 70% retention account cannot exceed
        # eligible incurred costs. Land cost is eligible 100% upfront (baseline 35% of total cost)
        # and civil construction cost is eligible in proportion to physical completion percentage.
        if escrow_rows and fin_rows:
            tot_withdrawn = sum(float(r["withdrawal_amt"] or 0.0) for r in escrow_rows)
            tot_deposited = sum(float(r["deposit_amt"] or 0.0) for r in escrow_rows)
            est_cost = float(fin_rows[-1]["estimated_cost"] or prow["estimated_cost_inr"] or 0.0)
            progress_pct = float(engg_score or prow["latest_form_one_progress_pct"] or 0.0)

            if est_cost > 0 and progress_pct > 0 and tot_withdrawn > 0 and not is_govt:
                # Land cost is eligible 100% upfront (statutory baseline 35% of total estimated cost)
                land_cost_ratio = 0.35
                civil_progress_share = (1.0 - land_cost_ratio) * (progress_pct / 100.0)
                eligible_fraction = land_cost_ratio + civil_progress_share

                if tot_deposited > 0:
                    allowed_withdrawal = tot_deposited * min(1.0, eligible_fraction)
                else:
                    allowed_withdrawal = est_cost * min(1.0, eligible_fraction)

                if tot_withdrawn > allowed_withdrawal * 1.05:  # 5% buffer for interest / bank fees
                    excess_cr = (tot_withdrawn - allowed_withdrawal) / 10_000_000.0
                    bank_names = ", ".join(set(r["bank_name"] for r in escrow_rows if r["bank_name"]))
                    leads.append(
                        DiscrepancyLead(
                            project_id=project_id,
                            category="financial",
                            severity="CRITICAL",
                            title=f"Statutory 70% Escrow Over-Withdrawal: Excess ₹{excess_cr:.2f} Cr Withdrawn Ahead of Progress",
                            detail=(
                                f"Under RERA Section 4(2)(l)(D), cumulative withdrawals from the 70% Designated Retention Escrow "
                                f"account at {bank_names} (reported as ₹{tot_withdrawn / 10_000_000:.2f} Cr) cannot exceed the certified "
                                f"eligible progress share (₹{allowed_withdrawal / 10_000_000:.2f} Cr based on {progress_pct:.1f}% civil progress "
                                f"and an estimated baseline heuristic of 35% land cost allocation, not a verified filing figure). "
                                f"Excess uncertified funds withdrawn: ₹{excess_cr:.2f} Cr."
                            ),
                            evidence_source="banks (Account Type 1 withdrawal_amt) vs Form 1 Progress % x Estimated Baseline Heuristic (35% Land Cost)",
                            reconciliation_guidance=(
                                "Audit signed Form 3 CA withdrawal certificates and Form 1 architect certificates. "
                                "Verify whether excess withdrawals were utilized for unauthorized non-project expenditures or land purchase."
                            ),
                        )
                    )
        elif (not escrow_rows or not fin_rows) and include_skipped:
            leads.append(
                DiscrepancyLead(
                    project_id=project_id,
                    category="financial",
                    severity="SKIPPED_UNINGESTED",
                    title="Section 4(2)(l)(D) Escrow Audit Skipped (Finances or Escrow Uningested)",
                    detail=f"Financial or escrow filings are unpopulated for project {project_id}.",
                    evidence_source="finances / banks (0 rows)",
                    reconciliation_guidance="Obtain certified Form 3 CA withdrawal certificates and bank statements.",
                )
            )

        # 4. Registered Completion Date Expired Without Form 4 or BU NOC
        if prow["completion_date"]:
            comp_date_str = str(prow["completion_date"])[:10]
            form4_row = self.con.execute(
                "SELECT COUNT(*) FROM documents_catalog WHERE project_id = ? AND doc_type = 'form_four_completion'",
                (project_id,),
            ).fetchone()[0]

            # Project is completed and occupied if municipal BU NOC is on record
            if comp_date_str < "2026-10-15" and not has_bu and form4_row == 0:
                detail_note = ""
                if is_legacy:
                    detail_note = " (Note: Grandfathered legacy scheme with scheduled completion <= 2019)."
                elif is_govt:
                    detail_note = " (Note: Public/governmental authority development scheme)."

                leads.append(
                    DiscrepancyLead(
                        project_id=project_id,
                        category="schedule",
                        severity="LOW" if (is_legacy or is_govt) else "HIGH",
                        title="Registered Completion Date Expired Without Form 4 or BU NOC",
                        detail=(
                            f"The project's statutory completion deadline was {comp_date_str}, which has passed. "
                            f"No Form 4 Architect Completion Certificate or Municipal BU NOC has been recorded.{detail_note}"
                        ),
                        evidence_source="projects (completion_date) vs project_summaries.has_bu_noc & noc_bu_records",
                        reconciliation_guidance=(
                            "Verify if promoter filed an extension application (Section 6) or if municipal BU NOC was issued under local authority. "
                            "Inspect whether allottees were granted delay interest compensation."
                        ),
                    )
                )

        # 5. Active Consumer Complaints
        complaint_cnt = prow["complaints_count"] or 0
        if complaint_cnt > 0:
            leads.append(
                DiscrepancyLead(
                    project_id=project_id,
                    category="regulatory",
                    severity="HIGH" if complaint_cnt >= 2 else "MEDIUM",
                    title=f"{complaint_cnt} Consumer Complaint Application(s) on Record",
                    detail=f"GujRERA regulatory records show {complaint_cnt} complaint application(s) filed under Section 31.",
                    evidence_source="all_applications endpoint",
                    reconciliation_guidance=(
                        "Search GujRERA order database to determine whether orders or interim stays have been passed against the promoter."
                    ),
                )
            )

        # 6. Post-Registration Sanctioned Layout Alterations (Section 14)
        alt_cnt = prow["alterations_count"] or 0
        if alt_cnt > 0:
            leads.append(
                DiscrepancyLead(
                    project_id=project_id,
                    category="regulatory",
                    severity="MEDIUM",
                    title=f"{alt_cnt} Post-Registration Sanctioned Plan Alteration(s) Disclosed",
                    detail=(
                        f"Promoter submitted Section 14 alteration applications after launching the project. "
                        f"Sanctioned layouts, unit configurations, or common facilities were amended."
                    ),
                    evidence_source="all_applications endpoint (applicationType: Alteration)",
                    reconciliation_guidance=(
                        "Section 14 requires 2/3rd allottee consent for layout changes. Review the Alteration Application PDF "
                        "in the document archive to verify if unit dimensions or common areas were changed."
                    ),
                )
            )
        else:
            apps_cnt = self.con.execute(
                "SELECT COUNT(*) FROM applications WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
            if apps_cnt == 0 and include_skipped:
                leads.append(
                    DiscrepancyLead(
                        project_id=project_id,
                        category="regulatory",
                        severity="SKIPPED_UNINGESTED",
                        title="Section 14 Alteration Application Filings Uningested",
                        detail=f"Table applications contains 0 rows for project {project_id}.",
                        evidence_source="applications table (0 rows)",
                        reconciliation_guidance="Verify Section 14 layout alteration filings in portal archives.",
                    )
                )

        # 7. Missed Statutory Quarterly Returns (QPR Defaults)
        def_cnt = prow["default_quarters_count"] or 0
        if def_cnt > 0:
            leads.append(
                DiscrepancyLead(
                    project_id=project_id,
                    category="statutory",
                    severity="MEDIUM",
                    title=f"Defaulted on {def_cnt} Statutory Quarterly Return(s) (QPR Defaults)",
                    detail=(
                        f"Project has {def_cnt} quarterly filing(s) marked with isDefault = YES by GujRERA Authority."
                    ),
                    evidence_source="quarter_index endpoint (isDefault flag)",
                    reconciliation_guidance=(
                        "Check quarter_index for penalty orders or late fees assessed by GujRERA Authority."
                    ),
                )
            )
        else:
            qpr_cnt = self.con.execute(
                "SELECT COUNT(*) FROM quarterly_timeline WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
            if qpr_cnt == 0 and prow["default_quarters_count"] is None and include_skipped:
                leads.append(
                    DiscrepancyLead(
                        project_id=project_id,
                        category="statutory",
                        severity="SKIPPED_UNINGESTED",
                        title="Quarterly Timeline Filings Uningested (QPR Defaults Audit Skipped)",
                        detail=f"Quarterly filing index holds 0 records for project {project_id}.",
                        evidence_source="quarterly_timeline table (0 rows)",
                        reconciliation_guidance="Check GujRERA portal for quarterly return defaults.",
                    )
                )

        # 8. Overdue Form 5 CA Annual Audits
        pending_f5 = self.con.execute(
            """
            SELECT financial_year FROM form5_compliance
            WHERE project_id = ? AND status = 'ACTIVE' AND financial_year IN ('2022-23', '2023-24', '2024-25')
            ORDER BY financial_year ASC
            """,
            (project_id,),
        ).fetchall()

        if pending_f5:
            pending_yrs = ", ".join(r["financial_year"] for r in pending_f5)
            leads.append(
                DiscrepancyLead(
                    project_id=project_id,
                    category="statutory",
                    severity="MEDIUM",
                    title=f"Statutory Form 5 CA Annual Audit Pending for FY {pending_yrs}",
                    detail=(
                        f"Under Section 4(2)(l)(D), the promoter must upload an annual CA audit report within 6 months. "
                        f"Status remains ACTIVE (pending submission) for: {pending_yrs}."
                    ),
                    evidence_source="annual_compliance endpoint",
                    reconciliation_guidance="Request certified copies of annual audited accounts for the pending fiscal years.",
                )
            )
        else:
            f5_total = self.con.execute(
                "SELECT COUNT(*) FROM form5_compliance WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
            if f5_total == 0 and include_skipped:
                leads.append(
                    DiscrepancyLead(
                        project_id=project_id,
                        category="statutory",
                        severity="SKIPPED_UNINGESTED",
                        title="Form 5 CA Annual Compliance Filings Uningested",
                        detail=f"Table form5_compliance contains 0 rows for project {project_id}.",
                        evidence_source="form5_compliance table (0 rows)",
                        reconciliation_guidance="Obtain annual Form 5 CA certificates directly from developer or portal.",
                    )
                )

        # 9. Institutional Loans & Mortgages Disclosed
        loans_cnt = self.con.execute(
            "SELECT MAX(loan_rows_count) FROM finances WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] or 0

        if loans_cnt > 0:
            leads.append(
                DiscrepancyLead(
                    project_id=project_id,
                    category="statutory",
                    severity="INFO",
                    title=f"{loans_cnt} Institutional Loan Row(s) Disclosed in Form 3",
                    detail=(
                        f"Promoter disclosed {loans_cnt} loan facility row(s). Receivables and project land may be charged/mortgaged."
                    ),
                    evidence_source="latest_loan_details / Form 3 loanDtLList",
                    reconciliation_guidance=(
                        "Obtain Bank NOC for conveyance before final unit registration to confirm release of charge."
                    ),
                )
            )
        elif len(fin_rows) == 0 and include_skipped:
            leads.append(
                DiscrepancyLead(
                    project_id=project_id,
                    category="statutory",
                    severity="SKIPPED_UNINGESTED",
                    title="Form 3 Institutional Loan Disclosures Uningested",
                    detail=f"Form 3 financial loan disclosure records are unpopulated for project {project_id}.",
                    evidence_source="finances table (0 rows)",
                    reconciliation_guidance="Inspect physical Form 3 filings to confirm whether bank charges exist.",
                )
            )

        # 10. Statutory Professional Credentials & Signer Coverage Audit
        # Checks for linked signed Form 3 CA certificates in documents catalog,
        # and verifies architect and structural engineer statutory registrations.
        has_financial_activity = bool(
            (prow["incurred_cost_inr"] and prow["incurred_cost_inr"] > 0)
            or any(r["incurred_and_paid"] for r in fin_rows)
        )

        form3_count = self.con.execute(
            "SELECT COUNT(*) FROM documents_catalog WHERE project_id = ? AND doc_type = 'form_three_ca'",
            (project_id,),
        ).fetchone()[0]

        if has_financial_activity and form3_count == 0:
            inc_cr = float(prow["incurred_cost_inr"] or 0) / 10_000_000.0
            leads.append(
                DiscrepancyLead(
                    project_id=project_id,
                    category="statutory",
                    severity="HIGH",
                    title="No Linked Signed Form 3 CA Certificate in Statutory Document Catalog",
                    detail=(
                        f"Project has recorded financial activity and expenditures (reported incurred cost: ₹{inc_cr:.2f} Cr), "
                        "but no signed Form 3 Chartered Accountant certificate is on file in the statutory documents catalog."
                    ),
                    evidence_source="finances vs documents_catalog (doc_type='form_three_ca')",
                    reconciliation_guidance=(
                        "Under Section 4(2)(l)(D), all withdrawals from the designated 70% retention escrow account must be "
                        "certified by a practicing Chartered Accountant via Form 3. Verify whether signed Form 3 certificates "
                        "were filed under separate submissions or if withdrawals occurred without CA certification."
                    ),
                )
            )
        elif not has_financial_activity and form3_count == 0 and include_skipped:
            leads.append(
                DiscrepancyLead(
                    project_id=project_id,
                    category="statutory",
                    severity="SKIPPED_UNINGESTED",
                    title="Form 3 CA Certificate Documents Uningested",
                    detail=f"No Form 3 CA certificate PDF records exist in documents catalog for project {project_id}.",
                    evidence_source="documents_catalog table (doc_type='form_three_ca', 0 rows)",
                    reconciliation_guidance="Verify CA certificate documents in GujRERA portal.",
                )
            )

        prof_rows = self.con.execute(
            "SELECT role, name, firm_name, license_or_reg_no FROM professionals WHERE project_id = ?",
            (project_id,),
        ).fetchall()

        architects = [r for r in prof_rows if r["role"].lower() == "architect"]

        if not architects:
            if is_statewide_unscraped:
                # In statewide ingestion tier, architect data was never scraped statewide.
                # Avoid false-positive statutory breach allegation; report as SKIPPED_UNINGESTED if requested.
                if include_skipped:
                    leads.append(
                        DiscrepancyLead(
                            project_id=project_id,
                            category="statutory",
                            severity="SKIPPED_UNINGESTED",
                            title="Statutory Architect Filings Uningested (Statewide Lake Omission)",
                            detail="Statutory architect filings were not extracted statewide in current ingestion wave.",
                            evidence_source="professionals table (statewide tier)",
                            reconciliation_guidance="Verify physical Form 1 / application disclosures in GujRERA portal.",
                        )
                    )
            else:
                leads.append(
                    DiscrepancyLead(
                        project_id=project_id,
                        category="statutory",
                        severity="MEDIUM",
                        title="No Statutory Architect Assigned in Project Registration",
                        detail=(
                            "Project registration records do not contain a designated architect assignment. "
                            "Section 4 requires an architect to certify physical milestone percentage via Form 1."
                        ),
                        evidence_source="professionals table (role='architect')",
                        reconciliation_guidance=(
                            "Inspect Form 1 filings to confirm whether a licensed architect has certified milestone progress."
                        ),
                    )
                )
        else:
            for arch in architects:
                reg_no = arch["license_or_reg_no"]
                if not reg_no or not str(reg_no).strip():
                    leads.append(
                        DiscrepancyLead(
                            project_id=project_id,
                            category="statutory",
                            severity="MEDIUM",
                            title=f"Architect Registration Unverified: License Number Omitted for {arch['name']}",
                            detail=(
                                f"Architect '{arch['name']}' is assigned in project records without a Council of Architecture (CoA) "
                                "registration number in statutory disclosures."
                            ),
                            evidence_source=f"professionals table (architect: {arch['name']})",
                            reconciliation_guidance=(
                                "Cross-reference with Council of Architecture registry to confirm valid professional standing."
                            ),
                        )
                    )

        engineers = [r for r in prof_rows if r["role"].lower() == "engineer"]
        if not engineers:
            leads.append(
                DiscrepancyLead(
                    project_id=project_id,
                    category="statutory",
                    severity="MEDIUM",
                    title="No Statutory Engineer Assigned in Project Registration",
                    detail=(
                        "Project registration records do not contain a designated structural engineer assignment. "
                        "Section 4 requires an engineer to certify structural execution via Form 2."
                    ),
                    evidence_source="professionals table (role='engineer')",
                    reconciliation_guidance=(
                        "Inspect Form 2 filings to confirm whether a licensed structural engineer has certified structural progress."
                    ),
                )
            )
        else:
            for eng in engineers:
                reg_no = eng["license_or_reg_no"]
                if not reg_no or not str(reg_no).strip():
                    leads.append(
                        DiscrepancyLead(
                            project_id=project_id,
                            category="statutory",
                            severity="MEDIUM",
                            title=f"Engineer Registration Unverified: License Number Omitted for {eng['name']}",
                            detail=(
                                f"Engineer '{eng['name']}' is assigned in project records without a municipal or institutional "
                                "structural license number in statutory disclosures."
                            ),
                            evidence_source=f"professionals table (engineer: {eng['name']})",
                            reconciliation_guidance=(
                                "Confirm competent authority structural engineering license with municipal corporation or development authority."
                            ),
                        )
                    )

        return leads

    def audit_rule_coverage(self, project_id: int) -> Dict[str, Any]:
        """Audit statutory rule evaluation census and report triggered, clean, and skipped rules."""
        prow = self.con.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
        if not prow:
            return {"error": f"Project {project_id} not found"}

        cohort = self.get_cohort_flags(project_id)
        bu_info = self.check_bu_status(project_id)

        all_leads = self.audit_project(project_id, include_skipped=True)
        active_leads = [l for l in all_leads if l.severity != "SKIPPED_UNINGESTED"]
        skipped_leads = [l for l in all_leads if l.severity == "SKIPPED_UNINGESTED"]

        return {
            "project_id": project_id,
            "is_legacy_grandfathered": cohort["is_legacy_grandfathered"],
            "is_govt_authority": cohort["is_govt_authority"],
            "has_bu_noc": bu_info["has_bu_noc"],
            "bu_evidence_source": bu_info["evidence_source"],
            "total_active_leads": len(active_leads),
            "total_skipped_rules": len(skipped_leads),
            "leads": active_leads,
            "skipped_rules": skipped_leads,
        }

    def audit_credential_coverage(self, project_id: int) -> Dict[str, Any]:
        """Audit statutory signer and professional credential coverage matrix for a project."""
        prow = self.con.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
        if not prow:
            return {"error": f"Project {project_id} not found"}

        prof_rows = self.con.execute(
            "SELECT role, name, firm_name, license_or_reg_no FROM professionals WHERE project_id = ?",
            (project_id,),
        ).fetchall()

        f3_docs = self.con.execute(
            "SELECT uid_hash, doc_type, sha256, status FROM documents_catalog WHERE project_id = ? AND doc_type = 'form_three_ca'",
            (project_id,),
        ).fetchall()

        fin_rows = self.con.execute(
            "SELECT incurred_and_paid FROM finances WHERE project_id = ?",
            (project_id,),
        ).fetchall()

        has_financial_activity = bool(
            (prow["incurred_cost_inr"] and prow["incurred_cost_inr"] > 0)
            or any(r["incurred_and_paid"] for r in fin_rows)
        )

        architects = [r for r in prof_rows if r["role"].lower() == "architect"]
        engineers = [r for r in prof_rows if r["role"].lower() == "engineer"]

        arch_verified = [r for r in architects if r["license_or_reg_no"] and str(r["license_or_reg_no"]).strip()]
        eng_verified = [r for r in engineers if r["license_or_reg_no"] and str(r["license_or_reg_no"]).strip()]
        f3_verified = [d for d in f3_docs if d["sha256"]]

        gap_codes = []
        is_statewide_unscraped = False
        try:
            total_projs = self.con.execute("SELECT COUNT(1) FROM projects").fetchone()[0]
            if total_projs > 1000:
                DEEP_AUDIT_IDS = {13560, 13705, 16104, 16562, 17255, 17830, 17855, 20523, 24508}
                if project_id not in DEEP_AUDIT_IDS:
                    is_statewide_unscraped = True
        except Exception:
            pass

        if not architects:
            if not is_statewide_unscraped:
                gap_codes.append("registration_architect_profile_unassigned")
            else:
                gap_codes.append("registration_architect_profile_uningested")
        elif len(arch_verified) == 0:
            gap_codes.append("registration_architect_profile_unverified")
        elif len(arch_verified) < len(architects):
            gap_codes.append("architect_has_unresolved_observations")

        if not engineers:
            gap_codes.append("registration_engineer_profile_unassigned")
        elif len(eng_verified) == 0:
            gap_codes.append("registration_engineer_profile_unverified")
        elif len(eng_verified) < len(engineers):
            gap_codes.append("engineer_has_unresolved_observations")

        if has_financial_activity and not f3_docs:
            gap_codes.append("no_linked_signed_form_three_certificate_in_archive")

        return {
            "project_id": project_id,
            "has_financial_activity": has_financial_activity,
            "roles": {
                "architect": {
                    "observed_count": len(architects),
                    "verified_count": len(arch_verified),
                    "records": [
                        {"name": a["name"], "firm": a["firm_name"], "license": a["license_or_reg_no"]}
                        for a in architects
                    ],
                },
                "engineer": {
                    "observed_count": len(engineers),
                    "verified_count": len(eng_verified),
                    "records": [
                        {"name": e["name"], "firm": e["firm_name"], "license": e["license_or_reg_no"]}
                        for e in engineers
                    ],
                },
                "ca_certificate": {
                    "observed_count": len(f3_docs),
                    "verified_count": len(f3_verified),
                    "document_hashes": [d["sha256"] for d in f3_docs if d["sha256"]],
                },
            },
            "gap_codes": gap_codes,
        }

    def calculate_escrow_runway(self, project_id: int) -> dict:
        """Calculate quarterly construction spend velocity and estimated escrow cash runway in months."""
        prow = self.con.execute(
            "SELECT estimated_cost_inr, incurred_cost_inr, engg_score_pct FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if not prow:
            return {"error": f"Project {project_id} not found"}

        escrow_rows = self.con.execute(
            "SELECT closing_bal FROM banks WHERE project_id = ? AND account_type = 1",
            (project_id,),
        ).fetchall()
        closing_bal = max([float(r["closing_bal"] or 0.0) for r in escrow_rows] or [0.0])

        est_cost = float(prow["estimated_cost_inr"] or 0.0)
        inc_cost = float(prow["incurred_cost_inr"] or 0.0)
        rem_cost = max(0.0, est_cost - inc_cost)

        # Look at historical finances
        fin_rows = self.con.execute(
            "SELECT filing_date, incurred_and_paid FROM finances WHERE project_id = ? AND incurred_and_paid IS NOT NULL ORDER BY id ASC",
            (project_id,),
        ).fetchall()

        monthly_burn = 0.0
        if len(fin_rows) >= 2:
            f1, f2 = fin_rows[0], fin_rows[-1]
            c1 = float(f1["incurred_and_paid"] or 0.0)
            c2 = float(f2["incurred_and_paid"] or 0.0)
            diff_cost = c2 - c1
            monthly_burn = max(0.0, diff_cost / 3.0) if diff_cost > 0 else 0.0
        elif inc_cost > 0:
            monthly_burn = inc_cost / 12.0

        runway_months = None
        if monthly_burn > 0:
            runway_months = round(closing_bal / monthly_burn, 1)
        elif closing_bal > 0 and rem_cost == 0:
            runway_months = 999.0

        engg_pct = float(prow["engg_score_pct"] or 0.0)
        if runway_months is not None and runway_months < 3.0 and engg_pct < 95.0:
            risk = "CRITICAL"
        elif runway_months is not None and runway_months < 6.0:
            risk = "MODERATE"
        else:
            risk = "LOW"

        return {
            "project_id": project_id,
            "closing_escrow_balance_inr": closing_bal,
            "monthly_construction_burn_inr": round(monthly_burn, 2),
            "estimated_runway_months": runway_months,
            "remaining_construction_cost_inr": rem_cost,
            "insolvency_risk": risk,
        }
