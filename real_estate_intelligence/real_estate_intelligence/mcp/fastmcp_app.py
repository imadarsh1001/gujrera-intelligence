"""FastMCP 4.2 application exposing 14 sovereign tools and read-only resources.

Exposes:
- Statewide Core (11 tools):
  1. search_projects
  2. get_project_dossier
  3. compare_projects
  4. query_unit_transactions
  5. get_spatial_pricing_benchmark
  6. get_pricing_appreciation_trend
  7. verify_sales_claim
  8. get_spatial_density
  9. get_land_records
  10. trace_entity_network
  11. get_promoter_portfolio
- Pilot Deep-Audit Gated (3 tools):
  12. audit_discrepancies
  13. get_escrow_and_finances
  14. get_regulatory_radar
- MCP Resources:
  - rera://project/{id}/summary
  - rera://project/{id}/pricing
  - rera://cluster/{cluster_id}/profile
"""

import json
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP

from .envelope import wrap_tool_response
from .server import RealEstateIntelligenceMCP

# Instantiate FastMCP server
mcp = FastMCP("GujRERA Sovereign Real Estate Intelligence", version="1.0.0")

# Internal server delegate
_mcp_server: Optional[RealEstateIntelligenceMCP] = None


def get_server() -> RealEstateIntelligenceMCP:
    """Lazy initialize server instance sharing active DB connection."""
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = RealEstateIntelligenceMCP()
    return _mcp_server


# =============================================================================
# STATEWIDE CORE TOOLS (11)
# =============================================================================


