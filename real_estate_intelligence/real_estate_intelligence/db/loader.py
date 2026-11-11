"""Ingestion loader that maps GujRERA collection runs into typed relational facts and FTS5.

Decoupled from filesystem layout via the RunReader seam.
"""

import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .reader import DiskRunReader, DocumentRef, ProjectSnapshot, RunReader

from ..config import DEFAULT_DB_PATH, DEFAULT_SOURCE_RUN
from ..db.database import get_connection, init_schema
from ..db.fts import index_page_text, init_fts
from ..documents.parser import classify_document_type, extract_pdf_pages


def mask_account_number(acc: Optional[str]) -> Optional[str]:
    if not acc:
        return None
    acc_clean = str(acc).strip()
    if len(acc_clean) <= 4:
        return "****"
    return f"****{acc_clean[-4:]}"


def parse_land_identifiers(address: str, loc_data: dict) -> dict:
    addr = address or ""
    fp = loc_data.get("finalPlotNo")
    if not fp:
        fp_match = re.search(r"F(?:inal)?\.?\s*P(?:lot)?\.?\s*(?:No\.?)?\s*[:\s-]+\s*([0-9A-Za-z/]+)", addr, re.IGNORECASE)
        if fp_match:
            fp = fp_match.group(1).strip()

    tp = loc_data.get("tpScheme")
    if not tp:
        tp_match = re.search(r"T(?:own)?\.?\s*P(?:lanning)?\.?\s*(?:S(?:cheme)?)?\.?\s*(?:No\.?)?\s*[:\s-]+\s*([0-9A-Za-z/()\s-]+?)(?:Near|Road|,|FP|Final|$)", addr, re.IGNORECASE)
        if tp_match:
            tp = tp_match.group(1).strip()

    sr = loc_data.get("surveyNo")
    if not sr:
        sr_match = re.search(r"(?:Survey|Block|Sub\s*Plot)\s*(?:No\.?)?\s*[:\s-]+\s*([0-9A-Za-z/+,]+)", addr, re.IGNORECASE)
        if sr_match:
            sr = sr_match.group(1).strip()

    return {"tp_scheme": tp, "final_plot_no": fp, "survey_no": sr}


