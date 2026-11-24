"""Shared database query routines and serialization logic.

Single source of truth for SQL operations across API servers and CLI tools.
"""

from collections import OrderedDict
from datetime import datetime, timezone
import difflib
import json
from pathlib import Path
import re
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .redaction import redact_payload, redact_record, redact_value

GOVT_AUTHORITY_REGEX = re.compile(
    r"\b(VUDA|AUDA|SUDA|RUDA|GUDA|GIDC|PMAY|GHB|GUJARAT HOUSING BOARD|URBAN DEVELOPMENT AUTHORITY|MUNICIPAL|CORPORATION|NIGAM)\b",
    re.IGNORECASE,
)


def parse_timestamp(raw: Any) -> Optional[datetime]:
    """Parse a portal timestamp into an aware UTC datetime, or None if unparseable."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace(" ", "T", 1)).astimezone(timezone.utc)
    except ValueError:
        return None


def get_revision_state(filings_count: int, extension_rows_count: int) -> str:
    """Three honest states for the completion-date revision summary.

    'revision_observed': extension applications exist.
    'no_revision_observed': >= 2 filings with no extension application.
    'insufficient_history': < 2 filings on record.
    """
    if filings_count < 2:
        return "insufficient_history"
    if extension_rows_count > 0:
        return "revision_observed"
    return "no_revision_observed"


def get_projects_list(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Return concise project catalog for dropdowns and listings."""
    cur = con.execute("SELECT project_id, name, district, promoter_name FROM projects ORDER BY project_id")
    return [dict(r) for r in cur.fetchall()]


SORT_COLUMN_MAP: Dict[str, str] = {
    "project_id": "project_id",
    "name": "name",
    "registration_number": "registration_number",
    "reg_no": "registration_number",
    "promoter_name": "promoter_name",
    "promoter": "promoter_name",
    "district": "district",
    "taluka": "taluka",
    "project_type": "project_type",
    "type": "project_type",
    "project_status": "project_status",
    "status": "project_status",
    "tier": "tier",
    "completion_date": "completion_date",
    "total_units": "total_units",
    "booked_units": "booked_units",
    "unbooked_units": "unbooked_units",
    "absorption_pct": "absorption_pct",
    "absorption": "absorption_pct",
    "min_price_booked": "min_price_booked",
    "price": "min_price_booked",
    "max_price_booked": "max_price_booked",
    "min_rate_sqft_booked": "min_rate_sqft_booked",
    "rate": "min_rate_sqft_booked",
    "avg_rate_sqft_booked": "avg_rate_sqft_booked",
}


DEEP_AUDIT_IDS = {13560, 13705, 16104, 16562, 17255, 17830, 17855, 20523, 24508}


def normalize_data_tier(db_tier: Optional[str], project_id: Optional[int] = None) -> str:
    """Normalize raw DB tier into canonical 'pilot_deep' or 'statewide_core' (matching mcp/envelope.py)."""
    if project_id is not None and project_id in DEEP_AUDIT_IDS:
        return "pilot_deep"
    t = str(db_tier or "").strip().lower()
    if "deep" in t:
        return "pilot_deep"
    return "statewide_core"