@mcp.tool()
def search_projects(
    district: Optional[str] = None,
    taluka: Optional[str] = None,
    promoter_name: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_absorption: Optional[float] = None,
    has_bu: Optional[bool] = None,
    cohort_year: Optional[int] = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Search and filter Gujarat RERA projects across the statewide universe (17,787 projects).

    Args:
        district: District name filter (case-insensitive substring match).
        taluka: Taluka name filter (case-insensitive substring match).
        promoter_name: Developer / promoter name filter (case-insensitive substring match).
        min_price: Minimum median price per sq.ft. (INR/sq.ft.).
        max_price: Maximum median price per sq.ft. (INR/sq.ft.).
        min_absorption: Minimum unit absorption rate percentage (0.0 to 100.0).
        has_bu: Filter by Building Use (BU) permission status.
        cohort_year: Registration or scheduled completion calendar year.
        limit: Maximum projects to return (default 20, max 100).
        offset: Pagination offset (default 0).
    """
    srv = get_server()
    res = srv.search_projects(
        district=district,
        taluka=taluka,
        promoter_name=promoter_name,
        min_price=min_price,
        max_price=max_price,
        min_absorption=min_absorption,
        has_bu=has_bu,
        cohort_year=cohort_year,
        limit=limit,
        offset=offset,
    )
    pids = [p["project_id"] for p in res["projects"]]
    return wrap_tool_response(
        res["projects"],
        project_ids=pids,
        tables=["projects", "project_summaries", "noc_bu_records"],
        con=srv.con,
        pagination={"offset": res["offset"], "limit": res["limit"], "total": res["total"]},
    )


@mcp.tool()
def get_project_dossier(project_id: int) -> dict:
    """Generate a complete 4-quadrant executive diligence dossier for a project.

    Args:
        project_id: The GujRERA project registration ID (e.g. 16562, 16104).
    """
    srv = get_server()
    dossier = srv.get_project_dossier(project_id)
    return wrap_tool_response(
        {"project_id": project_id, "dossier_markdown": dossier},
        project_ids=[project_id],
        tables=["projects", "project_summaries", "unit_transactions", "noc_bu_records", "banks", "finances", "form5_compliance"],
        con=srv.con,
    )


@mcp.tool()
def compare_projects(project_ids: List[int]) -> dict:
    """Compare multiple projects side-by-side on progress, pricing, velocity, and regulatory risk.

    Args:
        project_ids: List of GujRERA project registration IDs to compare.
    """
    srv = get_server()
    res = srv.compare_projects(project_ids)
    return wrap_tool_response(
        res,
        project_ids=project_ids,
        tables=["projects", "project_summaries", "noc_bu_records"],
        con=srv.con,
    )


@mcp.tool()
def query_unit_transactions(
    project_id: int,
    asset_class: Optional[str] = None,
    status: Optional[str] = None,
    min_rate: Optional[float] = None,
    max_rate: Optional[float] = None,
    year: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Query individual deed-level unit transactions with strictly indexed lookups.

    Args:
        project_id: The GujRERA project registration ID (indexed lookup key).
        asset_class: Filter by asset category ('Residential', 'Commercial_Office', 'Commercial_Retail', 'Industrial_Warehouse').
        status: Filter by unit booking status ('BOOKED' or 'UNBOOKED').
        min_rate: Minimum registered rate per sq.ft. (INR/sq.ft.).
        max_rate: Maximum registered rate per sq.ft. (INR/sq.ft.).
        year: Agreement calendar year filter.
        limit: Maximum records to return (default 50, max 200).
        offset: Pagination offset (default 0).
    """
    srv = get_server()
    res = srv.query_unit_transactions(
        project_id=project_id,
        asset_class=asset_class,
        status=status,
        min_rate=min_rate,
        max_rate=max_rate,
        year=year,
        limit=limit,
        offset=offset,
    )
    return wrap_tool_response(
        res["transactions"],
        project_ids=[project_id],
        tables=["unit_transactions"],
        con=srv.con,
        pagination={"offset": res["offset"], "limit": res["limit"], "total": res["total"]},
    )


@mcp.tool()
def get_spatial_pricing_benchmark(
    project_id: int,
    asset_class: str = "Residential",
    year: Optional[int] = None,
) -> dict:
    """Compute empirical spatial micro-market pricing benchmark using SpatialEmpiricalPricer.

    Args:
        project_id: GujRERA project registration ID.
        asset_class: Asset class ('Residential', 'Commercial_Office', 'Commercial_Retail', 'Industrial_Warehouse').
        year: Agreement calendar year.
    """
    srv = get_server()
    res = srv.get_spatial_pricing_benchmark(project_id, asset_class=asset_class, year=year)
    return wrap_tool_response(
        res,
        project_ids=[project_id],
        tables=["projects", "unit_transactions"],
        con=srv.con,
    )


@mcp.tool()
def get_pricing_appreciation_trend(project_id: int) -> dict:
    """Calculate historical quarterly registered transaction rate velocity, longitudinal appreciation, and CAGR.

    Args:
        project_id: The GujRERA project registration ID.
    """
    srv = get_server()
    res = srv.get_pricing_appreciation_trend(project_id)
    return wrap_tool_response(
        res,
        project_ids=[project_id],
        tables=["unit_transactions"],
        con=srv.con,
    )


@mcp.tool()
def verify_sales_claim(
    project_id: int,
    claimed_rate: Optional[float] = None,
    claimed_sold_pct: Optional[float] = None,
    claimed_completion_date: Optional[str] = None,
) -> dict:
    """Verify broker or developer marketing sales claims against official sworn RERA deed disclosures.

    Args:
        project_id: GujRERA project registration ID.
        claimed_rate: Claimed price per square foot (INR/sq.ft.).
        claimed_sold_pct: Claimed percentage of inventory sold (0.0 to 100.0).
        claimed_completion_date: Claimed completion date (YYYY-MM-DD).
    """
    srv = get_server()
    res = srv.verify_sales_claim(
        project_id=project_id,
        claimed_rate=claimed_rate,
        claimed_sold_pct=claimed_sold_pct,
        claimed_completion_date=claimed_completion_date,
    )
    return wrap_tool_response(
        res,
        project_ids=[project_id],
        tables=["projects", "project_summaries", "unit_transactions"],
        con=srv.con,
    )


@mcp.tool()
def get_spatial_density(
    project_id: int,
    radius_km: float = 3.0,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Find neighbouring projects within radius, shared TP scheme cluster, and competitive density.

    Args:
        project_id: GujRERA project registration ID.
        radius_km: Search radius in kilometres (default 3.0 km).
        limit: Maximum neighbours to return (default 20, max 20).
        offset: Pagination offset (default 0).
    """
    srv = get_server()
    res = srv.get_spatial_density(
        project_id=project_id,
        radius_km=radius_km,
        limit=limit,
        offset=offset,
    )
    nearby = res.get("nearby_projects", [])
    pagination = res.get("pagination", {"offset": offset, "limit": len(nearby), "total": len(nearby)})
    return wrap_tool_response(
        res,
        project_ids=[project_id],
        tables=["projects", "project_summaries"],
        con=srv.con,
        pagination=pagination,
    )


@mcp.tool()
def get_land_records(project_id: int) -> dict:
    """Fetch municipal town planning, final plot, survey identifiers, GPS centroids and block BU permissions.

    Args:
        project_id: The GujRERA project registration ID.
    """
    srv = get_server()
    res = srv.get_land_records(project_id)
    return wrap_tool_response(
        res,
        project_ids=[project_id],
        tables=["projects", "project_summaries", "noc_bu_records"],
        con=srv.con,
    )


@mcp.tool()
def trace_entity_network(project_id: int, max_tokens: int = 4000) -> dict:
    """Trace cross-project relationships, shared professionals, and contagion risk.

    Args:
        project_id: The GujRERA project registration ID.
        max_tokens: Maximum token ceiling (default 4,000).
    """
    srv = get_server()
    res = srv.trace_entity_network(project_id, max_tokens=max_tokens)
    return wrap_tool_response(
        res,
        project_ids=[project_id],
        tables=["graph_nodes", "graph_edges"],
        con=srv.con,
        max_tokens=min(max_tokens, 4000),
    )


@mcp.tool()
def get_promoter_portfolio(
    project_id: Optional[int] = None,
    promoter_name: Optional[str] = None,
) -> dict:
    """Resolve promoter cross-project portfolio with composite linkage, homonym warnings, and expired scheme risk.

    Args:
        project_id: Optional GujRERA project registration ID anchor.
        promoter_name: Optional developer/promoter commercial brand name.
    """
    srv = get_server()
    res = srv.get_promoter_portfolio(project_id=project_id, promoter_name=promoter_name)
    pids = [project_id] if project_id else []
    for p in res.get("resolved_projects", []):
        if isinstance(p, dict) and "project_id" in p:
            pids.append(p["project_id"])
    return wrap_tool_response(
        res,
        project_ids=pids,
        tables=["projects", "project_summaries", "noc_bu_records", "banks", "professionals"],
        con=srv.con,
    )


# =============================================================================
# PILOT DEEP-AUDIT GATED TOOLS (3)
# =============================================================================


@mcp.tool()
def audit_discrepancies(project_id: int, include_skipped: bool = True) -> dict:
    """Run automated discrepancy checks (cost drops, schedule slippage, missing BUs, complaints).

    Args:
        project_id: The GujRERA project registration ID.
        include_skipped: Whether to explicitly report SKIPPED_UNINGESTED indicators for unpopulated tables.
    """
    srv = get_server()
    leads = srv.audit_discrepancies(project_id, include_skipped=include_skipped)
    return wrap_tool_response(
        leads,
        project_ids=[project_id],
        tables=[
            "projects",
            "project_summaries",
            "noc_bu_records",
            "finances",
            "banks",
            "form5_compliance",
            "applications",
            "quarterly_timeline",
        ],
        con=srv.con,
    )


@mcp.tool()
def get_escrow_and_finances(project_id: int) -> dict:
    """Audit project banking structure and monthly construction cash runway (merges escrow health + runway).

    Args:
        project_id: The GujRERA project registration ID.
    """
    srv = get_server()
    res = srv.get_escrow_and_finances(project_id)
    return wrap_tool_response(
        res,
        project_ids=[project_id],
        tables=["banks", "finances", "projects"],
        con=srv.con,
    )


@mcp.tool()
def get_regulatory_radar(project_id: int) -> dict:
    """Retrieve regulatory radar indicators: complaints, Section 14 alterations, QPR defaults, and Form 5 audit history.

    Args:
        project_id: The GujRERA project registration ID.
    """
    srv = get_server()
    res = srv.get_regulatory_radar(project_id)
    return wrap_tool_response(
        res,
        project_ids=[project_id],
        tables=["projects", "project_summaries", "form5_compliance", "noc_bu_records"],
        con=srv.con,
    )


# =============================================================================
# READ-ONLY MCP RESOURCES
# =============================================================================


@mcp.resource("rera://project/{id}/summary")
def get_project_summary_resource(id: int) -> str:
    """Read-only resource for high-level project summary dossier and statutory compliance status.

    Args:
        id: GujRERA project registration ID.
    """
    srv = get_server()
    row = srv.con.execute(
        """
        SELECT p.project_id, p.name, p.registration_number, p.promoter_name,
               p.district, p.taluka, p.project_type, p.total_units, p.booked_units,
               p.booking_rate_pct, p.start_date, p.completion_date,
               ps.avg_rate_sqft_booked, ps.has_bu_noc, ps.absorption_pct
        FROM projects p
        LEFT JOIN project_summaries ps ON p.project_id = ps.project_id
        WHERE p.project_id = ?
        """,
        (id,),
    ).fetchone()
    if not row:
        return json.dumps({"error": f"Project {id} not found"})
    d = dict(row)
    d["bu_status"] = "YES" if d.get("has_bu_noc") else "NO"
    envelope = wrap_tool_response(d, project_ids=[id], tables=["projects", "project_summaries"], con=srv.con)
    return json.dumps(envelope, default=str, indent=2)


@mcp.resource("rera://project/{id}/pricing")
def get_project_pricing_resource(id: int) -> str:
    """Read-only resource for project pricing dynamics, longitudinal appreciation, and empirical comps.

    Args:
        id: GujRERA project registration ID.
    """
    srv = get_server()
    trend = srv.get_pricing_appreciation_trend(id)
    benchmark = srv.get_spatial_pricing_benchmark(id)
    payload = {
        "project_id": id,
        "pricing_trend": trend,
        "spatial_benchmark": benchmark,
    }
    envelope = wrap_tool_response(payload, project_ids=[id], tables=["unit_transactions", "projects"], con=srv.con)
    return json.dumps(envelope, default=str, indent=2)


@mcp.resource("rera://cluster/{cluster_id}/profile")
def get_cluster_profile_resource(cluster_id: str) -> str:
    """Read-only resource for town planning scheme, taluka, or spatial cluster competitive density profile.

    Args:
        cluster_id: TP scheme identifier, taluka name, or numeric project ID anchor.
    """
    srv = get_server()
    cid_str = str(cluster_id).strip()
    if cid_str.isdigit():
        pid = int(cid_str)
        density = srv.get_spatial_density(pid, radius_km=3.0, limit=20)
        envelope = wrap_tool_response(density, project_ids=[pid], tables=["projects", "project_summaries"], con=srv.con)
        return json.dumps(envelope, default=str, indent=2)

    # Query matching TP scheme or taluka
    rows = srv.con.execute(
        """
        SELECT p.project_id, p.name, p.promoter_name, p.district, p.taluka, p.tp_scheme,
               ps.avg_rate_sqft_booked, ps.absorption_pct, ps.has_bu_noc
        FROM projects p
        LEFT JOIN project_summaries ps ON p.project_id = ps.project_id
        WHERE UPPER(p.tp_scheme) = UPPER(?) OR UPPER(p.taluka) = UPPER(?)
        ORDER BY p.project_id ASC
        LIMIT 25
        """,
        (cid_str, cid_str),
    ).fetchall()
    pids = [r["project_id"] for r in rows]
    payload = {
        "cluster_query": cid_str,
        "matched_projects_count": len(rows),
        "projects": [dict(r) for r in rows],
    }
    envelope = wrap_tool_response(payload, project_ids=pids, tables=["projects", "project_summaries"], con=srv.con)
    return json.dumps(envelope, default=str, indent=2)