def ingest_from_run(
    source_run_or_reader: Union[RunReader, Path, str] = DEFAULT_SOURCE_RUN,
    target_db_path: Path = DEFAULT_DB_PATH,
    index_documents: bool = True,
) -> Dict[str, int]:
    """Ingest project snapshots and document references into curated SQLite and FTS5."""
    if isinstance(source_run_or_reader, RunReader):
        reader = source_run_or_reader
    else:
        reader = DiskRunReader(Path(source_run_or_reader))

    target_con = get_connection(target_db_path)
    init_schema(target_con)
    init_fts(target_con)

    run_id = getattr(reader, "run_id", "default_run") or "default_run"

    stats = {
        "projects": 0,
        "promoters": 0,
        "professionals": 0,
        "banks": 0,
        "inventory_blocks": 0,
        "unit_transactions": 0,
        "quarterly_progress": 0,
        "finances": 0,
        "form5_compliance": 0,
        "noc_bu_records": 0,
        "previous_projects": 0,
        "applications": 0,
        "documents_cataloged": 0,
        "document_pages_indexed": 0,
        "document_jobs_queued": 0,
    }

    # 1. Projects & Linked Details
    for snap in reader.iter_snapshots():
        pid = snap.project_id

        pdata = snap.project_details
        pdetail = pdata.get("projectDetail") if isinstance(pdata, dict) else {}
        pdetail = pdetail or {}

        f3_data = snap.form_three
        f3_b = f3_data.get("formThreeBId") or {}
        f1_data = snap.form_one

        total_u = f3_data.get("numberOfUnits")
        booked_u = f3_data.get("bookedUnit")
        unbooked_u = f3_data.get("unBookedUnit")
        rate_pct = None
        if total_u and booked_u is not None:
            try:
                rate_pct = round(100.0 * float(booked_u) / float(total_u), 2)
            except ZeroDivisionError:
                pass

        f1_prog = f1_data.get("progressReport")

        est_cost = None
        inc_cost = None
        if f3_b:
            try:
                est_cost = float(f3_b.get("totalEstimatedCostofTheRealEstateProject") or 0)
                inc_cost = float(f3_b.get("totalCostIncurredandPaid") or 0)
            except (ValueError, TypeError):
                pass

        # Location details & GPS
        loc_data = snap.locations
        addr = loc_data.get("address") or ""
        land_ids = parse_land_identifiers(addr, loc_data)
        coords = loc_data.get("coordinates") or []
        lat = None
        lng = None
        maps_url = None
        if coords and isinstance(coords, list) and len(coords) > 0:
            c0 = coords[0]
            try:
                lat = float(c0.get("lat"))
                lng = float(c0.get("lang"))
                maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
            except (ValueError, TypeError):
                pass

        # Legal Handover: Society Reg Date & Form 4
        f4_data = snap.form_four
        soc_reg_date = f4_data.get("society_reg_date")
        f4_status = f4_data.get("status")

        # Legal Handover: BU NOC
        noc_data = snap.noc_bu
        bu_blocks = []
        bu_rows = []
        for b in noc_data.get("blocksNocDocList") or []:
            if isinstance(b, dict):
                b_name = b.get("blockName") or "General"
                bu_chk = b.get("buCheck")
                bu_dt = b.get("buDate")
                fire_id = b.get("fireDocId")
                lift_id = b.get("liftDocId")
                bu_rows.append((pid, b_name, bu_chk, bu_dt, str(fire_id) if fire_id else None, str(lift_id) if lift_id else None))
                if bu_chk == "YES":
                    bu_blocks.append(f"{b_name} ({bu_dt or 'Approved'})")

        bu_status_str = f"Approved: {', '.join(bu_blocks)}" if bu_blocks else "Not Verified / Pending"

        # Construction Velocity Analytics
        pr_data = snap.progress_reports
        time_laps = float(pr_data.get("timeLaps") or 0.0) if pr_data.get("timeLaps") is not None else None
        engg_score = float(pr_data.get("enggScore") or 0.0) if pr_data.get("enggScore") is not None else None
        arch_score = float(pr_data.get("archScore") or 0.0) if pr_data.get("archScore") is not None else None
        pr_status = pr_data.get("progress")
        velocity_ratio = None
        if time_laps and time_laps > 0:
            velocity_ratio = round((engg_score or 0.0) / time_laps, 2)

        # Regulatory & Litigation Radar
        app_list = snap.applications
        complaint_cnt = 0
        alteration_cnt = 0
        extension_cnt = 0
        for app in app_list or []:
            if isinstance(app, dict):
                atype = str(app.get("applicationType") or "")
                if "complaint" in atype.lower():
                    complaint_cnt += 1
                elif "alteration" in atype.lower():
                    alteration_cnt += 1
                elif "extension" in atype.lower():
                    extension_cnt += 1

        # Defaults in Quarter Index
        q_idx_list = snap.quarter_index
        default_cnt = 0
        for q in q_idx_list or []:
            if isinstance(q, dict) and q.get("isDefault") == "YES":
                default_cnt += 1

        target_con.execute(
            """
            INSERT OR REPLACE INTO projects (
                project_id, run_id, name, registration_number, promoter_id, promoter_name,
                district, taluka, project_type, start_date, completion_date,
                total_units, booked_units, unbooked_units, booking_rate_pct,
                latest_form_one_progress_pct, estimated_cost_inr, incurred_cost_inr,
                collection_status,
                tp_scheme, final_plot_no, survey_no, latitude, longitude, google_maps_url,
                society_reg_date, form_four_status, bu_status,
                time_elapsed_pct, engg_score_pct, arch_score_pct, velocity_ratio, progress_status_label,
                has_complaints, complaints_count, has_alterations, alterations_count,
                has_extensions, extensions_count, default_quarters_count,
                updated_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pid,
                run_id,
                snap.name,
                snap.registration_number,
                snap.promoter_id,
                snap.promoter_name,
                pdetail.get("distName") or loc_data.get("districtName"),
                pdetail.get("talukaName") or loc_data.get("subDistrictName"),
                pdetail.get("projectType") or loc_data.get("projectType"),
                str(pdetail.get("startDate") or "")[:10],
                str(pdetail.get("completionDate") or "")[:10],
                int(total_u) if total_u is not None else None,
                int(booked_u) if booked_u is not None else None,
                int(unbooked_u) if unbooked_u is not None else None,
                rate_pct,
                float(f1_prog) if f1_prog is not None else None,
                est_cost,
                inc_cost,
                snap.status,
                land_ids["tp_scheme"],
                land_ids["final_plot_no"],
                land_ids["survey_no"],
                lat,
                lng,
                maps_url,
                soc_reg_date,
                f4_status,
                bu_status_str,
                time_laps,
                engg_score,
                arch_score,
                velocity_ratio,
                pr_status,
                1 if complaint_cnt > 0 else 0,
                complaint_cnt,
                1 if alteration_cnt > 0 else 0,
                alteration_cnt,
                1 if extension_cnt > 0 else 0,
                extension_cnt,
                default_cnt,
                snap.updated_at_utc,
            ),
        )
        stats["projects"] += 1

        # Insert BU records
        for brow in bu_rows:
            target_con.execute(
                """
                INSERT INTO noc_bu_records (
                    project_id, block_name, bu_check, bu_date, fire_doc_id, lift_doc_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                brow,
            )
            stats["noc_bu_records"] += 1

        # 2. Promoter record
        promoter_json = snap.promoter
        ptype = promoter_json.get("promoterType") or promoter_json.get("promoterTypeName")
        claimed_tot = promoter_json.get("total_projects")
        claimed_comp = promoter_json.get("completed")
        claimed_ong = promoter_json.get("ongoing")

        # Linked previous projects count
        prev_data = snap.previous_projects
        linked_rera = prev_data.get("gujrera") or []

        target_con.execute(
            """
            INSERT OR REPLACE INTO promoters (
                promoter_id, name, promoter_type, total_projects_claimed,
                completed_projects_claimed, ongoing_projects_claimed, linked_gujrera_projects_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snap.promoter_id,
                snap.promoter_name,
                ptype,
                int(claimed_tot) if claimed_tot and str(claimed_tot).isdigit() else None,
                int(claimed_comp) if claimed_comp and str(claimed_comp).isdigit() else None,
                int(claimed_ong) if claimed_ong and str(claimed_ong).isdigit() else None,
                len(linked_rera),
            ),
        )
        stats["promoters"] += 1

        # 3. Professionals (with license numbers)
        for a in pdata.get("acrchlist") or pdata.get("archlist") or []:
            name = a.get("architectName") or a.get("name")
            if name:
                target_con.execute(
                    "INSERT INTO professionals (project_id, role, name, firm_name, license_or_reg_no) VALUES (?, ?, ?, ?, ?)",
                    (pid, "architect", name.strip(), a.get("firmName"), a.get("licenceNO") or a.get("regNo")),
                )
                stats["professionals"] += 1

        for e in pdata.get("englist") or []:
            name = e.get("engineerName") or e.get("name")
            if name:
                target_con.execute(
                    "INSERT INTO professionals (project_id, role, name, firm_name, license_or_reg_no) VALUES (?, ?, ?, ?, ?)",
                    (pid, "engineer", name.strip(), e.get("firmName"), e.get("licenceNO") or e.get("regNo")),
                )
                stats["professionals"] += 1

        for c in pdata.get("calist") or []:
            name = c.get("caName") or c.get("name")
            if name:
                target_con.execute(
                    "INSERT INTO professionals (project_id, role, name, firm_name, license_or_reg_no) VALUES (?, ?, ?, ?, ?)",
                    (pid, "ca", name.strip(), c.get("firmName"), c.get("membershipNo") or c.get("regNo")),
                )
                stats["professionals"] += 1

        for con in pdata.get("contr") or []:
            name = con.get("contractorName") or con.get("name")
            if name:
                target_con.execute(
                    "INSERT INTO professionals (project_id, role, name, firm_name, license_or_reg_no) VALUES (?, ?, ?, ?, ?)",
                    (pid, "contractor", name.strip(), con.get("firmName"), con.get("licenceNO") or con.get("regNo")),
                )
                stats["professionals"] += 1

        # 4. Banks (Retention 70% Account + Collection 100% Account)
        target_con.execute("DELETE FROM banks WHERE project_id = ?", (pid,))

        # Retention account
        b_data = snap.banks
        bank_list = [b_data] if isinstance(b_data, dict) else (b_data or [])
        for b in bank_list:
            if isinstance(b, dict) and b.get("bankName"):
                dep = float(b.get("depositAmt") or 0.0) if b.get("depositAmt") is not None else None
                wd = float(b.get("withdrwalAmt") or 0.0) if b.get("withdrwalAmt") is not None else None
                op = float(b.get("openingBal") or 0.0) if b.get("openingBal") is not None else None
                cl = float(b.get("closingBal") or 0.0) if b.get("closingBal") is not None else None
                target_con.execute(
                    """
                    INSERT INTO banks (
                        project_id, bank_name, branch_name, ifsc_code, account_type,
                        account_name, account_number_masked, deposit_amt, withdrawal_amt,
                        opening_bal, closing_bal, opening_date, closing_date, passbook_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pid,
                        b.get("bankName"),
                        b.get("branchName"),
                        b.get("ifscCode"),
                        1,
                        b.get("accountName"),
                        mask_account_number(b.get("accountNumber")),
                        dep,
                        wd,
                        op,
                        cl,
                        str(b.get("openingDate") or "")[:10],
                        str(b.get("closingDate") or "")[:10],
                        str(b.get("passbookId") or ""),
                    ),
                )
                stats["banks"] += 1

        # Collection account
        c_data = snap.collection_accounts
        col_list = [c_data] if isinstance(c_data, dict) else (c_data or [])
        for c in col_list:
            if isinstance(c, dict) and c.get("bankName"):
                target_con.execute(
                    """
                    INSERT INTO banks (
                        project_id, bank_name, branch_name, ifsc_code, account_type,
                        account_name, account_number_masked, deposit_amt, withdrawal_amt,
                        opening_bal, closing_bal, opening_date, closing_date, passbook_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pid,
                        c.get("bankName"),
                        c.get("branchName"),
                        c.get("ifscCode"),
                        2,
                        c.get("accountName"),
                        mask_account_number(c.get("accountNumber")),
                        None,
                        None,
                        None,
                        float(c.get("closingBal") or 0.0) if c.get("closingBal") is not None and str(c.get("closingBal")).replace('.','',1).isdigit() else None,
                        str(c.get("openingDate") or "")[:10],
                        str(c.get("closingDate") or "")[:10],
                        str(c.get("passbookId") or ""),
                    ),
                )
                stats["banks"] += 1

        # 5. Inventory Blocks
        block_map = {}
        for unit in f3_data.get("formThreeAList") or []:
            if not isinstance(unit, dict):
                continue
            bname = str(unit.get("blockName") or "Unspecified").strip()
            status = str(unit.get("status") or "").upper()
            utype = str(unit.get("typeOfInventoryName") or unit.get("unitType") or "").lower()

            if bname not in block_map:
                block_map[bname] = {"total": 0, "booked": 0, "res": 0, "comm": 0}
            block_map[bname]["total"] += 1
            if status == "BOOKED":
                block_map[bname]["booked"] += 1
            if "shop" in utype or "office" in utype or "commercial" in utype:
                block_map[bname]["comm"] += 1
            else:
                block_map[bname]["res"] += 1

        for bname, counts in block_map.items():
            tot = counts["total"]
            bk = counts["booked"]
            unbk = tot - bk
            rate = round(100.0 * bk / tot, 2) if tot else 0.0
            target_con.execute(
                """
                INSERT OR REPLACE INTO inventory_blocks (
                    project_id, block_name, total_units, booked_units, unbooked_units,
                    booking_rate_pct, residential_units, commercial_units
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (pid, bname, tot, bk, unbk, rate, counts["res"], counts["comm"]),
            )
            stats["inventory_blocks"] += 1

        # 6. Unit Transactions (Form 3 realized sales & benchmarks)
        target_con.execute("DELETE FROM unit_transactions WHERE project_id = ? AND run_id = ?", (pid, run_id))
        for tx in snap.unit_transactions:
            utype = tx.get("unit_type") or "Residential"
            lower_u = str(utype).lower()
            if any(k in lower_u for k in ["office", "commercial office"]):
                asset_class = "Commercial_Office"
            elif any(k in lower_u for k in ["shop", "retail", "showroom", "store"]):
                asset_class = "Commercial_Retail"
            elif any(k in lower_u for k in ["warehouse", "industrial", "shed"]):
                asset_class = "Industrial_Warehouse"
            else:
                asset_class = "Residential"

            target_con.execute(
                """
                INSERT INTO unit_transactions (
                    run_id, project_id, form_three_id, block_name, unit_type, asset_class,
                    carpet_area_sqm, carpet_area_sqft, unit_consideration,
                    rate_per_sqft, rate_per_sqm, status, agreement_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    pid,
                    tx["form_three_id"],
                    tx["block_name"],
                    utype,
                    asset_class,
                    tx["carpet_area_sqm"],
                    tx["carpet_area_sqft"],
                    tx["unit_consideration"],
                    tx["rate_per_sqft"],
                    tx["rate_per_sqm"],
                    tx["status"],
                    tx["agreement_date"],
                ),
            )
            stats["unit_transactions"] += 1

        # 7. Quarterly Progress
        for p in snap.qpr_progress or []:
            if isinstance(p, dict):
                period = p.get("qtr_name") or p.get("period")
                pct = p.get("project_progress") or p.get("percentage") or 0.0
                target_con.execute(
                    """
                    INSERT INTO quarterly_timeline (
                        project_id, quarter_name, period_label, progress_percentage, submission_date
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (pid, str(period), str(period), float(pct), None),
                )
                stats["quarterly_progress"] += 1

        # 8. Financial History (Form 3 Indexed & Latest)
        for ftype, f3_hdata in [("index", snap.index_form_three), ("latest", snap.form_three)]:
            if f3_hdata:
                cost_b = f3_hdata.get("formThreeBId") or {}
                loans = f3_hdata.get("loanDtLList") or []
                loans_count = len(loans) if isinstance(loans, list) else 0

                unbk_val = f3_hdata.get("totalUnbookedUnitConside")
                res_cnt = int(f3_hdata.get("totalResidential") or 0)
                shop_cnt = int(f3_hdata.get("totalShop") or 0)
                off_cnt = int(f3_hdata.get("totalOffice") or 0)

                target_con.execute(
                    """
                    INSERT INTO finances (
                        project_id, filing_date, filing_type, form_three_id,
                        estimated_cost, incurred_and_paid, booked_consideration,
                        received_amount, balance_amount, unbooked_consideration,
                        total_residential, total_commercial_shop, total_commercial_office,
                        loan_rows_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pid,
                        f3_hdata.get("submissionOn"),
                        ftype,
                        int(f3_hdata.get("formThreeId") or 0),
                        float(cost_b.get("totalEstimatedCostofTheRealEstateProject") or 0) if cost_b.get("totalEstimatedCostofTheRealEstateProject") else None,
                        float(cost_b.get("totalCostIncurredandPaid") or 0) if cost_b.get("totalCostIncurredandPaid") else None,
                        float(f3_hdata.get("totalBookedUnitConside") or 0) if f3_hdata.get("totalBookedUnitConside") else None,
                        float(f3_hdata.get("receivedAmountTotal") or 0) if f3_hdata.get("receivedAmountTotal") else None,
                        float(f3_hdata.get("balanceAmountTotal") or 0) if f3_hdata.get("balanceAmountTotal") else None,
                        float(unbk_val or 0) if unbk_val else None,
                        res_cnt,
                        shop_cnt,
                        off_cnt,
                        loans_count,
                    ),
                )
                stats["finances"] += 1

        # 9. Form 5 Annual Compliance
        for row in snap.annual_compliance or []:
            if isinstance(row, dict) and row.get("projectFinancialYear"):
                target_con.execute(
                    """
                    INSERT INTO form5_compliance (
                        project_id, financial_year, status, submitted_on, doc_uid
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        pid,
                        row.get("projectFinancialYear"),
                        row.get("projectFinancialYearStatus") or "UNKNOWN",
                        row.get("submittedOn"),
                        row.get("pdfUid"),
                    ),
                )
                stats["form5_compliance"] += 1

        # 10. Previous Projects
        for g in prev_data.get("gujrera") or []:
            target_con.execute(
                "INSERT INTO previous_projects (project_id, linked_project_name, linked_project_id, linked_reg_no, district_name) VALUES (?, ?, ?, ?, ?)",
                (pid, g.get("projectName"), g.get("projectRegId"), g.get("projRegNo"), g.get("distName")),
            )
            stats["previous_projects"] += 1

        # 11. Applications
        for app in app_list or []:
            if isinstance(app, dict):
                target_con.execute(
                    "INSERT INTO applications (project_id, application_type, application_status, apply_date, approval_date, final_status) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        pid,
                        app.get("applicationType") or "Unknown",
                        app.get("applicationStatus"),
                        app.get("submissionDate") or app.get("applyDate"),
                        app.get("approvalDate"),
                        app.get("finalStatus"),
                    ),
                )
                stats["applications"] += 1

    # 12. Documents & FTS Indexing via RunReader
    for doc_ref in reader.iter_document_refs():
        pid = doc_ref.project_id
        rel_path = doc_ref.file_path or ""
        full_path = reader.resolve_document_path(doc_ref.uid_hash)
        file_name = full_path.name if full_path else Path(rel_path).name
        doc_type = classify_document_type(doc_ref.json_path, doc_ref.request_key, file_name)

        target_con.execute(
            """
            INSERT OR REPLACE INTO documents_catalog (
                uid_hash, project_id, doc_type, file_path, raw_bytes, sha256, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc_ref.uid_hash,
                pid,
                doc_type,
                rel_path,
                doc_ref.raw_bytes,
                doc_ref.sha256,
                doc_ref.status,
            ),
        )
        stats["documents_cataloged"] += 1

        # Text indexing for PDFs
        is_indexed = False
        if index_documents and full_path and full_path.suffix.lower() == ".pdf" and full_path.exists():
            pages = extract_pdf_pages(full_path)
            for page_num, page_text in pages:
                index_page_text(
                    con=target_con,
                    doc_uid_hash=doc_ref.uid_hash,
                    project_id=pid,
                    doc_type=doc_type,
                    file_name=file_name,
                    page_number=page_num,
                    content=page_text,
                )
                stats["document_pages_indexed"] += 1
            is_indexed = True

        # Enqueue job in document_jobs queue
        job_status = "COMPLETED" if is_indexed else "PENDING"
        target_con.execute(
            """
            INSERT OR REPLACE INTO document_jobs (
                run_id, project_id, uid_hash, doc_type, file_path, sha256, status,
                created_at_utc, updated_at_utc, completed_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), CASE WHEN ? = 'COMPLETED' THEN datetime('now') ELSE NULL END)
            """,
            (
                run_id,
                pid,
                doc_ref.uid_hash,
                doc_type,
                rel_path,
                doc_ref.sha256,
                job_status,
                job_status,
            ),
        )
        stats["document_jobs_queued"] += 1

    target_con.commit()
    target_con.close()
    return stats
