"""Statewide ETL loader integrating GujRERA data lake into high-performance relational tables.

Adheres strictly to the EGM contracts and Karpathy coding guidelines:
1. Strict read-only seam: Never write to, mutate, or redact any file in ../gujrera_pipeline/data/.
2. In-memory PII scrubbing: Allotee names, phone numbers, and KYC IDs are dropped; bank account
   numbers are masked via mask_account_number().
3. Multi-phase coordinate collision guard: Ensures zero stacked coordinates across all 17,787 projects.
4. Dual-tier architecture: 9 deep_audit projects seeded via DiskRunReader, 17,778 statewide projects.
"""

import json
import logging
import math
import os
import re
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import duckdb
except ImportError:
    duckdb = None

from ..config import DEFAULT_DB_PATH, WORKSPACE_ROOT
from .database import get_connection, init_schema
from .loader import ingest_from_run, mask_account_number
from .reader import DiskRunReader

logger = logging.getLogger(__name__)

DEEP_AUDIT_IDS = [13560, 13705, 16104, 16562, 17255, 17830, 17855, 20523, 24508]

DISTRICT_CENTROIDS = {
    "ahmedabad": (23.0225, 72.5714),
    "vadodara": (22.3072, 73.1812),
    "surat": (21.1702, 72.8311),
    "rajkot": (22.3039, 70.8022),
    "gandhinagar": (23.2156, 72.6369),
    "bhavnagar": (21.7645, 72.1519),
    "valsad": (20.5992, 72.9342),
    "anand": (22.5645, 72.9289),
    "junagadh": (21.5222, 70.4579),
    "jamnagar": (22.4707, 70.0577),
    "bharuch": (21.7051, 72.9959),
    "mehsana": (23.5880, 72.3693),
    "navsari": (20.9500, 72.9328),
    "banaskantha": (24.1724, 72.4346),
    "kutch": (23.2420, 69.6669),
    "kheda": (22.7516, 72.6847),
    "patan": (23.8493, 72.1266),
    "surendranagar": (22.7284, 71.6370),
    "gir somnath": (20.9042, 70.3667),
    "sabarkantha": (23.5977, 73.0598),
    "aravalli": (23.5414, 73.2201),
    "porbandar": (21.6417, 69.6293),
    "morbi": (22.8173, 70.8370),
    "tapi": (21.2667, 73.4333),
    "panchmahals": (22.7667, 73.6167),
    "amreli": (21.6032, 71.2221),
    "chhota udepur": (22.3108, 74.0128),
    "chhota udaipur": (22.3108, 74.0128),
    "mahisagar": (23.1645, 73.6067),
    "dahod": (22.8340, 74.2555),
    "dang": (20.8500, 73.7167),
    "botad": (22.1704, 71.6685),
    "devbhumi dwarka": (22.2442, 68.9685),
    "narmada": (21.8700, 73.5500),
}


def get_district_centroid(district_name: Optional[str]) -> Tuple[float, float]:
    """Return (latitude, longitude) center point for a Gujarat district."""
    if not district_name:
        return (23.0, 72.0)
    clean = str(district_name).strip().lower().replace("\xa0", " ")
    return DISTRICT_CENTROIDS.get(clean, (23.0, 72.0))


def parse_taluka(reg_no: Optional[str], address: Optional[str]) -> Optional[str]:
    """Extract taluka from registration number token 4 or address string."""
    if reg_no and "/" in reg_no:
        tokens = [t.strip() for t in reg_no.split("/")]
        if len(tokens) >= 4 and tokens[3]:
            return tokens[3]
    if address:
        parts = [p.strip() for p in address.split(",") if p.strip()]
        if len(parts) >= 2:
            return parts[-2]
    return None


MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_iso_date(val: Any) -> Optional[str]:
    """Parse dates across diverse GujRERA formats into standard ISO YYYY-MM-DD.

    Handles:
      - DD-MonthName-YYYY (e.g. '19-August-2021', '01-July-2017')
      - DD-MM-YYYY or DD/MM/YYYY (e.g. '01-04-2025', '19/08/2021')
      - YYYY-MM-DD / ISO timestamps (e.g. '2024-08-19', '2024-08-19T10:00:00')
    """
    if not val:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("none", "null", "nan", "nat", "0", ""):
        return None

    # 1. Already ISO format YYYY-MM-DD (e.g. '2024-08-19' or '2024-08-19T...')
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return s[:10]

    # 2. Format: DD-MonthName-YYYY (e.g. '19-August-2021', '01-July-2017', '31-Dec-2020')
    m = re.match(r"^(\d{1,2})-([A-Za-z]+)-(\d{4})", s)
    if m:
        day = int(m.group(1))
        mon_str = m.group(2).lower()
        year = int(m.group(3))
        mon = MONTH_MAP.get(mon_str)
        if mon and 1 <= day <= 31:
            return f"{year:04d}-{mon:02d}-{day:02d}"

    # 3. Format: DD-MM-YYYY or DD/MM/YYYY (e.g. '01-04-2025')
    m = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})", s)
    if m:
        day = int(m.group(1))
        mon = int(m.group(2))
        year = int(m.group(3))
        if 1 <= mon <= 12 and 1 <= day <= 31:
            return f"{year:04d}-{mon:02d}-{day:02d}"

    # 4. Format: YYYY/MM/DD
    m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        year = int(m.group(1))
        mon = int(m.group(2))
        day = int(m.group(3))
        if 1 <= mon <= 12 and 1 <= day <= 31:
            return f"{year:04d}-{mon:02d}-{day:02d}"

    return None


def resolve_pipeline_dir(pipeline_dir: Optional[Union[Path, str]] = None) -> Path:
    """Locate the root of sibling gujrera_pipeline repository."""
    if pipeline_dir:
        p = Path(pipeline_dir).resolve()
        if p.exists():
            return p
    candidates = [
        WORKSPACE_ROOT.parent / "gujrera_pipeline",
        Path.cwd().parent / "gujrera_pipeline",
        WORKSPACE_ROOT / "gujrera_pipeline",
    ]
    for c in candidates:
        if c.exists() and (c / "data").exists():
            return c.resolve()
    raise FileNotFoundError("Could not find sibling gujrera_pipeline directory containing 'data'.")


