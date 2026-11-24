"""Forensic Agent Tools Factory.

Provides LangChain @tool wrappers around verified analytical engines and FastMCP
tool implementations, with per-request read-only SQLite database connections,
strict 6,000-token envelopes, PII scrubbing, and statutory truth flags.
"""

import sqlite3
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from pathlib import Path

from langchain_core.tools import tool

from ..analytics.audit import ProjectAuditor
from ..analytics.claims_checker import SalesClaimVerifier
from ..analytics.investor_dossier import generate_investor_dossier
from ..analytics.spatial_pricing import SpatialEmpiricalPricer
from ..db.database import get_connection
from ..db.queries import (
    get_project_detail,
    get_project_truth_flags,
    search_project_summaries,
)
from ..graph.network import KnowledgeGraph, resolve_promoter_portfolio
from ..mcp.envelope import wrap_tool_response


def build_forensic_tools(
    db_path_or_conn: Optional[Any] = None,
) -> Tuple[List[Any], Callable[[], None]]:
    """Build LangChain tools bound to an isolated read_only SQLite connection.

    Args:
        db_path_or_conn: File path, string path, or existing sqlite3.Connection.
            If None or a path is passed, a new read_only=True connection is created.

    Returns:
        (tools_list, teardown_callback)
    """
    owns_connection = False
    if isinstance(db_path_or_conn, sqlite3.Connection):
        con = db_path_or_conn
    else:
        path = db_path_or_conn if db_path_or_conn is not None else None
        con = get_connection(path, read_only=True)
        owns_connection = True

    def teardown() -> None:
        if owns_connection and con:
            try:
                con.close()
            except Exception:
                pass

    auditor = ProjectAuditor(con)
    claims_verifier = SalesClaimVerifier(con)
    spatial_pricer = SpatialEmpiricalPricer(con)
    graph_engine = KnowledgeGraph(con)

    @tool
    def search_projects(
        query: str,
        district: Optional[str] = None,
        limit: int = 15,
    ) -> Dict[str, Any]:
        """Search and filter Gujarat RERA projects by name, promoter, registration number, or district."""
        results = search_project_summaries(con, q=query, district=district, limit=limit)
        pids = [r["project_id"] for r in results if isinstance(r, dict) and "project_id" in r]
        return wrap_tool_response(
            results,
            project_ids=pids,
            tables=["project_summaries"],
            con=con,
        )

    @tool
    def get_project_dossier(project_id: int) -> Dict[str, Any]:
        """Retrieve executive 4-quadrant diligence dossier and statutory truth flags for a project ID."""
        pid = int(project_id)
        dossier_text = generate_investor_dossier(con, pid)
        truth_flags = get_project_truth_flags(con, pid)
        payload = {
            "project_id": pid,
            "truth_flags": truth_flags,
            "dossier_markdown": dossier_text,
        }
        return wrap_tool_response(
            payload,
            project_ids=[pid],
            tables=["projects", "project_summaries", "noc_bu_records", "banks", "finances", "form5_compliance"],
            con=con,
        )

    @tool
    def audit_discrepancies(project_id: int, include_skipped: bool = True) -> Dict[str, Any]:
        """Audit statutory filings for cost drops, schedule delays, BU status, and bank encumbrances."""
        pid = int(project_id)
        leads = auditor.audit_project(pid, include_skipped=include_skipped)
        lead_dicts = [
            {
                "category": l.category,
                "severity": l.severity,
                "title": l.title,
                "detail": l.detail,
                "evidence_source": l.evidence_source,
                "reconciliation_guidance": l.reconciliation_guidance,
            }
            for l in leads
        ]
        truth_flags = get_project_truth_flags(con, pid)
        has_skipped = any("SKIPPED_UNINGESTED" in (l.get("severity", "") + l.get("title", "")) for l in lead_dicts)
        payload = {
            "project_id": pid,
            "truth_flags": truth_flags,
            "discrepancies": lead_dicts,
            "has_skipped_uningested": has_skipped,
        }
        return wrap_tool_response(
            payload,
            project_ids=[pid],
            tables=["projects", "project_summaries", "finances", "form5_compliance", "noc_bu_records"],
            con=con,
        )

    @tool
    def verify_sales_claim(
        project_id: int,
        claim_type: str,
        claimed_value: float,
        asset_class: str = "Residential",
    ) -> Dict[str, Any]:
        """Verify broker sales price or absorption claims against registered transactions and spatial benchmarks."""
        pid = int(project_id)
        res = claims_verifier.verify_claim(
            pid,
            claimed_rate_sqft=claimed_value if claim_type != "absorption_pct" else None,
            claimed_sold_pct=claimed_value if claim_type == "absorption_pct" else None,
            asset_class=asset_class,
        )
        return wrap_tool_response(
            res,
            project_ids=[pid],
            tables=["unit_transactions", "project_summaries"],
            con=con,
        )

    @tool
    def get_spatial_pricing_benchmark(
        project_id: int,
        asset_class: str = "Residential",
    ) -> Dict[str, Any]:
        """Compute empirical spatial pricing distribution within registered micro-market transactions."""
        pid = int(project_id)
        res = spatial_pricer.benchmark(pid, asset_class=asset_class)
        return wrap_tool_response(
            res,
            project_ids=[pid],
            tables=["project_summaries", "unit_transactions"],
            con=con,
        )

    @tool
    def compare_projects(project_ids: List[int]) -> Dict[str, Any]:
        """Compare multiple projects side-by-side with statutory truth flags and financial metrics."""
        pids = [int(p) for p in project_ids[:10] if p is not None]
        comparisons = []
        for pid in pids:
            detail = get_project_detail(con, pid)
            tf = get_project_truth_flags(con, pid)
            if detail:
                comparisons.append({**detail, "truth_flags": tf})
            else:
                comparisons.append({"project_id": pid, "error": "not_found", "truth_flags": tf})
        return wrap_tool_response(
            comparisons,
            project_ids=pids,
            tables=["project_summaries", "noc_bu_records"],
            con=con,
        )

    @tool
    def trace_entity_network(project_id: int, depth: int = 2) -> Dict[str, Any]:
        """Trace cross-project relationships, shared professionals, and contagion risk in the knowledge graph."""
        pid = int(project_id)
        network = graph_engine.get_ego_network(pid, depth=depth)
        shared = graph_engine.find_shared_entities(pid)
        contagion = graph_engine.trace_contagion_risk(pid)
        payload = {
            "project_id": pid,
            "network": network,
            "shared_entities": shared,
            "contagion_risk_leads": contagion,
        }
        return wrap_tool_response(
            payload,
            project_ids=[pid],
            tables=["graph_nodes", "graph_edges"],
            con=con,
            max_tokens=4000,
        )

    @tool
    def get_promoter_portfolio(
        project_id: Optional[int] = None,
        promoter_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resolve complete developer portfolio with composite linkage and homonym warnings."""
        pid = int(project_id) if project_id is not None else None
        res = resolve_promoter_portfolio(con, project_id=pid, promoter_name=promoter_name)
        pids = [p["project_id"] for p in res.get("projects", []) if isinstance(p, dict) and "project_id" in p]
        return wrap_tool_response(
            res,
            project_ids=pids,
            tables=["projects", "project_summaries"],
            con=con,
        )

    tools = [
        search_projects,
        get_project_dossier,
        audit_discrepancies,
        verify_sales_claim,
        get_spatial_pricing_benchmark,
        compare_projects,
        trace_entity_network,
        get_promoter_portfolio,
    ]
    return tools, teardown
