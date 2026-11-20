"""Shared database query routines and serialization logic.

Single source of truth for SQL operations across API servers and CLI tools.
"""

from collections import defaultdict
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple, Union


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
    "name": "name",
    "district": "district",
    "completion_date": "completion_date",
    "progress_pct": "progress_pct",
    "min_price_booked": "min_price_booked",
    "price": "min_price_booked",
    "min_rate_sqft_booked": "min_rate_sqft_booked",
    "rate": "min_rate_sqft_booked",
    "days_since_latest_filing": "days_since_latest_filing",
    "revision_state": "revision_state",
    "project_id": "project_id",
}


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

    Price aggregates cover BOOKED transactions only. Per-unit-type aggregates
    are included for client-side filter cascading.
    """
    projects = [dict(r) for r in con.execute("SELECT * FROM projects ORDER BY project_id").fetchall()]
    if not projects:
        return []

    now_utc = datetime.now(timezone.utc)

    # Bulk pre-fetch child records in 4 indexed queries (O(1) database roundtrips)
    filings_by_pid: Dict[int, List[str]] = defaultdict(list)
    for r in con.execute(
        "SELECT project_id, filing_date FROM finances WHERE filing_date IS NOT NULL ORDER BY filing_date"
    ).fetchall():
        filings_by_pid[r["project_id"]].append(str(r["filing_date"]))

    ext_rows_by_pid: Dict[int, List[Any]] = defaultdict(list)
    for r in con.execute(
        "SELECT project_id, apply_date FROM applications WHERE application_type = 'Extension'"
    ).fetchall():
        ext_rows_by_pid[r["project_id"]].append(r["apply_date"])

    booked_by_pid: Dict[int, List[Any]] = defaultdict(list)
    for r in con.execute(
        "SELECT project_id, unit_type, unit_consideration, rate_per_sqft, agreement_date "
        "FROM unit_transactions WHERE status = 'BOOKED'"
    ).fetchall():
        booked_by_pid[r["project_id"]].append(r)

    archs_by_pid: Dict[int, List[str]] = defaultdict(list)
    for r in con.execute(
        "SELECT project_id, name FROM professionals WHERE role = 'architect' AND name IS NOT NULL AND name != '' ORDER BY name"
    ).fetchall():
        archs_by_pid[r["project_id"]].append(r["name"])

    rows: List[Dict[str, Any]] = []
    for p in projects:
        pid = p["project_id"]

        filing_dates = filings_by_pid.get(pid, [])
        ext_raw = ext_rows_by_pid.get(pid, [])
        extension_dates = sorted(
            dt.date().isoformat() for dt in (parse_timestamp(d) for d in ext_raw) if dt
        )
        latest_filing_dt = parse_timestamp(filing_dates[-1]) if filing_dates else None
        days_since_filing = max(0, (now_utc - latest_filing_dt).days) if latest_filing_dt else None

        booked = booked_by_pid.get(pid, [])
        by_type: Dict[str, Dict[str, Any]] = {}
        for r in booked:
            bucket = by_type.setdefault(r["unit_type"] or "Unknown", {
                "min_price": None, "min_rate_sqft": None, "count": 0,
                "price_date_min": None, "price_date_max": None,
            })
            bucket["count"] += 1
            price, rate, ad = r["unit_consideration"], r["rate_per_sqft"], r["agreement_date"]
            if price is not None and (bucket["min_price"] is None or price < bucket["min_price"]):
                bucket["min_price"] = price
            if rate is not None and rate > 0 and (bucket["min_rate_sqft"] is None or rate < bucket["min_rate_sqft"]):
                bucket["min_rate_sqft"] = rate
            if ad:
                ad = str(ad)
                if bucket["price_date_min"] is None or ad < bucket["price_date_min"]:
                    bucket["price_date_min"] = ad
                if bucket["price_date_max"] is None or ad > bucket["price_date_max"]:
                    bucket["price_date_max"] = ad

        overall = {
            "min_price": min((b["min_price"] for b in by_type.values() if b["min_price"] is not None), default=None),
            "min_rate_sqft": min((b["min_rate_sqft"] for b in by_type.values() if b["min_rate_sqft"] is not None), default=None),
            "price_date_min": min((b["price_date_min"] for b in by_type.values() if b["price_date_min"]), default=None),
            "price_date_max": max((b["price_date_max"] for b in by_type.values() if b["price_date_max"]), default=None),
        }

        rows.append({
            "project_id": pid,
            "name": p["name"],
            "registration_number": p["registration_number"],
            "district": p["district"],
            "taluka": p["taluka"],
            "project_type": p["project_type"],
            "promoter_name": p["promoter_name"],
            "completion_date": p["completion_date"],
            "progress_pct": p["latest_form_one_progress_pct"],
            "latitude": p["latitude"],
            "longitude": p["longitude"],
            "complaints_count": p["complaints_count"] or 0,
            "extensions_count": p["extensions_count"] or 0,
            "filings_count": len(filing_dates),
            "latest_filing_date": filing_dates[-1] if filing_dates else None,
            "days_since_latest_filing": days_since_filing,
            "revision_state": get_revision_state(len(filing_dates), len(ext_raw)),
            "revision_evidence_dates": extension_dates,
            "unit_types": sorted(by_type.keys()),
            "min_price_booked": overall["min_price"],
            "min_rate_sqft_booked": overall["min_rate_sqft"],
            "price_date_min": overall["price_date_min"],
            "price_date_max": overall["price_date_max"],
            "booked_by_unit_type": by_type,
            "architects": archs_by_pid.get(pid, []),
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
        "project": p_dict,
        "blocks": blocks,
        "units": units,
        "timeline": timeline,
        "finances": finances,
        "professionals": professionals,
        "banks": banks,
        "prior_projects": prior,
        "form5": form5,
        "bu_records": bu_records,
        "leads": leads,
        "contagion": contagion,
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
            return graph_engine.get_ego_network(project_id, depth=depth)
        except Exception:
            pass

    cur = con.cursor()
    cur.execute("SELECT node_id, kind, label FROM graph_nodes LIMIT 250")
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
            "label": r["label"],
            "group": r["kind"],
            "color": color_map.get(r["kind"], "#3b82f6"),
        }
        for r in cur.fetchall()
    ]
    node_ids = {n["id"] for n in nodes}

    cur.execute("SELECT src_id, relation, dst_id FROM graph_edges")
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
    return {"nodes": nodes, "edges": edges}
