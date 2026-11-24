"""Deterministic Specialist Subgraphs with Timeout & Concurrency Isolation.

Implements three forensic specialists:
1. DueDiligenceSpecialist: Truth flags, project summary, spatial empirical benchmark, and claim verification.
2. PilotAuditorSpecialist: Deep Section 4(2)(l)(D) escrow, cost drops, completion velocity, and SKIPPED_UNINGESTED detection.
3. PromoterContagionSpecialist: Cross-scheme entity network tracing, shared professionals, and cluster split detection.

Concurrency & Safety Invariants:
- Every specialist opens its own isolated `get_connection(db_path, read_only=True)` inside a `try...finally` block.
- Operations are guarded by `threading.Timer(timeout_s, con.interrupt)`.
- Catch-all exception handling yields structured partial error findings to protect the coordinator from failing.
- LLM summaries are capped at 1.5 KB JSON to prevent context window explosion.
- Specialist findings are strictly validated via Pydantic and returned as plain dicts.
"""

import json
import logging
import sqlite3
import statistics
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from ..analytics.audit import ProjectAuditor
from ..analytics.claims_checker import SalesClaimVerifier
from ..analytics.investor_dossier import generate_investor_dossier
from ..analytics.spatial_pricing import SpatialEmpiricalPricer
from ..db.database import DEFAULT_DB_PATH, get_connection
from ..db.queries import get_project_detail, get_project_truth_flags, get_zombie_radar_data
from ..db.redaction import redact_record
from ..graph.network import KnowledgeGraph, resolve_promoter_portfolio

logger = logging.getLogger(__name__)


class SpecialistFinding(BaseModel):
    """Structured, serializable finding returned by a forensic specialist."""

    specialist: str
    project_id: Optional[int] = None
    promoter_name: Optional[str] = None
    status: str = "ok"  # "ok", "partial", "error", "skipped"
    error: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    card_data: Optional[Dict[str, Any]] = None
    llm_summary: Dict[str, Any] = Field(default_factory=dict)
    requested_followups: List[Dict[str, Any]] = Field(default_factory=list)
    tool_call_count: int = 1


def _start_interrupt_timer(con: Any, timeout_s: float) -> Optional[threading.Timer]:
    """Start a daemon watchdog timer calling con.interrupt if supported by the connection."""
    interrupt_fn = getattr(con, "interrupt", None)
    if not callable(interrupt_fn):
        return None
    timer = threading.Timer(timeout_s, interrupt_fn)
    timer.daemon = True
    timer.start()
    return timer


def _truncate_summary(summary: Dict[str, Any], max_bytes: int = 1500) -> Dict[str, Any]:
    """Ensure summary JSON fits within max_bytes budget."""
    try:
        raw = json.dumps(summary)
        if len(raw.encode("utf-8")) <= max_bytes:
            return summary
        # If too large, return an abbreviated view
        return {
            "summary_abbreviated": True,
            "keys": list(summary.keys()),
            "status": summary.get("status", "ok"),
            "notice": f"Truncated to conform to {max_bytes} byte specialist budget.",
        }
    except Exception:
        return {"error": "Failed to serialize summary"}