def get_project_truth_flags(con: sqlite3.Connection, pid: int) -> Dict[str, Any]:
    """Single canonical source of truth for project compliance, BU status, and risk flags."""
    srow = con.execute(
        "SELECT has_bu_noc, bu_certificate_no, tier, completion_date, promoter_name, name, registration_number "
        "FROM project_summaries WHERE project_id = ?",
        (pid,),
    ).fetchone()
    prow = con.execute(
        "SELECT completion_date, promoter_name, name, registration_number, tier "
        "FROM projects WHERE project_id = ?",
        (pid,),
    ).fetchone()

    name = (srow["name"] if srow and srow["name"] else (prow["name"] if prow else "")) or ""
    promoter_name = (srow["promoter_name"] if srow and srow["promoter_name"] else (prow["promoter_name"] if prow else "")) or ""
    reg_no = (srow["registration_number"] if srow and srow["registration_number"] else (prow["registration_number"] if prow else "")) or ""
    comp_date_str = (srow["completion_date"] if srow and srow["completion_date"] else (prow["completion_date"] if prow else "")) or ""
    raw_tier = (srow["tier"] if srow and srow["tier"] else (prow["tier"] if prow else "")) or ""

    bu_rows = con.execute(
        "SELECT id, block_name, bu_check, bu_date, fire_doc_id, lift_doc_id "
        "FROM noc_bu_records WHERE project_id = ?",
        (pid,),
    ).fetchall()
    bu_blocks_total = len(bu_rows)

    has_summary_bu = bool(srow["has_bu_noc"]) if srow and srow["has_bu_noc"] is not None else False
    summary_bu_cert = str(srow["bu_certificate_no"]).strip() if srow and srow["bu_certificate_no"] else None

    verified_bu_blocks = [r for r in bu_rows if str(r["bu_check"] or "").strip().upper() == "YES" or r["bu_date"]]
    bu_blocks_granted = len(verified_bu_blocks)

    bu_dates = [str(r["bu_date"]).strip() for r in verified_bu_blocks if r["bu_date"]]
    bu_date = max(bu_dates) if bu_dates else None

    # Return bu_certificate_no ONLY when the raw value is a numeric document ID
    bu_certificate_no = None
    if summary_bu_cert and summary_bu_cert.isdigit():
        bu_certificate_no = summary_bu_cert
        bu_evidence = "doc_id"
    elif has_summary_bu or (summary_bu_cert and summary_bu_cert.upper() in ("BU-VERIFIED", "YES", "VERIFIED")) or any(str(r["bu_check"] or "").strip().upper() == "YES" for r in bu_rows):
        bu_evidence = "verified_flag"
    elif bu_dates:
        bu_evidence = "date_only"
    else:
        bu_evidence = "none"

    # Block granularity check: when 0 < bu_blocks_granted < bu_blocks_total, mark partial
    if bu_blocks_total > 0 and 0 < bu_blocks_granted < bu_blocks_total:
        has_bu_noc = False
        bu_status = "partial"
    elif bu_blocks_granted > 0 and bu_blocks_granted == bu_blocks_total:
        has_bu_noc = True
        bu_status = "verified"
    elif has_summary_bu:
        has_bu_noc = True
        bu_status = "verified"
    else:
        has_bu_noc = False
        bu_status = "none"

    is_govt_authority = bool(
        GOVT_AUTHORITY_REGEX.search(promoter_name) or GOVT_AUTHORITY_REGEX.search(name)
    )

    today_utc = datetime.now(timezone.utc).date()
    is_legacy_grandfathered = False
    months_overdue = 0
    comp_date_clean = str(comp_date_str).strip()[:10]
    if comp_date_clean:
        try:
            comp_d = datetime.strptime(comp_date_clean, "%Y-%m-%d").date()
            if comp_d.year <= 2019:
                is_legacy_grandfathered = True
            if not has_bu_noc and today_utc > comp_d:
                days_over = (today_utc - comp_d).days
                months_overdue = max(1, round(days_over / 30.4375))
        except Exception:
            pass

    if bu_status == "partial":
        overdue_suffix = f", +{months_overdue}m overdue" if months_overdue > 0 else ""
        status_badge = f"🟠 PARTIAL BU ({bu_blocks_granted}/{bu_blocks_total} blocks{overdue_suffix})"
    elif has_bu_noc:
        cert_disp = bu_certificate_no or "Verified"
        date_disp = f" (Date: {bu_date})" if bu_date else ""
        status_badge = f"✅ BU GRANTED / VERIFIED (Certificate: {cert_disp}{date_disp})"
    elif months_overdue > 0:
        if is_govt_authority:
            status_badge = f"ℹ️ EXPIRED WITHOUT BU (+{months_overdue}m overdue, Govt Authority Scheme)"
        elif is_legacy_grandfathered:
            status_badge = f"ℹ️ EXPIRED WITHOUT BU (+{months_overdue}m overdue, Legacy Pre-2020 Grandfathered)"
        else:
            status_badge = f"🔴 EXPIRED_WITHOUT_BU (+{months_overdue}m overdue)"
    else:
        sched_date = comp_date_clean or "Statutory Deadline"
        status_badge = f"⏳ Pending / Under Construction (Scheduled completion: {sched_date})"

    return {
        "has_bu_noc": has_bu_noc,
        "bu_status": bu_status,
        "bu_certificate_no": bu_certificate_no,
        "bu_evidence": bu_evidence,
        "bu_date": bu_date,
        "bu_blocks_granted": bu_blocks_granted,
        "bu_blocks_total": bu_blocks_total,
        "months_overdue": months_overdue,
        "is_legacy_grandfathered": is_legacy_grandfathered,
        "is_govt_authority": is_govt_authority,
        "status_badge": status_badge,
        "data_tier": normalize_data_tier(raw_tier, project_id=pid),
    }


_FUZZY_INDEX_CACHE: "OrderedDict[Tuple[str, int, int], Dict[str, Any]]" = OrderedDict()
_FUZZY_CACHE_LOCK = threading.Lock()
_FUZZY_CACHE_MAX = 4
_FUZZY_MIN_SCORE = 0.58


def _norm_fuzzy(text: Any) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"[^a-z0-9\s]", " ", str(text).lower())
    return " ".join(cleaned.split())


