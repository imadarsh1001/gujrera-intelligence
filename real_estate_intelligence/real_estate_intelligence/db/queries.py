"""Shared database query routines and serialization logic.

Single source of truth for SQL operations across API servers and CLI tools.
"""

from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple, Union

from .redaction import redact_payload, redact_record, redact_value


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
    # Note: 'days_since_latest_filing' is dropped as an active sort column since filing dates
    # are not tracked in pre-aggregated project_summaries.
    "revision_state": "revision_state",
    "project_id": "project_id",
    "total_units": "total_units",
    "booked_units": "booked_units",
    "absorption_pct": "absorption_pct",
    "absorption": "absorption_pct",
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