def due_diligence_specialist(item: Dict[str, Any]) -> Dict[str, Any]:
    """Execute statutory due-diligence and empirical spatial benchmarking.

    Args:
        item: Task dictionary containing 'project_id', optional 'db_path',
              'timeout_s', and claim verification arguments.

    Returns:
        Graph state update with delta 'findings' list and 'tool_call_count'.
    """
    task = item.get("task", item)
    pid = task.get("project_id")
    if pid is None:
        finding = SpecialistFinding(
            specialist="due_diligence",
            status="error",
            error="Missing project_id in due diligence task",
            tool_call_count=0,
        )
        return {"findings": [finding.model_dump()], "tool_call_count": 0}

    pid = int(pid)
    db_path = task.get("db_path") or DEFAULT_DB_PATH
    timeout_s = float(task.get("timeout_s", 8.0))
    claimed_price = task.get("claimed_price")
    claimed_type = task.get("claimed_type", "price_per_sqft")
    asset_class = task.get("asset_class", "Residential")

    con = get_connection(db_path, read_only=True)
    timer = _start_interrupt_timer(con, timeout_s)

    calls = 0
    try:
        truth_flags = get_project_truth_flags(con, pid)
        detail = get_project_detail(con, pid)
        calls += 1

        dossier_text = generate_investor_dossier(con, pid)
        pricer = SpatialEmpiricalPricer(con)
        spatial = pricer.benchmark(pid, asset_class=asset_class)
        calls += 1

        claim_res = None
        if claimed_price is not None:
            verifier = SalesClaimVerifier(con)
            claim_res = verifier.verify_claim(
                pid,
                claimed_rate_sqft=float(claimed_price) if claimed_type != "absorption_pct" else None,
                claimed_sold_pct=float(claimed_price) if claimed_type == "absorption_pct" else None,
                asset_class=asset_class,
            )
            calls += 1

        p_info = detail.get("project", {}) if (detail and isinstance(detail.get("project"), dict)) else (detail or {})
        project_name = p_info.get("name") or p_info.get("project_name") or f"Project {pid}"
        promoter = truth_flags.get("promoter_name") or p_info.get("promoter_name")
        district = p_info.get("district")
        total_units = p_info.get("total_units")
        carpet_sqft = p_info.get("total_carpet_area_sqm") or p_info.get("carpet_area_sqft")

        # Check followups to request
        followups: List[Dict[str, Any]] = []
        if promoter:
            followups.append({
                "specialist": "promoter_contagion",
                "promoter_name": promoter,
                "project_id": pid,
            })

        tier = truth_flags.get("data_tier")
        if tier == "pilot_deep" or task.get("audit_requested"):
            followups.append({
                "specialist": "pilot_auditor",
                "project_id": pid,
            })

        # Structured card data for A2UI
        card_data = {
            "dossier_truth": {
                "project_id": pid,
                "project_name": project_name,
                "promoter_name": promoter,
                "district": district,
                "truth_flags": truth_flags,
                "approved_units": total_units,
                "carpet_sqft": carpet_sqft,
            },
            "spatial_comps": {
                "project_id": pid,
                "benchmark": spatial,
            },
        }
        _CLAIM_VERDICT_MAP = {
            "VERIFIED IN MARKET RANGE": "SUPPORTED",
            "DISCOUNTED": "SUPPORTED",
            "EXAGGERATED / PREMIUM": "EXAGGERATED",
            "INSUFFICIENT DATA": "UNVERIFIABLE",
            "ARTIFICIAL SCARCITY": "DISPUTED",
            "AGGRESSIVE SALES PROMISE": "DISPUTED",
            "VERIFIED ACCURATE": "SUPPORTED",
            "ALIGNED WITH RERA": "SUPPORTED",
        }

        claim_card_payload = None
        if claim_res is not None:
            checks = claim_res.get("verification_checks") or []
            primary_check = next(
                (c for c in checks if isinstance(c, dict) and c.get("metric") == "Price per Sq.Ft"),
                checks[0] if checks and isinstance(checks[0], dict) else None,
            )
            if primary_check:
                raw_verdict = str(primary_check.get("verdict") or "").strip().upper()
                mapped_verdict = _CLAIM_VERDICT_MAP.get(
                    raw_verdict,
                    "DISPUTED" if "CONTRADICT" in raw_verdict else "UNVERIFIABLE",
                )
                emp_median = primary_check.get("empirical_median")
                spread_pct = primary_check.get("spread_pct")
                deed_count = int(primary_check.get("deed_count") or 0)
                stale = bool(primary_check.get("stale_deed_warning", False))
                if deed_count >= 10 and not stale:
                    confidence = "HIGH"
                elif deed_count >= 3:
                    confidence = "MEDIUM"
                else:
                    confidence = "LOW"
                summary_txt = str(
                    primary_check.get("detail")
                    or primary_check.get("statutory_actual")
                    or f"Claim verdict: {mapped_verdict}"
                ).strip()
            else:
                mapped_verdict = "UNVERIFIABLE"
                emp_median = None
                spread_pct = None
                confidence = "LOW"
                summary_txt = str(
                    claim_res.get("error")
                    or f"Insufficient registered deed data to verify claimed rate for project {pid}."
                ).strip()

            claim_card_payload = {
                "project_id": pid,
                "verdict": mapped_verdict,
                "claim_type": claimed_type,
                "claimed_value": float(claimed_price),
                "empirical_median": emp_median,
                "spread_pct": spread_pct,
                "confidence": confidence,
                "summary": summary_txt,
                "result": claim_res,
            }
            card_data["claim_verdict"] = claim_card_payload

        llm_summary = _truncate_summary({
            "project_id": pid,
            "project_name": project_name,
            "promoter_name": promoter,
            "truth_flags": truth_flags,
            "spatial_median": spatial.get("median_rate_sqft"),
            "spatial_iqr": [spatial.get("p25"), spatial.get("p75")],
            "claim_verdict": claim_card_payload.get("verdict") if claim_card_payload else None,
            "claimed_price": claim_card_payload.get("claimed_value") if claim_card_payload else None,
            "claim_empirical_median": claim_card_payload.get("empirical_median") if claim_card_payload else None,
            "claim_spread_pct": claim_card_payload.get("spread_pct") if claim_card_payload else None,
            "claim_summary": claim_card_payload.get("summary") if claim_card_payload else None,
        })

        finding = SpecialistFinding(
            specialist="due_diligence",
            project_id=pid,
            status="ok",
            data={
                "truth_flags": truth_flags,
                "detail": detail,
                "dossier_text": dossier_text,
                "spatial": spatial,
                "claim_verification": claim_res,
            },
            card_data=card_data,
            llm_summary=llm_summary,
            requested_followups=followups,
            tool_call_count=calls,
        )
        return {"findings": [finding.model_dump()], "tool_call_count": calls}

    except Exception as e:
        logger.warning(f"Due diligence specialist failed for project {pid}: {e}")
        err_msg = str(e) or "Execution error or query interrupted"
        finding = SpecialistFinding(
            specialist="due_diligence",
            project_id=pid,
            status="error",
            error=err_msg,
            llm_summary={"project_id": pid, "error": err_msg},
            tool_call_count=max(calls, 1),
        )
        return {"findings": [finding.model_dump()], "tool_call_count": max(calls, 1)}
    finally:
        if timer is not None:
            timer.cancel()
        try:
            con.close()
        except Exception:
            pass