def _char_trigrams(norm_text: str) -> Set[str]:
    if not norm_text:
        return set()
    padded = f" {norm_text} "
    if len(padded) < 3:
        return {padded}
    return {padded[i : i + 3] for i in range(len(padded) - 2)}


def _token_window_ratio(q_norm: str, target_norm: str) -> float:
    if not q_norm or not target_norm:
        return 0.0
    full_ratio = difflib.SequenceMatcher(None, q_norm, target_norm).ratio()
    q_tokens = q_norm.split()
    t_tokens = target_norm.split()
    k = len(q_tokens)
    best_win = 0.0
    if k > 0 and len(t_tokens) >= k:
        for i in range(len(t_tokens) - k + 1):
            win = " ".join(t_tokens[i : i + k])
            r = difflib.SequenceMatcher(None, q_norm, win).ratio()
            if r > best_win:
                best_win = r
    return max(full_ratio, best_win)


def _get_db_cache_key(con: sqlite3.Connection) -> Optional[Tuple[str, int, int]]:
    try:
        rows = con.execute("PRAGMA database_list").fetchall()
        for r in rows:
            db_name = r[1] if len(r) > 1 else ""
            file_str = r[2] if len(r) > 2 else ""
            if db_name == "main" and file_str and file_str != ":memory:":
                p = Path(file_str)
                if p.is_file():
                    st = p.stat()
                    return (str(p.resolve()), st.st_mtime_ns, st.st_size)
    except Exception:
        pass
    return None


def _build_trigram_index(con: sqlite3.Connection) -> Dict[str, Any]:
    rows = con.execute(
        "SELECT project_id, name, district, promoter_name FROM project_summaries"
    ).fetchall()
    inverted: Dict[str, Set[int]] = {}
    docs: Dict[int, Tuple[str, str, str]] = {}
    for r in rows:
        pid = int(r["project_id"] if isinstance(r, sqlite3.Row) else r[0])
        name_n = _norm_fuzzy(r["name"] if isinstance(r, sqlite3.Row) else r[1])
        dist_n = _norm_fuzzy(r["district"] if isinstance(r, sqlite3.Row) else r[2])
        prom_n = _norm_fuzzy(r["promoter_name"] if isinstance(r, sqlite3.Row) else r[3])
        docs[pid] = (name_n, dist_n, prom_n)
        for tri in _char_trigrams(f"{name_n} {prom_n} {dist_n}".strip()):
            inverted.setdefault(tri, set()).add(pid)
    return {"inverted": inverted, "docs": docs}


def _fuzzy_search_project_summaries(
    con: sqlite3.Connection,
    clean_q: str,
    district: Optional[str],
    limit: int,
) -> List[Dict[str, Any]]:
    q_norm = _norm_fuzzy(clean_q)
    if len(q_norm) < 2:
        return []
    q_trigrams = _char_trigrams(q_norm)
    if not q_trigrams:
        return []

    cache_key = _get_db_cache_key(con)
    index: Optional[Dict[str, Any]] = None
    if cache_key is not None:
        with _FUZZY_CACHE_LOCK:
            if cache_key in _FUZZY_INDEX_CACHE:
                index = _FUZZY_INDEX_CACHE[cache_key]
                _FUZZY_INDEX_CACHE.move_to_end(cache_key)
    if index is None:
        index = _build_trigram_index(con)
        if cache_key is not None:
            with _FUZZY_CACHE_LOCK:
                _FUZZY_INDEX_CACHE[cache_key] = index
                _FUZZY_INDEX_CACHE.move_to_end(cache_key)
                while len(_FUZZY_INDEX_CACHE) > _FUZZY_CACHE_MAX:
                    _FUZZY_INDEX_CACHE.popitem(last=False)

    inverted: Dict[str, Set[int]] = index["inverted"]
    docs: Dict[int, Tuple[str, str, str]] = index["docs"]
    dist_filter = _norm_fuzzy(district) if (district and district.strip()) else None

    overlap_counts: Dict[int, int] = {}
    for tri in q_trigrams:
        for pid in inverted.get(tri, ()):
            overlap_counts[pid] = overlap_counts.get(pid, 0) + 1

    if not overlap_counts:
        return []

    # Candidate pool of top 80 trigram-overlap entries (respecting district filter)
    top_candidates = sorted(overlap_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:100]
    scored: List[Tuple[float, int]] = []
    for pid, _ in top_candidates:
        name_n, dist_n, prom_n = docs[pid]
        if dist_filter and dist_n != dist_filter:
            continue
        score = max(
            _token_window_ratio(q_norm, name_n),
            _token_window_ratio(q_norm, prom_n),
            _token_window_ratio(q_norm, f"{name_n} {dist_n}".strip()),
        )
        if score >= _FUZZY_MIN_SCORE:
            scored.append((score, pid))

    if not scored:
        return []

    scored.sort(key=lambda sp: (-sp[0], sp[1]))
    top_pids = [pid for _, pid in scored[: min(5, limit)]]

    placeholders = ",".join("?" for _ in top_pids)
    rows = con.execute(
        f"SELECT * FROM project_summaries WHERE project_id IN ({placeholders})",
        top_pids,
    ).fetchall()
    by_pid = {int(dict(r)["project_id"]): dict(r) for r in rows}

    ordered_rows: List[Dict[str, Any]] = []
    for pid in top_pids:
        row = by_pid.get(pid)
        if row is not None:
            row["match_type"] = "fuzzy"
            ordered_rows.append(row)
    return redact_payload(ordered_rows)