def ingest_statewide(
    pipeline_dir: Optional[Union[Path, str]] = None,
    target_db_path: Optional[Union[Path, str]] = None,
) -> Dict[str, Any]:
    """Execute complete statewide ingestion pipeline (Phases 1-2)."""
    p_root = resolve_pipeline_dir(pipeline_dir)
    target_path = Path(target_db_path) if target_db_path else DEFAULT_DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"=== Starting Statewide Data Ingestion ===")
    print(f"Producer Data Lake: {p_root / 'data'}")
    print(f"Target SQLite Database: {target_path}")

    start_time = time.time()
    stats: Dict[str, Any] = {
        "deep_audit_seeded": 0,
        "master_projects_loaded": 0,
        "governance_banks_loaded": 0,
        "governance_noc_loaded": 0,
        "professionals_loaded": 0,
        "unit_transactions_loaded": 0,
        "project_summaries_loaded": 0,
        "elapsed_seconds": 0.0,
    }

    # Connect to target database
    target_con = sqlite3.connect(target_path, timeout=60.0)
    target_con.row_factory = sqlite3.Row
    target_con.execute("PRAGMA journal_mode = WAL;")
    target_con.execute("PRAGMA synchronous = NORMAL;")
    target_con.execute("PRAGMA cache_size = -64000;")
    target_con.execute("PRAGMA foreign_keys = OFF;")  # Disable FK checks during high-speed batch load
    init_schema(target_con)

    # ---------------------------------------------------------
    # Step A: Seed Deep 9 Projects via DiskRunReader
    # ---------------------------------------------------------
    runs_dir = p_root / "data" / "runs" / "nine_projects_2026_10_15"
    if runs_dir.exists():
        print(f"\n[Step A] Seeding Deep 9 Reference Projects from {runs_dir.name}...")
        reader = DiskRunReader(runs_dir)
        ingest_from_run(source_run_or_reader=reader, target_db_path=target_path, index_documents=False)
        target_con.executemany(
            "UPDATE projects SET tier = 'deep_audit', has_deep_filings = 1 WHERE project_id = ?",
            [(pid,) for pid in DEEP_AUDIT_IDS],
        )
        target_con.commit()
        stats["deep_audit_seeded"] = len(DEEP_AUDIT_IDS)
        print(f"[Step A] Successfully seeded {len(DEEP_AUDIT_IDS)} deep_audit reference projects.")
    else:
        print(f"[Step A WARNING] Deep run not found at {runs_dir}, skipping deep seeding.")

    # ---------------------------------------------------------
    # Step B: Load Master Registry (17,787 Projects) via DuckDB
    # ---------------------------------------------------------
    master_parquet = p_root / "data" / "indexes" / "all_projects_2026-11-13.parquet"
    if not master_parquet.exists():
        raise FileNotFoundError(f"Master index parquet not found at: {master_parquet}")

    print(f"\n[Step B] Streaming Master Project Registry from {master_parquet.name}...")
    if duckdb is None:
        raise ImportError("duckdb is required for statewide ingestion. Run: uv pip install duckdb>=1.1.0")

    duck = duckdb.connect()
    master_rows = duck.execute(f"""
        SELECT 
            projectRegId, projectName, regNo, promoterName, districtName,
            projectType, project_status, startDate, endDate, projectCost,
            total_est_cost_of_proj, project_address, approvedOn
        FROM '{master_parquet.as_posix()}'
        ORDER BY projectRegId ASC
    """).fetchall()

    project_records = []
    projects_metadata = {}

    for row in master_rows:
        pid = int(row[0])
        name = str(row[1] or f"Project {pid}").strip()
        reg_no = str(row[2]).strip() if row[2] else None
        promoter_name = str(row[3] or "Independent Developer").strip()
        district = str(row[4] or "Gujarat").strip()
        ptype = str(row[5] or "Residential").strip()
        pstatus = str(row[6] or "Approved").strip()
        start_date = parse_iso_date(row[7])
        end_date = parse_iso_date(row[8])
        cost = float(row[9] or row[10] or 0.0)
        address = str(row[11] or "")
        taluka = parse_taluka(reg_no, address)
        approved_iso = parse_iso_date(row[12])
        approved_on = f"{approved_iso}T00:00:00" if approved_iso else ""

        tier = "deep_audit" if pid in DEEP_AUDIT_IDS else "statewide"
        has_deep = 1 if pid in DEEP_AUDIT_IDS else 0

        projects_metadata[pid] = {
            "name": name,
            "reg_no": reg_no,
            "promoter_name": promoter_name,
            "district": district,
            "taluka": taluka,
            "project_type": ptype,
            "project_status": pstatus,
            "tier": tier,
            "completion_date": end_date,
        }

        project_records.append((
            pid,
            "statewide_2026_11_13",
            name,
            reg_no,
            promoter_name,
            district,
            taluka,
            ptype,
            pstatus,
            start_date,
            end_date,
            cost,
            tier,
            has_deep,
            approved_on or "2026-11-13T00:00:00",
            "2026-11-13T00:00:00",
        ))

    # Batch upsert projects with tier protection
    target_con.executemany("""
        INSERT INTO projects (
            project_id, run_id, name, registration_number, promoter_name,
            district, taluka, project_type, project_status, start_date, completion_date,
            estimated_cost_inr, tier, has_deep_filings, created_at_utc, updated_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(project_id) DO UPDATE SET
            name = excluded.name,
            registration_number = COALESCE(excluded.registration_number, projects.registration_number),
            promoter_name = COALESCE(excluded.promoter_name, projects.promoter_name),
            district = excluded.district,
            taluka = COALESCE(excluded.taluka, projects.taluka),
            project_type = COALESCE(excluded.project_type, projects.project_type),
            project_status = COALESCE(excluded.project_status, projects.project_status),
            start_date = COALESCE(excluded.start_date, projects.start_date),
            completion_date = COALESCE(excluded.completion_date, projects.completion_date),
            estimated_cost_inr = COALESCE(excluded.estimated_cost_inr, projects.estimated_cost_inr),
            tier = CASE WHEN projects.tier = 'deep_audit' THEN 'deep_audit' ELSE excluded.tier END,
            has_deep_filings = CASE WHEN projects.has_deep_filings = 1 THEN 1 ELSE excluded.has_deep_filings END,
            updated_at_utc = excluded.updated_at_utc
    """, project_records)
    target_con.commit()
    stats["master_projects_loaded"] = len(project_records)
    print(f"[Step B] Upserted {len(project_records)} master projects.")

    # ---------------------------------------------------------
    # Step C: Governance Lake (Locations, Banks, NOC, Details)
    # ---------------------------------------------------------
    gov_pattern = (p_root / "data" / "governance" / "2026-11-13" / "*.parquet").as_posix()
    print(f"\n[Step C] Parsing Governance Lake from {gov_pattern}...")

    # 1. Plot Coordinates from 'locations'
    loc_rows = duck.execute(f"""
        SELECT project_id, raw_json 
        FROM '{gov_pattern}'
        WHERE endpoint = 'locations' AND raw_json IS NOT NULL
    """).fetchall()

    raw_coords: Dict[int, Tuple[float, float, int]] = {}
    for pid, rjson in loc_rows:
        try:
            d = json.loads(rjson)
            coords = d.get("coordinates")
            if coords and isinstance(coords, list) and len(coords) > 0:
                c0 = coords[0]
                lat_str, lng_str = c0.get("lat"), c0.get("lang")
                if lat_str is not None and lng_str is not None:
                    lat_f, lng_f = float(lat_str), float(lng_str)
                    if 20.0 <= lat_f <= 25.0 and 68.0 <= lng_f <= 75.0:
                        raw_coords[int(pid)] = (lat_f, lng_f, 1)
        except Exception:
            pass
    print(f"[Step C] Extracted {len(raw_coords)} verified plot coordinates (is_exact_gps = 1).")

    # 2. Escrow Banks from 'banks' (Strict in-memory masking!)
    bank_rows = duck.execute(f"""
        SELECT project_id, raw_json 
        FROM '{gov_pattern}'
        WHERE endpoint = 'banks' AND raw_json IS NOT NULL
    """).fetchall()

    bank_records = []
    project_escrow_banks: Dict[int, str] = {}
    for pid, rjson in bank_rows:
        try:
            d = json.loads(rjson)
            bdata = d.get("data") if isinstance(d, dict) else {}
            bdata = bdata or {}
            bank_name = str(bdata.get("bankName") or "").strip()
            if bank_name:
                acc_num = bdata.get("accountNumber")
                masked_acc = mask_account_number(acc_num)
                branch = bdata.get("branchName")
                ifsc = bdata.get("ifscCode")
                bank_records.append((int(pid), bank_name, branch, ifsc, masked_acc))
                if int(pid) not in project_escrow_banks:
                    project_escrow_banks[int(pid)] = bank_name
        except Exception:
            pass

    target_con.executemany("""
        INSERT INTO banks (project_id, bank_name, branch_name, ifsc_code, account_number_masked)
        VALUES (?, ?, ?, ?, ?)
    """, bank_records)
    target_con.commit()
    stats["governance_banks_loaded"] = len(bank_records)
    print(f"[Step C] Loaded {len(bank_records)} bank records with in-memory masking.")

    # 3. BU Permissions & Certificates from 'noc_bu'
    noc_rows = duck.execute(f"""
        SELECT project_id, raw_json 
        FROM '{gov_pattern}'
        WHERE endpoint = 'noc_bu' AND raw_json IS NOT NULL
    """).fetchall()

    noc_records = []
    project_bu_info: Dict[int, Tuple[int, Optional[str]]] = {}
    for pid, rjson in noc_rows:
        try:
            d = json.loads(rjson)
            blist = d.get("blocksNocDocList") if isinstance(d, dict) else []
            has_bu = 0
            bu_cert = None
            for b in blist or []:
                if isinstance(b, dict):
                    b_name = b.get("blockName") or "A"
                    bu_chk = b.get("buCheck")
                    bu_dt = parse_iso_date(b.get("buDate"))
                    fire_id = str(b.get("fireDocId") or "") or None
                    lift_id = str(b.get("liftDocId") or "") or None
                    noc_records.append((int(pid), b_name, bu_chk, bu_dt, fire_id, lift_id))
                    if bu_chk == "YES" or bu_dt:
                        has_bu = 1
                        bu_cert = str(b.get("buPdfDocId") or bu_dt or "BU-VERIFIED")
            if has_bu:
                project_bu_info[int(pid)] = (1, bu_cert)
        except Exception:
            pass

    target_con.executemany("""
        INSERT INTO noc_bu_records (project_id, block_name, bu_check, bu_date, fire_doc_id, lift_doc_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, noc_records)
    target_con.commit()
    stats["governance_noc_loaded"] = len(noc_records)
    print(f"[Step C] Loaded {len(noc_records)} NOC/BU compliance records.")

    # 4. Architects & Engineers from 'project_details'
    prof_rows = duck.execute(f"""
        SELECT project_id, raw_json 
        FROM '{gov_pattern}'
        WHERE endpoint = 'project_details' AND raw_json IS NOT NULL
    """).fetchall()

    prof_records = []
    project_architects: Dict[int, List[str]] = {}
    project_engineers: Dict[int, List[str]] = {}

    for pid, rjson in prof_rows:
        try:
            d = json.loads(rjson)
            pdata = d.get("data") if isinstance(d, dict) else {}
            pdata = pdata or {}

            archlist = pdata.get("archlist") or []
            for a in archlist:
                if isinstance(a, dict) and a.get("name"):
                    aname = str(a["name"]).strip()
                    prof_records.append((int(pid), "architect", aname, a.get("firmName"), a.get("licenceNO")))
                    project_architects.setdefault(int(pid), []).append(aname)

            englist = pdata.get("englist") or []
            for e in englist:
                if isinstance(e, dict) and e.get("name"):
                    ename = str(e["name"]).strip()
                    prof_records.append((int(pid), "engineer", ename, e.get("firmName"), e.get("licenceNO")))
                    project_engineers.setdefault(int(pid), []).append(ename)
        except Exception:
            pass

    target_con.executemany("""
        INSERT INTO professionals (project_id, role, name, firm_name, license_or_reg_no)
        VALUES (?, ?, ?, ?, ?)
    """, prof_records)
    target_con.commit()
    stats["professionals_loaded"] = len(prof_records)
    print(f"[Step C] Loaded {len(prof_records)} professionals (architects/engineers).")

    # ---------------------------------------------------------
    # Step D: Form 3 Unit Bookings (826,162 Sworn Units)
    # ---------------------------------------------------------
    f3_pattern = (p_root / "data" / "form3" / "2026-11-13" / "*.parquet").as_posix()
    print(f"\n[Step D] Streaming Form 3 Sworn Unit Bookings from {f3_pattern}...")

    # Clear unit_transactions so target count is 100% authoritative and exact
    target_con.execute("DELETE FROM unit_transactions;")
    target_con.commit()

    f3_rows = duck.execute(f"""
        SELECT project_id, raw_json 
        FROM '{f3_pattern}'
        WHERE raw_json IS NOT NULL
        ORDER BY project_id ASC
    """).fetchall()

    unit_batch: List[Tuple] = []
    unit_count = 0
    project_unit_stats: Dict[int, Dict[str, Any]] = {}

    for pid, rjson in f3_rows:
        try:
            d = json.loads(rjson)
            data = d.get("data") if isinstance(d, dict) else None
            if not data and isinstance(d, dict):
                data = d
            f3_id = data.get("formThreeId") if isinstance(data, dict) else None
            alist = data.get("formThreeAList") if isinstance(data, dict) else None

            if alist and isinstance(alist, list):
                p_stats = project_unit_stats.setdefault(int(pid), {
                    "total": 0, "booked": 0, "unbooked": 0,
                    "prices": [], "rates": [], "types": set(), "booked_by_type": {}
                })

                for u in alist:
                    if not isinstance(u, dict):
                        continue
                    bname = str(u.get("blockName") or "Main").strip()
                    utype = str(u.get("usage") or u.get("typeOfInventoryName") or "Residential").strip()
                    ca_sqm = float(u["carpetArea"]) if u.get("carpetArea") is not None else None
                    ca_sqft = round(ca_sqm * 10.7639, 2) if ca_sqm is not None else None
                    raw_cons = u.get("unitConsideration")
                    cons = float(raw_cons) if raw_cons is not None else None
                    status = str(u.get("status") or "UNBOOKED").strip().upper()
                    agr_date = parse_iso_date(u.get("dateOfAgrrement") or u.get("createdOn"))

                    rate_sqft = None
                    rate_sqm = None
                    if cons is not None and cons > 0:
                        if ca_sqft and ca_sqft > 0:
                            rate_sqft = round(cons / ca_sqft, 2)
                        if ca_sqm and ca_sqm > 0:
                            rate_sqm = round(cons / ca_sqm, 2)

                    # PII omission: alloteeName, mobileNumber, kycId are strictly ignored
                    unit_batch.append((
                        "statewide_2026_11_13",
                        int(pid),
                        f3_id,
                        bname,
                        utype,
                        "Residential" if "res" in utype.lower() else "Commercial",
                        ca_sqm,
                        ca_sqft,
                        cons,
                        rate_sqft,
                        rate_sqm,
                        status,
                        agr_date,
                    ))
                    unit_count += 1

                    # Accumulate project aggregate statistics
                    p_stats["total"] += 1
                    p_stats["types"].add(utype)
                    if status == "BOOKED":
                        p_stats["booked"] += 1
                        p_stats["booked_by_type"][utype] = p_stats["booked_by_type"].get(utype, 0) + 1
                        if cons and cons > 0:
                            p_stats["prices"].append(cons)
                            if rate_sqft and rate_sqft > 0:
                                p_stats["rates"].append(rate_sqft)
                    else:
                        p_stats["unbooked"] += 1

                    if len(unit_batch) >= 5000:
                        target_con.executemany("""
                            INSERT INTO unit_transactions (
                                run_id, project_id, form_three_id, block_name, unit_type, asset_class,
                                carpet_area_sqm, carpet_area_sqft, unit_consideration,
                                rate_per_sqft, rate_per_sqm, status, agreement_date
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, unit_batch)
                        target_con.commit()
                        unit_batch.clear()
        except Exception:
            pass

    if unit_batch:
        target_con.executemany("""
            INSERT INTO unit_transactions (
                run_id, project_id, form_three_id, block_name, unit_type, asset_class,
                carpet_area_sqm, carpet_area_sqft, unit_consideration,
                rate_per_sqft, rate_per_sqm, status, agreement_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, unit_batch)
        target_con.commit()
        unit_batch.clear()

    stats["unit_transactions_loaded"] = unit_count
    print(f"[Step D] Ingested {unit_count} sworn unit rows into unit_transactions.")

    # ---------------------------------------------------------
    # Step E: Coordinate Resolution & Collision Guard
    # ---------------------------------------------------------
    print("\n[Step E] Resolving coordinates & running collision guard across 17,787 projects...")
    resolved_coords: Dict[int, Tuple[float, float, int]] = {}
    used_coords: set = set()

    for pid in sorted(projects_metadata.keys()):
        meta = projects_metadata[pid]
        dist = meta["district"]

        if pid in raw_coords:
            lat, lng, is_exact = raw_coords[pid]
        else:
            c_lat, c_lng = get_district_centroid(dist)
            theta = (pid * 137.508) * (math.pi / 180.0)
            r = 0.005 + (((pid * 9301 + 49297) % 233280) / 233280.0) * 0.020
            lat = c_lat + r * math.sin(theta)
            lng = c_lng + r * math.cos(theta)
            is_exact = 0

        # Collision guard: Ensure coordinate pair is globally distinct
        key = (round(lat, 6), round(lng, 6))
        step = 1
        while key in used_coords:
            # Deterministic micro-offset (±0.0002 deg seeded by pid)
            micro_theta = ((pid * 137.508) + step * 45.0) * (math.pi / 180.0)
            micro_r = 0.0002 * step
            lat = lat + micro_r * math.sin(micro_theta)
            lng = lng + micro_r * math.cos(micro_theta)
            key = (round(lat, 6), round(lng, 6))
            step += 1

        used_coords.add(key)
        resolved_coords[pid] = (round(lat, 7), round(lng, 7), is_exact)

    # Update projects table with coordinates
    target_con.executemany(
        "UPDATE projects SET latitude = ?, longitude = ? WHERE project_id = ?",
        [(coords[0], coords[1], pid) for pid, coords in resolved_coords.items()],
    )
    target_con.commit()
    print(f"[Step E] Collision guard verified: {len(used_coords)} globally unique coordinate pairs.")

    # ---------------------------------------------------------
    # Step F: Pre-Aggregate project_summaries (Explore Table)
    # ---------------------------------------------------------
    print("\n[Step F] Pre-aggregating project_summaries explore table...")
    target_con.execute("DELETE FROM project_summaries;")
    target_con.commit()

    summary_records = []
    for pid in sorted(projects_metadata.keys()):
        meta = projects_metadata[pid]
        lat, lng, is_exact = resolved_coords[pid]

        p_u = project_unit_stats.get(pid, {})
        tot_u = p_u.get("total", 0)
        bk_u = p_u.get("booked", 0)
        unbk_u = p_u.get("unbooked", 0)
        abs_pct = round((bk_u / tot_u) * 100.0, 1) if tot_u > 0 else 0.0

        prices = p_u.get("prices", [])
        min_p = min(prices) if prices else None
        max_p = max(prices) if prices else None

        rates = p_u.get("rates", [])
        min_r = round(min(rates), 2) if rates else None
        avg_r = round(sum(rates) / len(rates), 2) if rates else None

        utypes = list(p_u.get("types", []))
        utypes_json = json.dumps(sorted(utypes)) if utypes else None
        bk_types = p_u.get("booked_by_type", {})
        bk_types_json = json.dumps(bk_types) if bk_types else None

        has_bu, bu_cert = project_bu_info.get(pid, (0, None))
        arch_names = ", ".join(project_architects.get(pid, [])) or None
        eng_names = ", ".join(project_engineers.get(pid, [])) or None
        bank_name = project_escrow_banks.get(pid)

        summary_records.append((
            pid,
            meta["name"],
            meta["reg_no"],
            meta["promoter_name"],
            meta["district"],
            meta["taluka"],
            meta["project_type"],
            meta["project_status"],
            meta["tier"],
            meta["completion_date"],
            tot_u,
            bk_u,
            unbk_u,
            abs_pct,
            min_p,
            max_p,
            min_r,
            avg_r,
            utypes_json,
            bk_types_json,
            has_bu,
            bu_cert,
            arch_names,
            eng_names,
            None,  # ca_name
            bank_name,
            lat,
            lng,
            is_exact,
        ))

        if len(summary_records) >= 5000:
            target_con.executemany("""
                INSERT INTO project_summaries (
                    project_id, name, registration_number, promoter_name, district, taluka,
                    project_type, project_status, tier, completion_date, total_units,
                    booked_units, unbooked_units, absorption_pct, min_price_booked,
                    max_price_booked, min_rate_sqft_booked, avg_rate_sqft_booked,
                    unit_types_json, booked_by_type_json, has_bu_noc, bu_certificate_no,
                    architect_names, engineer_names, ca_name, escrow_bank_name,
                    latitude, longitude, is_exact_gps
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, summary_records)
            target_con.commit()
            summary_records.clear()

    if summary_records:
        target_con.executemany("""
            INSERT INTO project_summaries (
                project_id, name, registration_number, promoter_name, district, taluka,
                project_type, project_status, tier, completion_date, total_units,
                booked_units, unbooked_units, absorption_pct, min_price_booked,
                max_price_booked, min_rate_sqft_booked, avg_rate_sqft_booked,
                unit_types_json, booked_by_type_json, has_bu_noc, bu_certificate_no,
                architect_names, engineer_names, ca_name, escrow_bank_name,
                latitude, longitude, is_exact_gps
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, summary_records)
        target_con.commit()
        summary_records.clear()

    stats["project_summaries_loaded"] = len(projects_metadata)
    print(f"[Step F] Pre-aggregated {len(projects_metadata)} project summaries.")

    # ---------------------------------------------------------
    # Step G: Final Optimization & Secondary Sync
    # ---------------------------------------------------------
    print("\n[Step G] Running ANALYZE and restoring constraints...")
    target_con.execute("ANALYZE;")
    target_con.execute("PRAGMA foreign_keys = ON;")
    target_con.commit()
    target_con.close()

    # Mirror to workspace secondary data location if different (only for default production runs, not custom targets)
    alt_data_path = WORKSPACE_ROOT / "real_estate_intelligence" / "data" / "intelligence.sqlite"
    if target_db_path is None and alt_data_path.resolve() != target_path.resolve():
        try:
            alt_data_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target_path, alt_data_path)
            print(f"[Step G] Synced target database to {alt_data_path}")
        except Exception as e:
            logger.warning("Could not mirror to alternate data path: %s", e)

    stats["elapsed_seconds"] = round(time.time() - start_time, 2)
    print(f"\n[COMPLETE] Statewide ingestion successfully finished in {stats['elapsed_seconds']}s.")
    return stats