def pilot_auditor_specialist(item: Dict[str, Any]) -> Dict[str, Any]:
    """Execute deep forensic audit on statutory filings (Form 1/3/5, cost drops, velocity).

    Args:
        item: Task dictionary containing 'project_id', optional 'db_path', and 'timeout_s'.

    Returns:
        Graph state update with delta 'findings' list and 'tool_call_count'.
    """
    task = item.get("task", item)
    pid = task.get("project_id")
    if pid is None:
        finding = SpecialistFinding(
            specialist="pilot_auditor",
            status="error",
            error="Missing project_id in pilot auditor task",
            tool_call_count=0,
        )
        return {"findings": [finding.model_dump()], "tool_call_count": 0}

    pid = int(pid)
    db_path = task.get("db_path") or DEFAULT_DB_PATH
    timeout_s = float(task.get("timeout_s", 8.0))

    con = get_connection(db_path, read_only=True)
    timer = _start_interrupt_timer(con, timeout_s)

    calls = 0
    try:
        auditor = ProjectAuditor(con)
        leads = auditor.audit_project(pid, include_skipped=True)
        calls += 1

        lead_dicts = [
            {
                "category": getattr(l, "category", ""),
                "severity": getattr(l, "severity", ""),
                "title": getattr(l, "title", ""),
                "detail": getattr(l, "detail", ""),
                "evidence_source": getattr(l, "evidence_source", ""),
                "reconciliation_guidance": getattr(l, "reconciliation_guidance", ""),
            }
            for l in leads
        ]

        has_skipped = any("SKIPPED_UNINGESTED" in (l.get("severity", "") + l.get("title", "")) for l in lead_dicts)
        critical_count = sum(1 for l in lead_dicts if l.get("severity") == "CRITICAL")
        high_count = sum(1 for l in lead_dicts if l.get("severity") == "HIGH")

        card_data = {
            "audit_leads": {
                "project_id": pid,
                "total_leads": len(lead_dicts),
                "critical_count": critical_count,
                "high_count": high_count,
                "has_skipped_uningested": has_skipped,
                "leads": lead_dicts[:10],
            }
        }

        llm_summary = _truncate_summary({
            "project_id": pid,
            "total_leads": len(lead_dicts),
            "critical_count": critical_count,
            "high_count": high_count,
            "has_skipped_uningested": has_skipped,
            "top_leads": [
                {"title": l.get("title"), "severity": l.get("severity"), "detail": l.get("detail")}
                for l in lead_dicts[:5]
            ],
        })

        finding = SpecialistFinding(
            specialist="pilot_auditor",
            project_id=pid,
            status="ok",
            data={
                "discrepancies": lead_dicts,
                "has_skipped_uningested": has_skipped,
                "critical_count": critical_count,
                "high_count": high_count,
            },
            card_data=card_data,
            llm_summary=llm_summary,
            tool_call_count=calls,
        )
        return {"findings": [finding.model_dump()], "tool_call_count": calls}

    except Exception as e:
        logger.warning(f"Pilot auditor specialist failed for project {pid}: {e}")
        err_msg = str(e) or "Execution error or query interrupted"
        finding = SpecialistFinding(
            specialist="pilot_auditor",
            project_id=pid,
            status="error",
            error=err_msg,
            llm_summary={"project_id": pid, "error": err_msg},
            tool_call_count=max(calls, 1),
        )
        return {"findings": [finding.model_dump()], "tool_call_count": max(calls, 1)}
    finally:
        if timer is not None:
            timer.cancel()
        try:
            con.close()
        except Exception:
            pass