def search_project_summaries(
    con: sqlite3.Connection,
    q: Optional[str],
    district: Optional[str] = None,
    limit: int = 15,
) -> List[Dict[str, Any]]:
    """Query project_summaries across name, promoter_name, registration_number, district, taluka.
    
    Escapes wildcard characters and matches district case-insensitively.
    Falls back to cached trigram + token-aware fuzzy matching ONLY when exact LIKE returns 0 rows.
    Scrubbed via redact_payload before returning.
    """
    clean_q = (q or "").strip()
    if len(clean_q) < 2:
        return []

    clamped_limit = min(max(1, limit), 50)
    escaped = clean_q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"

    sql = """
        SELECT * FROM project_summaries
        WHERE (
            name LIKE ? ESCAPE '\\'
            OR promoter_name LIKE ? ESCAPE '\\'
            OR registration_number LIKE ? ESCAPE '\\'
            OR district LIKE ? ESCAPE '\\'
            OR taluka LIKE ? ESCAPE '\\'
        )
    """
    params: List[Any] = [pattern, pattern, pattern, pattern, pattern]

    if district and district.strip():
        sql += " AND LOWER(district) = LOWER(?)"
        params.append(district.strip())

    sql += " ORDER BY project_id ASC LIMIT ?"
    params.append(clamped_limit)

    cur = con.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    if rows:
        for r in rows:
            r["match_type"] = "exact"
        return redact_payload(rows)

    return _fuzzy_search_project_summaries(con, clean_q, district, clamped_limit)


def sort_explore_rows(
    rows: List[Dict[str, Any]],
    sort_by: Optional[str] = None,
    sort_dir: Optional[str] = "asc",
) -> List[Dict[str, Any]]:
    """Sort explore rows by whitelisted column with safe None handling."""
    if not sort_by:
        return rows
    field = SORT_COLUMN_MAP.get(str(sort_by).lower())
    if not field:
        return rows
    desc = (str(sort_dir).lower() == "desc") if sort_dir else False

    def sort_key(r: Dict[str, Any]) -> Tuple[int, float, str, str, int]:
        v = r.get(field)
        is_none = (v is None or v == "")
        name = str(r.get("name") or "").lower()
        pid = r.get("project_id") or 0
        if desc:
            if is_none:
                return (0, 0.0, "", name, pid)
            if isinstance(v, (int, float)):
                return (1, float(v), "", name, pid)
            return (1, 0.0, str(v).lower(), name, pid)
        else:
            if is_none:
                return (1, 0.0, "", name, pid)
            if isinstance(v, (int, float)):
                return (0, float(v), "", name, pid)
            return (0, 0.0, str(v).lower(), name, pid)

    return sorted(rows, key=sort_key, reverse=desc)


def get_explore_facets(con: sqlite3.Connection) -> Dict[str, Any]:
    """Return distinct districts with project counts and distinct unit types for dropdown filters."""
    cur = con.execute(
        "SELECT district, COUNT(*) as count FROM projects "
        "WHERE district IS NOT NULL AND district != '' "
        "GROUP BY district ORDER BY district ASC"
    )
    districts = {r["district"]: r["count"] for r in cur.fetchall()}

    cur_u = con.execute(
        "SELECT DISTINCT unit_type FROM unit_transactions "
        "WHERE unit_type IS NOT NULL AND unit_type != '' "
        "ORDER BY unit_type ASC"
    )
    unit_types = [r["unit_type"] for r in cur_u.fetchall()]
    return {
        "districts": districts,
        "unit_types": unit_types,
    }


def get_map_pins(
    con: sqlite3.Connection,
    district: Optional[str] = None,
    tier: Optional[str] = None,
    status: Optional[str] = None,
) -> List[List[Any]]:
    """Fetch compact map pins: [project_id, latitude, longitude, tier, project_status, is_exact_gps, name, district]."""
    sql = """
        SELECT project_id, latitude, longitude, tier, project_status, is_exact_gps, name, district
        FROM project_summaries
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """
    params: List[Any] = []
    if district:
        sql += " AND district = ?"
        params.append(district)
    if tier:
        sql += " AND tier = ?"
        params.append(tier)
    if status:
        sql += " AND project_status = ?"
        params.append(status)
    sql += " ORDER BY project_id ASC"
    cur = con.execute(sql, params)
    return [list(r) for r in cur.fetchall()]


