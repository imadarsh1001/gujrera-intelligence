"""Discrepancy and statutory commitment audit engine."""

import sqlite3
from datetime import datetime, timezone
from typing import List

from ..models.schema import DiscrepancyLead


class ProjectAuditor:
    def __init__(self, con: sqlite3.Connection):
        self.con = con

    def audit_project(self, project_id: int) -> List[DiscrepancyLead]:
        """Run deterministic audit checks for a project across statutory filings."""
        leads: List[DiscrepancyLead] = []

        # Fetch enriched project facts
        prow = self.con.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
        if not prow:
            return leads

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

        # 3. Escrow Account Liquidity Depletion
        escrow_acc = self.con.execute(
            """
            SELECT bank_name, closing_bal, deposit_amt, withdrawal_amt
            FROM banks WHERE project_id = ? AND account_type = 1
            """,
            (project_id,),
        ).fetchone()

        if escrow_acc:
            cl_bal = escrow_acc["closing_bal"]
            if cl_bal is not None and cl_bal < 50_000.0 and engg_score and engg_score < 90.0:
                leads.append(
                    DiscrepancyLead(
                        project_id=project_id,
                        category="financial",
                        severity="HIGH",
                        title=f"Escrow 70% Liquidity Depleted: Closing Balance ₹{cl_bal:,.0f}",
                        detail=(
                            f"The 70% designated RERA retention escrow account at {escrow_acc['bank_name']} "
                            f"holds only ₹{cl_bal:,.0f} in closing liquidity, while {100.0 - engg_score:.1f}% of construction remains."
                        ),
                        evidence_source="banks endpoint (Account Type 1 / 70% Retention)",
                        reconciliation_guidance=(
                            "Compare outstanding buyer receivables against remaining civil liabilities. Ensure the developer "
                            "is not facing a liquidity squeeze that could stall site operations."
                        ),
                    )
                )

        # 3b. Statutory Section 4(2)(l)(D) Escrow Over-Withdrawal Audit
        # Statutory Rule: Allowed cumulative withdrawal from 70% retention account cannot exceed
        # estimated total cost multiplied by certified physical completion percentage.
        # Source: Real Estate (Regulation and Development) Act 2016, Section 4(2)(l)(D) Proviso 1
        # https://mohua.gov.in/upload/uploadfiles/files/Real_Estate_Act_2016.pdf
        if escrow_acc and fin_rows:
            tot_withdrawn = float(escrow_acc["withdrawal_amt"] or 0.0)
            est_cost = float(fin_rows[-1]["estimated_cost"] or prow["estimated_cost_inr"] or 0.0)
            progress_pct = float(engg_score or prow["latest_form_one_progress_pct"] or 0.0)
            if est_cost > 0 and progress_pct > 0 and tot_withdrawn > 0:
                allowed_withdrawal = est_cost * (progress_pct / 100.0)
                if tot_withdrawn > allowed_withdrawal * 1.05:  # 5% buffer for interest / bank fees
                    excess_cr = (tot_withdrawn - allowed_withdrawal) / 10_000_000.0
                    leads.append(
                        DiscrepancyLead(
                            project_id=project_id,
                            category="financial",
                            severity="CRITICAL",
                            title=f"Statutory 70% Escrow Over-Withdrawal: Excess ₹{excess_cr:.2f} Cr Withdrawn Ahead of Progress",
                            detail=(
                                f"Under RERA Section 4(2)(l)(D), cumulative withdrawals from the 70% Designated Retention Escrow "
                                f"account (reported as ₹{tot_withdrawn / 10_000_000:.2f} Cr) cannot exceed the certified physical progress "
                                f"share of total estimated cost (₹{allowed_withdrawal / 10_000_000:.2f} Cr based on {progress_pct:.1f}% progress). "
                                f"Excess uncertified funds withdrawn: ₹{excess_cr:.2f} Cr."
                            ),
                            evidence_source="banks (Account Type 1 withdrawalAmt) vs Form 1 Progress % x Form 3 Estimated Cost",
                            reconciliation_guidance=(
                                "Audit signed Form 3 CA withdrawal certificates and Form 1 architect certificates. "
                                "Verify whether excess withdrawals were utilized for unauthorized non-project expenditures or land purchase."
                            ),
                        )
                    )

        # 4. Registered Completion Date Expired Without Form 4
        if prow["completion_date"]:
            comp_date_str = str(prow["completion_date"])[:10]
            form4_row = self.con.execute(
                "SELECT COUNT(*) FROM documents_catalog WHERE project_id = ? AND doc_type = 'form_four_completion'",
                (project_id,),
            ).fetchone()[0]

            now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if comp_date_str < "2026-10-15" and form4_row == 0:
                leads.append(
                    DiscrepancyLead(
                        project_id=project_id,
                        category="schedule",
                        severity="HIGH",
                        title="Registered Completion Date Expired Without Form 4 Completion Certificate",
                        detail=(
                            f"The project's statutory completion deadline was {comp_date_str}, which has passed. "
                            f"No Form 4 Architect Completion Certificate is on file."
                        ),
                        evidence_source="Project Details (completionDate) vs Form 4 Catalog",
                        reconciliation_guidance=(
                            "Verify if promoter filed an extension application (Section 6) or if construction was delayed. "
                            "Inspect whether allottees were granted delay interest compensation."
                        ),
                    )
                )

        # 5. Active Consumer Complaints
        complaint_cnt = prow["complaints_count"]
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
        alt_cnt = prow["alterations_count"]
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

        # 7. Missed Statutory Quarterly Returns (QPR Defaults)
        def_cnt = prow["default_quarters_count"]
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

        return leads

    def calculate_escrow_runway(self, project_id: int) -> dict:
        """Calculate quarterly construction spend velocity and estimated escrow cash runway in months."""
        prow = self.con.execute(
            "SELECT estimated_cost_inr, incurred_cost_inr, engg_score_pct FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if not prow:
            return {"error": f"Project {project_id} not found"}

        escrow_acc = self.con.execute(
            "SELECT closing_bal FROM banks WHERE project_id = ? AND account_type = 1",
            (project_id,),
        ).fetchone()
        closing_bal = float(escrow_acc["closing_bal"] or 0.0) if escrow_acc else 0.0

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