def promoter_contagion_specialist(item: Dict[str, Any]) -> Dict[str, Any]:
    """Execute developer portfolio resolution, contagion analysis, and cluster detection.

    Args:
        item: Task dictionary containing 'promoter_name' or 'project_id',
              optional 'db_path', and 'timeout_s'.

    Returns:
        Graph state update with delta 'findings' list and 'tool_call_count'.
    """
    task = item.get("task", item)
    pid = task.get("project_id")
    promoter_name = task.get("promoter_name")
    if pid is None and not promoter_name:
        finding = SpecialistFinding(
            specialist="promoter_contagion",
            status="error",
            error="Missing project_id and promoter_name in promoter contagion task",
            tool_call_count=0,
        )
        return {"findings": [finding.model_dump()], "tool_call_count": 0}

    pid = int(pid) if pid is not None else None
    db_path = task.get("db_path") or DEFAULT_DB_PATH
    timeout_s = float(task.get("timeout_s", 8.0))

    con = get_connection(db_path, read_only=True)
    timer = _start_interrupt_timer(con, timeout_s)

    calls = 0
    try:
        portfolio = resolve_promoter_portfolio(con, project_id=pid, promoter_name=promoter_name)
        calls += 1

        graph_engine = KnowledgeGraph(con)
        contagion_leads = []
        shared_entities = {}
        if pid:
            contagion_leads = graph_engine.trace_contagion_risk(pid)
            shared_entities = graph_engine.find_shared_entities(pid)
            calls += 1

        # Check for multi-cluster partitioning or homonyms
        clusters = portfolio.get("clusters", [])
        resolved_projects = portfolio.get("resolved_projects") or portfolio.get("projects") or []
        is_multi_cluster = portfolio.get("is_multi_cluster", False) or len(clusters) > 1

        card_data = None
        if is_multi_cluster or len(clusters) > 1:
            card_data = {
                "cluster_split": {
                    "promoter_name": promoter_name or portfolio.get("promoter_name"),
                    "clusters": clusters,
                    "is_multi_cluster": True,
                    "resolution": "PARTITIONED_MULTI_CLUSTER",
                }
            }

        llm_summary = _truncate_summary({
            "promoter_name": promoter_name or portfolio.get("promoter_name"),
            "project_id": pid,
            "total_schemes": portfolio.get("portfolio_count") or len(resolved_projects),
            "clusters_count": len(clusters),
            "is_multi_cluster": is_multi_cluster,
            "linkage_confidence": portfolio.get("linkage_confidence"),
            "contagion_leads_count": len(contagion_leads),
            "sample_pids": [p.get("project_id") for p in resolved_projects[:10] if isinstance(p, dict) and p.get("project_id")],
        })

        finding = SpecialistFinding(
            specialist="promoter_contagion",
            project_id=pid,
            promoter_name=promoter_name,
            status="ok",
            data={
                "portfolio": portfolio,
                "contagion_leads": contagion_leads,
                "shared_entities": shared_entities,
                "is_multi_cluster": is_multi_cluster,
            },
            card_data=card_data,
            llm_summary=llm_summary,
            tool_call_count=calls,
        )
        return {"findings": [finding.model_dump()], "tool_call_count": calls}

    except Exception as e:
        logger.warning(f"Promoter contagion specialist failed for promoter {promoter_name} / pid {pid}: {e}")
        err_msg = str(e) or "Execution error or query interrupted"
        finding = SpecialistFinding(
            specialist="promoter_contagion",
            project_id=pid,
            promoter_name=promoter_name,
            status="error",
            error=err_msg,
            llm_summary={"promoter_name": promoter_name, "error": err_msg},
            tool_call_count=max(calls, 1),
        )
        return {"findings": [finding.model_dump()], "tool_call_count": max(calls, 1)}
    finally:
        if timer is not None:
            timer.cancel()
        try:
            con.close()
        except Exception:
            pass