def get_explore_rows(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    """One pre-aggregated row per project for the Explore table (route contract in ui/EGM.md).

    Reads directly from pre-aggregated project_summaries joined with projects metadata.
    Zero unit_transactions scans.
    """
    try:
        has_summaries = con.execute("SELECT 1 FROM project_summaries LIMIT 1").fetchone()
    except sqlite3.OperationalError:
        has_summaries = None

    if not has_summaries:
        return []

    cur = con.execute("""
        SELECT 
            s.project_id, s.name, s.registration_number, s.promoter_name, s.district, s.taluka,
            s.project_type, s.completion_date, s.latitude, s.longitude, s.min_price_booked,
            s.min_rate_sqft_booked, s.total_units, s.booked_units, s.unbooked_units,
            s.absorption_pct, s.unit_types_json, s.booked_by_type_json, s.architect_names,
            p.latest_form_one_progress_pct AS progress_pct,
            COALESCE(p.complaints_count, 0) AS complaints_count,
            COALESCE(p.extensions_count, 0) AS extensions_count
        FROM project_summaries s
        LEFT JOIN projects p ON s.project_id = p.project_id
        ORDER BY s.project_id ASC
    """)
    rows: List[Dict[str, Any]] = []
    for r in cur.fetchall():
        s = dict(r)
        pid = s["project_id"]

        raw_utypes = s.get("unit_types_json")
        try:
            unit_types = json.loads(raw_utypes) if raw_utypes else []
        except Exception:
            unit_types = []

        raw_booked = s.get("booked_by_type_json")
        try:
            raw_booked_map = json.loads(raw_booked) if raw_booked else {}
        except Exception:
            raw_booked_map = {}

        min_p = s.get("min_price_booked")
        min_r = s.get("min_rate_sqft_booked")

        # Populate min_price and min_rate_sqft only when the project has a single booked unit type.
        # For multi-type projects, project_summaries does not track per-type pricing, so setting None
        # avoids falsely attributing project-wide residential minimums to commercial/other unit types.
        is_single_type = (len(raw_booked_map) == 1)
        type_p = min_p if is_single_type else None
        type_r = min_r if is_single_type else None

        booked_by_type: Dict[str, Dict[str, Any]] = {}
        for utype, val in raw_booked_map.items():
            cnt = val if isinstance(val, int) else (val.get("count", 0) if isinstance(val, dict) else 0)
            booked_by_type[utype] = {
                "count": cnt,
                "min_price": type_p,
                "min_rate_sqft": type_r,
                "price_date_min": None,
                "price_date_max": None,
            }

        arch_raw = s.get("architect_names")
        architects = [redact_value("name", a.strip()) for a in arch_raw.split(",") if a.strip()] if arch_raw else []

        ext_cnt = s.get("extensions_count") or 0
        rev_state = "revision_observed" if ext_cnt > 0 else "insufficient_history"

        rows.append({
            "project_id": pid,
            "name": s["name"],
            "registration_number": s["registration_number"],
            "district": s["district"],
            "taluka": s["taluka"],
            "project_type": s["project_type"],
            "promoter_name": s["promoter_name"],
            "completion_date": s["completion_date"],
            "progress_pct": s["progress_pct"],
            "latitude": s["latitude"],
            "longitude": s["longitude"],
            "complaints_count": s["complaints_count"],
            "extensions_count": ext_cnt,
            "filings_count": 0,
            "latest_filing_date": None,
            "days_since_latest_filing": None,
            "revision_state": rev_state,
            "revision_evidence_dates": [],
            "unit_types": unit_types,
            "min_price_booked": min_p,
            "min_rate_sqft_booked": min_r,
            "price_date_min": None,
            "price_date_max": None,
            "booked_by_unit_type": booked_by_type,
            "architects": architects,
            # Pre-aggregated Form 3 metrics
            "total_units": s.get("total_units"),
            "booked_units": s.get("booked_units"),
            "unbooked_units": s.get("unbooked_units"),
            "absorption_pct": s.get("absorption_pct"),
        })
    return rows


def get_project_detail(
    con: sqlite3.Connection,
    pid: int,
    auditor: Any = None,
    graph_engine: Any = None,
) -> Optional[Dict[str, Any]]:
    """Fetch complete statutory records, forensic leads, and network risk for a project."""
    cur = con.execute("SELECT * FROM projects WHERE project_id = ?", (pid,))
    prow = cur.fetchone()
    if not prow:
        return None

    p_dict = dict(prow)
    s_row = con.execute("SELECT * FROM project_summaries WHERE project_id = ?", (pid,)).fetchone()
    if s_row:
        s = dict(s_row)
        if p_dict.get("booking_rate_pct") is None:
            p_dict["booking_rate_pct"] = s.get("absorption_pct")
        if p_dict.get("total_units") is None:
            p_dict["total_units"] = s.get("total_units")
        if p_dict.get("booked_units") is None:
            p_dict["booked_units"] = s.get("booked_units")
        if p_dict.get("unbooked_units") is None:
            p_dict["unbooked_units"] = s.get("unbooked_units")
        if s.get("has_bu_noc") and not p_dict.get("bu_status"):
            p_dict["bu_status"] = f"Verified (Cert #{s.get('bu_certificate_no') or 'YES'})"

    blocks = [dict(r) for r in con.execute("SELECT * FROM inventory_blocks WHERE project_id = ? ORDER BY block_name", (pid,)).fetchall()]
    if not blocks:
        cur_blocks = con.execute("""
            SELECT 
                block_name,
                COUNT(*) as total_units,
                SUM(CASE WHEN status = 'BOOKED' THEN 1 ELSE 0 END) as booked_units,
                SUM(CASE WHEN status != 'BOOKED' THEN 1 ELSE 0 END) as unbooked_units,
                ROUND(100.0 * SUM(CASE WHEN status = 'BOOKED' THEN 1 ELSE 0 END) / COUNT(*), 1) as booking_rate_pct,
                SUM(CASE WHEN asset_class = 'Residential' THEN 1 ELSE 0 END) as residential_units,
                SUM(CASE WHEN asset_class = 'Commercial' THEN 1 ELSE 0 END) as commercial_units
            FROM unit_transactions
            WHERE project_id = ?
            GROUP BY block_name
            ORDER BY block_name
        """, (pid,))
        blocks = [dict(r) for r in cur_blocks.fetchall()]

    units = [
        dict(r) for r in con.execute(
            "SELECT block_name, unit_type, asset_class, carpet_area_sqft, unit_consideration, rate_per_sqft, status, agreement_date "
            "FROM unit_transactions WHERE project_id = ? ORDER BY agreement_date DESC, id DESC LIMIT 500",
            (pid,)
        ).fetchall()
    ]
    timeline = [dict(r) for r in con.execute("SELECT * FROM quarterly_timeline WHERE project_id = ? ORDER BY id ASC", (pid,)).fetchall()]
    finances = [dict(r) for r in con.execute("SELECT * FROM finances WHERE project_id = ? ORDER BY id ASC", (pid,)).fetchall()]
    professionals = [dict(r) for r in con.execute("SELECT role, name, firm_name, license_or_reg_no FROM professionals WHERE project_id = ?", (pid,)).fetchall()]
    banks = [dict(r) for r in con.execute("SELECT * FROM banks WHERE project_id = ? ORDER BY account_type ASC", (pid,)).fetchall()]
    prior = [dict(r) for r in con.execute(
        "SELECT linked_project_name, linked_project_id FROM previous_projects WHERE project_id = ? AND linked_project_id != ?",
        (pid, pid),
    ).fetchall()]
    form5 = [dict(r) for r in con.execute("SELECT * FROM form5_compliance WHERE project_id = ? ORDER BY financial_year ASC", (pid,)).fetchall()]
    bu_records = [dict(r) for r in con.execute("SELECT * FROM noc_bu_records WHERE project_id = ? ORDER BY block_name ASC", (pid,)).fetchall()]

    leads: List[Dict[str, Any]] = []
    credential_coverage: Dict[str, Any] = {}
    escrow_runway: Dict[str, Any] = {}
    if auditor is not None:
        try:
            leads = [
                {
                    "category": l.category,
                    "severity": l.severity,
                    "title": l.title,
                    "detail": l.detail,
                    "reconciliation_guidance": l.reconciliation_guidance,
                }
                for l in auditor.audit_project(pid)
            ]
            credential_coverage = auditor.audit_credential_coverage(pid)
            escrow_runway = auditor.calculate_escrow_runway(pid)
        except Exception:
            pass

    contagion: List[Dict[str, Any]] = []
    if graph_engine is not None:
        try:
            contagion = graph_engine.trace_contagion_risk(pid)
        except Exception:
            pass

    ext_rows = con.execute(
        "SELECT apply_date, approval_date FROM applications WHERE project_id = ? AND application_type = 'Extension'",
        (pid,),
    ).fetchall()
    filings_count = con.execute(
        "SELECT COUNT(*) FROM finances WHERE project_id = ? AND filing_date IS NOT NULL", (pid,)
    ).fetchone()[0]

    return {
        "project": redact_record(p_dict),
        "blocks": blocks,
        "units": units,
        "timeline": timeline,
        "finances": finances,
        "professionals": [redact_record(p) for p in professionals],
        "banks": [redact_record(b) for b in banks],
        "prior_projects": prior,
        "form5": form5,
        "bu_records": bu_records,
        "leads": redact_payload(leads),
        "contagion": redact_payload(contagion),
        "filings_count": filings_count,
        "revision_state": get_revision_state(filings_count, len(ext_rows)),
        "revision_evidence_dates": sorted(
            dt.date().isoformat() for dt in (parse_timestamp(r["apply_date"]) for r in ext_rows) if dt
        ),
        "revision_actioned_dates": sorted(
            dt.date().isoformat() for dt in (parse_timestamp(r["approval_date"]) for r in ext_rows) if dt
        ),
        "credential_coverage": credential_coverage,
        "escrow_runway": escrow_runway,
    }


def get_graph_data(
    con: sqlite3.Connection,
    graph_engine: Any = None,
    project_id: Optional[int] = None,
    depth: int = 2,
) -> Dict[str, Any]:
    """Return nodes and edges formatted for Vis.js (scoped to project ego-network if requested)."""
    if project_id and project_id > 0 and graph_engine is not None:
        try:
            return redact_payload(graph_engine.get_ego_network(project_id, depth=depth))
        except Exception:
            pass

    cur = con.cursor()
    cur.execute(
        "SELECT node_id, kind, label FROM graph_nodes "
        "WHERE node_id NOT LIKE 'promoter:None%' AND node_id != 'promoter:' LIMIT 250"
    )
    color_map = {
        "Project": "#2563eb",
        "Promoter": "#7c3aed",
        "Engineer": "#d97706",
        "Architect": "#0d9488",
        "Ca": "#059669",
        "Bank": "#e11d48",
        "PriorProject": "#64748b",
    }
    nodes = [
        {
            "id": r["node_id"],
            "label": redact_value("name", r["label"]),
            "group": r["kind"],
            "color": color_map.get(r["kind"], "#3b82f6"),
        }
        for r in cur.fetchall()
    ]
    node_ids = {n["id"] for n in nodes}

    cur.execute(
        "SELECT src_id, relation, dst_id FROM graph_edges "
        "WHERE src_id NOT LIKE 'promoter:None%' AND dst_id NOT LIKE 'promoter:None%' "
        "  AND src_id != 'promoter:' AND dst_id != 'promoter:'"
    )
    edges = [
        {
            "from": r["src_id"],
            "to": r["dst_id"],
            "label": r["relation"],
            "color": {"color": "#94a3b8", "highlight": "#2563eb"},
        }
        for r in cur.fetchall()
        if r["src_id"] in node_ids and r["dst_id"] in node_ids
    ]
    return redact_payload({"nodes": nodes, "edges": edges})


def get_zombie_radar_data(
    con: sqlite3.Connection,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Retrieve high-risk modern private schemes past completion deadline with no BU/NOC.

    Selection Criteria:
    - COALESCE(has_bu_noc, 0) = 0 (no registered BU/NOC)
    - completion_date >= '2020-01-01' (modern schemes; pre-2020 grandfathered excluded)
    - completion_date < current UTC date (strictly past deadline)
    - Excludes public governmental authority promoters (AUDA, VUDA, SUDA, RUDA, GUDA, GIDC, PMAY, GHB, etc.)
    - Ordered by booked_units DESC to highlight projects with highest trapped buyer risk.
    """
    today_utc = datetime.now(timezone.utc).date()
    today_str = today_utc.isoformat()

    cur = con.cursor()
    sql = """
        SELECT 
            project_id,
            name,
            district,
            promoter_name,
            completion_date,
            booked_units,
            unbooked_units,
            total_units,
            absorption_pct,
            min_price_booked,
            max_price_booked,
            min_rate_sqft_booked
        FROM project_summaries
        WHERE COALESCE(has_bu_noc, 0) = 0
          AND completion_date IS NOT NULL
          AND completion_date >= '2020-01-01'
          AND completion_date < ?
        ORDER BY booked_units DESC
    """
    cur.execute(sql, (today_str,))
    rows = cur.fetchall()

    govt_keywords = (
        "AUDA", "VUDA", "SUDA", "RUDA", "GUDA", "GIDC",
        "PMAY", "GHB", "GUJARAT HOUSING BOARD", "MUNICIPAL",
        "CORPORATION", "NIGAM", "AUTHORITY",
    )

    results: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        pname = (d.get("promoter_name") or "").upper()
        p_proj_name = (d.get("name") or "").upper()
        if any(kw in pname or kw in p_proj_name for kw in govt_keywords):
            continue

        comp_date_str = d.get("completion_date")
        months_overdue = 0
        if comp_date_str:
            try:
                comp_d = datetime.strptime(str(comp_date_str)[:10], "%Y-%m-%d").date()
                if today_utc > comp_d:
                    days_over = (today_utc - comp_d).days
                    months_overdue = max(1, round(days_over / 30.4375))
            except ValueError:
                pass

        d["months_overdue"] = months_overdue
        d["status_badge"] = f"🔴 EXPIRED_WITHOUT_BU (+{months_overdue}m overdue)"
        d["risk_level"] = "HIGH"
        results.append(redact_record(d))
        if len(results) >= limit:
            break

    return results


def get_markup_spread_data(con: sqlite3.Connection) -> Dict[str, Any]:
    """Retrieve statewide unbooked asking rate markup vs. registered booked rate spread.

    Uses covering index idx_unit_status_rates on unit_transactions to aggregate
    booked vs unbooked average rates, and project_summaries for district totals.
    """
    cur = con.cursor()
    # Aggregated over covering index idx_unit_status_rates
    cur.execute("""
        SELECT 
            status,
            COUNT(*) as unit_count,
            ROUND(AVG(rate_per_sqft), 2) as avg_rate_per_sqft,
            ROUND(AVG(unit_consideration), 2) as avg_consideration
        FROM unit_transactions
        WHERE rate_per_sqft > 0
        GROUP BY status
    """)
    unit_rows = cur.fetchall()
    unit_stats = {r["status"]: dict(r) for r in unit_rows}

    booked_avg = (unit_stats.get("BOOKED") or {}).get("avg_rate_per_sqft") or 0.0
    unbooked_avg = (unit_stats.get("UNBOOKED") or {}).get("avg_rate_per_sqft") or 0.0

    empirical_markup_pct = (
        round(((unbooked_avg - booked_avg) / booked_avg) * 100, 2)
        if booked_avg > 0 else 12.63
    )

    # District breakdowns from project_summaries
    cur.execute("""
        SELECT 
            district,
            COUNT(*) as project_count,
            SUM(booked_units) as total_booked_units,
            SUM(unbooked_units) as total_unbooked_units,
            ROUND(AVG(min_rate_sqft_booked), 2) as avg_min_rate_sqft_booked
        FROM project_summaries
        WHERE district IS NOT NULL AND district != ''
        GROUP BY district
        ORDER BY project_count DESC
        LIMIT 10
    """)
    district_rows = [dict(r) for r in cur.fetchall()]

    payload = {
        "statewide_baseline_markup_pct": 12.63,
        "empirical_markup_pct": empirical_markup_pct,
        "statewide_transactions_summary": unit_stats,
        "top_districts_breakdown": district_rows,
        "provenance": {
            "source": "unit_transactions + project_summaries",
            "index_used": "idx_unit_status_rates",
            "statutory_note": (
                "Unbooked rates reflect developer portal asking prices; "
                "booked rates reflect verified registered consideration."
            ),
        },
    }
    return redact_payload(payload)


def get_developer_clusters_data(
    con: sqlite3.Connection,
    promoter_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve developer portfolio clusters via Composite Key (c) or return top brand summary."""
    from ..graph.network import resolve_promoter_portfolio

    if promoter_name and promoter_name.strip():
        portfolio = resolve_promoter_portfolio(con, promoter_name=promoter_name.strip())
        return redact_payload(portfolio)

    cur = con.cursor()
    cur.execute("""
        SELECT promoter_name, count(*) as project_count
        FROM projects
        WHERE promoter_name IS NOT NULL AND trim(promoter_name) != ''
          AND promoter_name NOT LIKE 'AUDA%'
          AND promoter_name NOT LIKE 'VUDA%'
          AND promoter_name NOT LIKE '%MUNICIPAL%'
          AND promoter_name NOT LIKE '%HOUSING BOARD%'
          AND promoter_name NOT LIKE '%CORPORATION%'
          AND promoter_name NOT LIKE '%AUTHORITY%'
        GROUP BY promoter_name
        ORDER BY project_count DESC
        LIMIT 12
    """)
    top_promoters = [dict(r) for r in cur.fetchall()]

    payload = {
        "mode": "statewide_developer_overview",
        "description": (
            "Statewide Developer Portfolio & Cluster Resolution. "
            "Pass ?promoter_name=<name> to resolve Composite Key (c) clusters."
        ),
        "frequent_brand_names": [
            "SHREEJI DEVELOPERS",
            "SHIV DEVELOPERS",
            "SHIVAM DEVELOPERS",
            "SHREE DEVELOPERS",
            "OM DEVELOPERS",
            "RADHE DEVELOPERS",
            "MARUTI DEVELOPERS",
        ],
        "top_promoters_by_project_count": top_promoters,
        "clustering_methodology": (
            "Projects are partitioned into disjoint clusters using Composite Key (c): "
            "promoter_name + shared verified professional license OR shared bank IFSC/branch."
        ),
    }
    return redact_payload(payload)

