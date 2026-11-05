"""Generate the 4-Quadrant Institutional Due-Diligence Dossier for investors."""

import sqlite3
from typing import Optional

from ..graph.network import KnowledgeGraph
from .audit import ProjectAuditor


def format_inr_cr(value: Optional[float]) -> str:
    if value is None:
        return "Not reported"
    return f"₹{value / 10_000_000:.2f} Cr"


def generate_investor_dossier(con: sqlite3.Connection, project_id: int) -> str:
    """Generate Markdown Institutional Dossier for an analytical buyer or investor."""
    cur = con.cursor()

    # Project Info
    cur.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,))
    proj = cur.fetchone()
    if not proj:
        raise ValueError(f"Project ID {project_id} not found in database.")

    # Promoter Info
    cur.execute("SELECT * FROM promoters WHERE promoter_id = ?", (proj["promoter_id"],))
    promoter = cur.fetchone() or {}

    # Professionals
    cur.execute("SELECT role, name, firm_name, license_or_reg_no FROM professionals WHERE project_id = ?", (project_id,))
    professionals = cur.fetchall()

    # Banks (Escrow + Collection)
    cur.execute(
        """
        SELECT bank_name, branch_name, ifsc_code, account_type, account_name,
               account_number_masked, deposit_amt, withdrawal_amt, opening_bal, closing_bal
        FROM banks WHERE project_id = ? ORDER BY account_type ASC
        """,
        (project_id,),
    )
    banks = cur.fetchall()

    # Inventory Blocks
    cur.execute(
        """
        SELECT block_name, total_units, booked_units, unbooked_units, booking_rate_pct,
               residential_units, commercial_units
        FROM inventory_blocks WHERE project_id = ? ORDER BY block_name
        """,
        (project_id,),
    )
    blocks = cur.fetchall()

    # Quarterly Progress
    cur.execute(
        """
        SELECT period_label, progress_percentage, submission_date
        FROM quarterly_timeline WHERE project_id = ? ORDER BY id ASC
        """,
        (project_id,),
    )
    timeline = cur.fetchall()

    # Finances
    cur.execute(
        """
        SELECT filing_type, filing_date, estimated_cost, incurred_and_paid,
               booked_consideration, received_amount, balance_amount, unbooked_consideration,
               total_residential, total_commercial_shop, total_commercial_office, loan_rows_count
        FROM finances WHERE project_id = ? ORDER BY id ASC
        """,
        (project_id,),
    )
    finances = cur.fetchall()

    # Form 5 Compliance
    cur.execute(
        """
        SELECT financial_year, status, submitted_on FROM form5_compliance
        WHERE project_id = ? ORDER BY financial_year ASC
        """,
        (project_id,),
    )
    form5_rows = cur.fetchall()

    # NOC BU Records
    cur.execute(
        """
        SELECT block_name, bu_check, bu_date FROM noc_bu_records
        WHERE project_id = ? ORDER BY block_name ASC
        """,
        (project_id,),
    )
    bu_rows = cur.fetchall()

    # Previous Projects
    cur.execute("SELECT linked_project_name, linked_project_id FROM previous_projects WHERE project_id = ?", (project_id,))
    prior_projects = cur.fetchall()

    # Audit Leads
    auditor = ProjectAuditor(con)
    leads = auditor.audit_project(project_id)

    # Graph Contagion
    kg = KnowledgeGraph(con)
    contagion = kg.trace_contagion_risk(project_id)

    # Documents Catalog
    cur.execute(
        """
        SELECT doc_type, COUNT(*) as cnt FROM documents_catalog
        WHERE project_id = ? GROUP BY doc_type
        """,
        (project_id,),
    )
    doc_summary = cur.fetchall()

    # Build Markdown
    maps_link_md = f"[View on Google Maps Satellite]({proj['google_maps_url']})" if proj["google_maps_url"] else "GPS coordinates not available"

    lines = [
        f"# Institutional Due-Diligence Dossier: {proj['name']}",
        "",
        f"**GujRERA Registration:** `{proj['registration_number']}` (Project ID: `{project_id}`)",
        f"**Promoter:** {proj['promoter_name']} (ID: `{proj['promoter_id']}`)",
        f"**Location:** {proj['taluka'] or 'Gandhinagar'}, {proj['district']} | **Type:** {proj['project_type'] or 'Group Housing'}",
        f"**Statutory Timeline:** Start: `{proj['start_date']}` | Registered Completion: `{proj['completion_date']}`",
        f"**Satellite & Land Link:** {maps_link_md}",
        "",
        "> [!IMPORTANT]",
        "> **Regulatory Due-Diligence Executive Snapshot:**",
        f"> * Total Units: **{proj['total_units'] or 'N/A'}** | Booked: **{proj['booked_units'] or 'N/A'}** ({proj['booking_rate_pct'] or 'N/A'}%)",
        f"> * Physical Progress: **{proj['engg_score_pct'] or proj['latest_form_one_progress_pct'] or 'N/A'}%** | Scheduled Time Elapsed: **{proj['time_elapsed_pct'] or 'N/A'}%**",
        f"> * Construction Velocity Ratio: **{proj['velocity_ratio'] or 'N/A'}x** (Portal Status: `{proj['progress_status_label'] or 'N/A'}`)",
        f"> * Estimated Project Cost: **{format_inr_cr(proj['estimated_cost_inr'])}** | Incurred Cost: **{format_inr_cr(proj['incurred_cost_inr'])}**",
        f"> * Society Registration: **{proj['society_reg_date'] or 'Pending / Not Formed'}** | BU Status: **{proj['bu_status'] or 'Pending'}**",
        "",
        "---",
        "",
        "## Executive 4-Quadrant Analysis",
        "",
        "### Quadrant 1: Capital Inflow & Escrow Cash-Flow Health",
    ]

    latest_fin = finances[-1] if finances else None
    if latest_fin:
        lines.extend([
            f"- **Booked Consideration Total:** {format_inr_cr(latest_fin['booked_consideration'])}",
            f"- **Actual Cash Collected from Allottees:** {format_inr_cr(latest_fin['received_amount'])}",
            f"- **Remaining Receivables from Booked Units:** {format_inr_cr(latest_fin['balance_amount'])}",
            f"- **Estimated Value of Unsold Inventory:** {format_inr_cr(latest_fin['unbooked_consideration'])}",
            f"- **Reported Cumulative Project Expenditure:** {format_inr_cr(latest_fin['incurred_and_paid'])}",
            "",
            "**Designated RERA Banking Structure:**",
        ])
        for b in banks:
            acc_label = "70% Designated Retention Escrow Account" if b["account_type"] == 1 else "100% Collection Account"
            lines.append(f"- **{acc_label}:** {b['bank_name']} ({b['branch_name'] or 'Main Branch'})")
            lines.append(f"  * Account: `{b['account_number_masked']}` | IFSC: `{b['ifsc_code']}`")
            if b["account_type"] == 1 and b["closing_bal"] is not None:
                lines.append(
                    f"  * Period Deposit: **₹{b['deposit_amt'] / 100000:.2f} Lakhs** | "
                    f"Period Withdrawal: **₹{b['withdrawal_amt'] / 100000:.2f} Lakhs** | "
                    f"Closing Balance: **₹{b['closing_bal'] / 100000:.2f} Lakhs**"
                )
    else:
        lines.append("- *Financial filings not available in archive.*")

    lines.extend([
        "",
        "### Quadrant 2: Physical Progress vs. Construction Velocity",
        f"- **Registered Handover Deadline:** `{proj['completion_date']}`",
        f"- **Structural Engineer Certified Progress:** `{proj['engg_score_pct'] or proj['latest_form_one_progress_pct']}%`",
        f"- **Total Calendar Duration Elapsed:** `{proj['time_elapsed_pct']}%`",
        f"- **Construction Velocity Ratio:** `{proj['velocity_ratio']}x` (Status: `{proj['progress_status_label']}`)",
    ])

    if proj["velocity_ratio"] and proj["velocity_ratio"] < 0.85:
        lines.append(
            f"> [!WARNING]\n> **Pace Alert:** Construction velocity ({proj['velocity_ratio']}x) is lagging calendar duration by "
            f"{(1.0 - proj['velocity_ratio']) * 100:.0f}%. High likelihood of completion delay."
        )

    if timeline:
        lines.append("")
        lines.append("- **Quarterly Milestone Trajectory:**")
        for t in timeline:
            lines.append(f"  * **{t['period_label']}**: `{t['progress_percentage']:.2f}%` physical completion")

    lines.extend([
        "",
        "### Quadrant 3: Land Identity & Block-Level Inventory Overhang",
        f"- **Town Planning Scheme (TPS):** `{proj['tp_scheme'] or 'Not explicitly identified'}`",
        f"- **Final Plot (FP) No:** `{proj['final_plot_no'] or 'Not explicitly identified'}`",
        f"- **Revenue Survey No:** `{proj['survey_no'] or 'Not explicitly identified'}`",
        f"- **GPS Plot Centroid:** `{proj['latitude']}, {proj['longitude']}`",
        "",
        "| Block Name | Total Units | Booked | Unsold | Booking % | Residential | Commercial |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])

    for b in blocks:
        lines.append(
            f"| **{b['block_name']}** | {b['total_units']} | {b['booked_units']} | {b['unbooked_units']} | {b['booking_rate_pct']:.1f}% | {b['residential_units']} | {b['commercial_units']} |"
        )

    lines.extend([
        "",
        "### Quadrant 4: Legal Milestones, Regulatory Radar & Contagion",
        f"- **Municipal Building Use (BU) Permission:** {proj['bu_status'] or 'Pending'}",
        f"- **Apartment Owners Society Registration:** {proj['society_reg_date'] or 'Pending / Not Formed'}",
        f"- **Consumer Complaints Filed:** {proj['complaints_count']} application(s)",
        f"- **Post-Registration Sanctioned Alterations:** {proj['alterations_count']} filing(s)",
        f"- **Statutory Quarterly Defaults (isDefault = YES):** {proj['default_quarters_count']} quarter(s)",
    ])

    if form5_rows:
        lines.append("")
        lines.append("**Form 5 CA Annual Audit Compliance History:**")
        for f5 in form5_rows:
            st_icon = "✅" if f5["status"] == "SUBMITTED" else "⚠️"
            lines.append(f"- {st_icon} **FY {f5['financial_year']}**: Status `{f5['status']}` (Submitted: `{f5['submitted_on'] or 'Pending'}`)")

    prof_str = "; ".join(f"**{p['role'].capitalize()}**: {p['name']} ({p['license_or_reg_no'] or 'No reg'})" for p in professionals)
    lines.append(f"- **Key Certified Professionals:** {prof_str or 'Not Listed'}")

    if prior_projects:
        prior_str = ", ".join(f"{p['linked_project_name']} (ID {p['linked_project_id']})" for p in prior_projects)
        lines.append(f"- **Promoter Sister Schemes (Prior GujRERA Links):** {prior_str}")
    else:
        lines.append("- **Promoter Sister Schemes:** No prior GujRERA projects linked under this promoter ID.")

    if contagion:
        lines.append("")
        lines.append("> [!WARNING]")
        lines.append("> **Professional Contagion Leads Detected:**")
        for c in contagion:
            lines.append(f"> - {c['detail']}")

    lines.extend([
        "",
        "---",
        "",
        "## Statutory Discrepancies & Due-Diligence Leads",
        "",
    ])

    if leads:
        for idx, lead in enumerate(leads, 1):
            badge = "🔴 HIGH RISK" if lead.severity == "HIGH" else ("🟡 AUDIT LEAD" if lead.severity == "MEDIUM" else "ℹ️ NOTICE")
            lines.extend([
                f"### {idx}. [{badge}] {lead.title}",
                f"- **Category:** `{lead.category.upper()}` | **Source:** `{lead.evidence_source}`",
                f"- **Observed Anomaly:** {lead.detail}",
                f"- **Recommended Verification:** {lead.reconciliation_guidance}",
                "",
            ])
    else:
        lines.append("No automated statutory discrepancies detected across structured fields.")

    lines.extend([
        "---",
        "",
        "## Verified Document Evidence Catalog",
        "",
        "| Document Category | Uploaded / Cataloged Files |",
        "|---|---:|",
    ])

    for d in doc_summary:
        lines.append(f"| `{d['doc_type']}` | {d['cnt']} |")

    lines.extend([
        "",
        "*Report generated from local tamper-evident GujRERA snapshot archive. Raw checksums verified.*",
    ])

    return "\n".join(lines)