def _load_markup_spread_snapshot() -> Dict[str, Any]:
    """Load pre-computed markup_spread_snapshot.json safely with empty fallback."""
    candidates = [
        Path(__file__).resolve().parents[2] / "data" / "markup_spread_snapshot.json",
        Path(__file__).resolve().parents[3] / "data" / "markup_spread_snapshot.json",
    ]
    for p in candidates:
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


def market_analyst_specialist(item: Dict[str, Any]) -> Dict[str, Any]:
    """Screen indexed project_summaries and macro market metrics without scanning unit_transactions.

    Args:
        item: Task dictionary containing optional 'district', 'project_type',
              'min_price', 'max_price', 'min_absorption', 'db_path', and 'timeout_s'.

    Returns:
        Graph state update with delta 'findings' list and 'tool_call_count'.
    """
    task = item.get("task", item)
    district = task.get("district")
    project_type = task.get("project_type")
    min_price = task.get("min_price")
    max_price = task.get("max_price")
    min_absorption = task.get("min_absorption")
    db_path = task.get("db_path") or DEFAULT_DB_PATH
    timeout_s = float(task.get("timeout_s", 8.0))

    con = get_connection(db_path, read_only=True)
    timer = _start_interrupt_timer(con, timeout_s)

    calls = 0
    try:
        where_clauses: List[str] = []
        params: List[Any] = []
        if district and str(district).strip():
            where_clauses.append("LOWER(district) = LOWER(?)")
            params.append(str(district).strip())
        if project_type and str(project_type).strip() and str(project_type).strip().lower() not in ("all", "any"):
            where_clauses.append("LOWER(project_type) LIKE LOWER(?)")
            params.append(f"%{str(project_type).strip()}%")
        if min_price is not None:
            where_clauses.append("avg_rate_sqft_booked >= ?")
            params.append(float(min_price))
        if max_price is not None:
            where_clauses.append("avg_rate_sqft_booked <= ?")
            params.append(float(max_price))
        if min_absorption is not None:
            where_clauses.append("absorption_pct >= ?")
            params.append(float(min_absorption))

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        agg_row = con.execute(
            f"SELECT COUNT(*), AVG(absorption_pct) FROM project_summaries {where_sql}",
            params,
        ).fetchone()
        screen_count = int(agg_row[0] or 0) if agg_row else 0
        avg_abs_raw = agg_row[1] if agg_row else None
        avg_absorption_pct = round(float(avg_abs_raw), 1) if avg_abs_raw is not None else None

        rate_rows = con.execute(
            f"SELECT avg_rate_sqft_booked FROM project_summaries {where_sql}"
            + (" AND " if where_sql else " WHERE ")
            + "avg_rate_sqft_booked IS NOT NULL AND avg_rate_sqft_booked > 0",
            params,
        ).fetchall()
        rates = [float(r[0]) for r in rate_rows if r[0] is not None]
        district_median_price = round(float(statistics.median(rates)), 2) if rates else None

        screen_rows = con.execute(
            f"""
            SELECT project_id, name, district, project_type, avg_rate_sqft_booked, absorption_pct, booked_units
            FROM project_summaries
            {where_sql}
            ORDER BY COALESCE(booked_units, 0) DESC, project_id ASC
            LIMIT 15
            """,
            params,
        ).fetchall()
        calls += 1

        snapshot = _load_markup_spread_snapshot()
        markup_raw = snapshot.get("empirical_markup_pct", snapshot.get("statewide_baseline_markup_pct"))
        markup_spread_pct = round(float(markup_raw), 2) if markup_raw is not None else None

        zombies = get_zombie_radar_data(con, limit=200)
        if district and str(district).strip():
            d_lower = str(district).strip().lower()
            zombie_count = sum(1 for z in zombies if str(z.get("district") or "").strip().lower() == d_lower)
        else:
            zombie_count = len(zombies)
        calls += 1

        aggregates: Dict[str, Dict[str, Any]] = {
            "screen_count": {"value": int(screen_count), "label": "Matched Projects", "unit": "projects"},
            "district_median_price": {"value": district_median_price, "label": "Median Booked Rate", "unit": "INR/sqft"},
            "avg_absorption_pct": {"value": avg_absorption_pct, "label": "Average Absorption", "unit": "%"},
            "markup_spread_pct": {"value": markup_spread_pct, "label": "Unbooked Markup Spread", "unit": "%"},
            "zombie_count": {"value": int(zombie_count), "label": "Expired Without BU Schemes", "unit": "projects"},
        }

        screened_projects: List[Dict[str, Any]] = []
        table_rows: List[Dict[str, Any]] = []
        for idx, r in enumerate(screen_rows):
            rd = dict(r)
            pid = int(rd["project_id"])
            tf = get_project_truth_flags(con, pid)
            avg_px = round(float(rd["avg_rate_sqft_booked"]), 2) if rd.get("avg_rate_sqft_booked") is not None else None
            abs_pct = round(float(rd["absorption_pct"]), 1) if rd.get("absorption_pct") is not None else None
            row_obj = redact_record({
                "project_id": pid,
                "name": rd.get("name") or f"Project {pid}",
                "district": rd.get("district"),
                "project_type": rd.get("project_type"),
                "avg_price_sqft": avg_px,
                "absorption_pct": abs_pct,
                "status_badge": tf.get("status_badge", ""),
            })
            screened_projects.append({**row_obj, "truth_flags": tf})
            if idx < 10:
                table_rows.append(row_obj)

        dist_label = str(district).strip() if district and str(district).strip() else None
        ptype_label = str(project_type).strip() if project_type and str(project_type).strip() else None

        card_data = {
            "market_screen": {
                "district": dist_label,
                "project_type": ptype_label,
                "total_matched": int(screen_count),
                "rows": table_rows,
            },
            "market_stats": {
                "district": dist_label,
                "aggregates": aggregates,
            },
        }

        llm_summary = _truncate_summary({
            "district": dist_label or "Statewide",
            "project_type": ptype_label or "All",
            "aggregates": {k: v["value"] for k, v in aggregates.items()},
            "top_projects": [
                {
                    "project_id": p["project_id"],
                    "name": p["name"],
                    "avg_price_sqft": p["avg_price_sqft"],
                    "absorption_pct": p["absorption_pct"],
                }
                for p in table_rows[:5]
            ],
        })

        finding = SpecialistFinding(
            specialist="market_analyst",
            status="ok",
            data={
                "district": dist_label,
                "project_type": ptype_label,
                "aggregates": aggregates,
                "screened_projects": screened_projects,
            },
            card_data=card_data,
            llm_summary=llm_summary,
            tool_call_count=calls,
        )
        return {"findings": [finding.model_dump()], "tool_call_count": calls}

    except Exception as e:
        logger.warning(f"Market analyst specialist failed: {e}")
        err_msg = str(e) or "Execution error or query interrupted"
        finding = SpecialistFinding(
            specialist="market_analyst",
            status="error",
            error=err_msg,
            llm_summary={"error": err_msg},
            tool_call_count=max(calls, 1),
        )
        return {"findings": [finding.model_dump()], "tool_call_count": max(calls, 1)}
    finally:
        if timer is not None:
            timer.cancel()
        try:
            con.close()
        except Exception:
            pass
