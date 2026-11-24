"""A2UI 1.0 Surface Builder & Spec Emitter.

Generates spec-compliant A2UI 1.0 UI surfaces for frontend consumption:
- Enforces version: "1.0"
- Guarantees unique scoped surfaceId: f"{card_type}_{entity_id}_{run_id}"
- Inline components with single root component "id": "root"
- PII-scrubbed string leaves preserving envelope structure
"""

import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .guardrails import _scrub_text


class A2UIComponent(BaseModel):
    """Inline component tree root conforming to A2UI 1.0 specification."""

    id: str = "root"
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class A2UISurface(BaseModel):
    """Server-bound A2UI 1.0 surface descriptor."""

    version: str = "1.0"
    surfaceId: str
    component: A2UIComponent


def _scrub_leaves(obj: Any) -> Any:
    """Recursively scrub PII from string values without modifying dict keys or numbers."""
    if isinstance(obj, str):
        return _scrub_text(obj)
    if isinstance(obj, dict):
        return {k: _scrub_leaves(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub_leaves(item) for item in obj]
    return obj


def build_a2ui_surfaces(
    findings: List[Dict[str, Any]],
    run_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Transform specialist findings into validated A2UI 1.0 surfaces.

    Args:
        findings: List of specialist findings dictionaries.
        run_id: Unique invocation or turn identifier.

    Returns:
        List of serialized A2UI 1.0 surface dictionaries.
    """
    rid = run_id or uuid.uuid4().hex[:8]
    surfaces: List[Dict[str, Any]] = []
    emitted_surface_ids = set()

    for finding in findings:
        card_data = finding.get("card_data")
        if not card_data or not isinstance(card_data, dict):
            continue

        # 1. DossierTruthCard
        if "dossier_truth" in card_data:
            data = card_data["dossier_truth"]
            pid = data.get("project_id", "unknown")
            sid = f"dossier_truth_{pid}_{rid}"
            if sid not in emitted_surface_ids:
                surface = A2UISurface(
                    surfaceId=sid,
                    component=A2UIComponent(
                        type="DossierTruthCard",
                        properties=_scrub_leaves(data),
                    ),
                )
                surfaces.append(surface.model_dump())
                emitted_surface_ids.add(sid)

        # 2. SpatialCompsCard
        if "spatial_comps" in card_data:
            data = card_data["spatial_comps"]
            pid = data.get("project_id", "unknown")
            sid = f"spatial_comps_{pid}_{rid}"
            if sid not in emitted_surface_ids:
                bench = data.get("benchmark", {})
                props = {
                    "project_id": pid,
                    "median_rate_sqft": bench.get("median_rate_sqft"),
                    "p25": bench.get("p25"),
                    "p75": bench.get("p75"),
                    "iqr": bench.get("iqr"),
                    "sample_size": bench.get("sample_size", 0),
                    "benchmark_tier": bench.get("benchmark_tier"),
                    "unbooked_markup_pct": bench.get("unbooked_markup_pct"),
                    "statewide_markup_baseline_pct": bench.get("statewide_markup_baseline_pct", 12.63),
                }
                surface = A2UISurface(
                    surfaceId=sid,
                    component=A2UIComponent(
                        type="SpatialCompsCard",
                        properties=_scrub_leaves(props),
                    ),
                )
                surfaces.append(surface.model_dump())
                emitted_surface_ids.add(sid)

        # 3. ClaimVerdictCard
        if "claim_verdict" in card_data:
            data = card_data["claim_verdict"]
            pid = data.get("project_id", "unknown")
            sid = f"claim_verdict_{pid}_{rid}"
            if sid not in emitted_surface_ids:
                res = data.get("result", {}) if isinstance(data.get("result"), dict) else {}
                emp_med = data.get("empirical_median")
                if emp_med is None:
                    emp_med = res.get("empirical_median")
                spread_val = data.get("spread_pct")
                if spread_val is None:
                    spread_val = res.get("spread_pct")
                summary_val = data.get("summary") or res.get("summary") or (
                    f"Claimed {data.get('claim_type', 'price_per_sqft')} evaluated as {data.get('verdict') or 'UNVERIFIABLE'}."
                )
                props = {
                    "project_id": pid,
                    "claim_type": data.get("claim_type", "price_per_sqft"),
                    "claimed_value": data.get("claimed_value", 0.0),
                    "verdict": data.get("verdict") or "UNVERIFIABLE",
                    "empirical_median": emp_med,
                    "spread_pct": spread_val,
                    "confidence": data.get("confidence") or res.get("confidence") or "LOW",
                    "summary": summary_val,
                }
                surface = A2UISurface(
                    surfaceId=sid,
                    component=A2UIComponent(
                        type="ClaimVerdictCard",
                        properties=_scrub_leaves(props),
                    ),
                )
                surfaces.append(surface.model_dump())
                emitted_surface_ids.add(sid)

        # 4. ClusterSplitCard
        if "cluster_split" in card_data:
            data = card_data["cluster_split"]
            p_name = data.get("promoter_name") or "promoter"
            safe_name = str(p_name).lower().replace(" ", "_")[:24]
            sid = f"cluster_split_{safe_name}_{rid}"
            if sid not in emitted_surface_ids:
                props = {
                    "promoter_name": p_name,
                    "resolution": data.get("resolution", "PARTITIONED_MULTI_CLUSTER"),
                    "is_multi_cluster": data.get("is_multi_cluster", True),
                    "clusters": data.get("clusters", []),
                }
                surface = A2UISurface(
                    surfaceId=sid,
                    component=A2UIComponent(
                        type="ClusterSplitCard",
                        properties=_scrub_leaves(props),
                    ),
                )
                surfaces.append(surface.model_dump())
                emitted_surface_ids.add(sid)

        # 5. AuditLeadsCard
        if "audit_leads" in card_data:
            data = card_data["audit_leads"]
            pid = data.get("project_id", "unknown")
            sid = f"audit_leads_{pid}_{rid}"
            if sid not in emitted_surface_ids:
                props = {
                    "project_id": pid,
                    "total_leads": data.get("total_leads", 0),
                    "critical_count": data.get("critical_count", 0),
                    "high_count": data.get("high_count", 0),
                    "has_skipped_uningested": data.get("has_skipped_uningested", False),
                    "leads": data.get("leads", []),
                }
                surface = A2UISurface(
                    surfaceId=sid,
                    component=A2UIComponent(
                        type="AuditLeadsCard",
                        properties=_scrub_leaves(props),
                    ),
                )
                surfaces.append(surface.model_dump())
                emitted_surface_ids.add(sid)

        # 6. ProjectDisambiguationCard
        if "disambiguation" in card_data:
            data = card_data["disambiguation"]
            sid = f"disambig_{rid}"
            if sid not in emitted_surface_ids:
                props = {
                    "query": data.get("query", ""),
                    "match_type": data.get("match_type", "exact"),
                    "candidates": (data.get("candidates") or [])[:5],
                    "allow_other": bool(data.get("allow_other", True)),
                    "other_label": data.get("other_label", "Other (type something else)"),
                }
                surface = A2UISurface(
                    surfaceId=sid,
                    component=A2UIComponent(
                        type="ProjectDisambiguationCard",
                        properties=_scrub_leaves(props),
                    ),
                )
                surfaces.append(surface.model_dump())
                emitted_surface_ids.add(sid)

        # 7. MarketScreenTable
        if "market_screen" in card_data:
            data = card_data["market_screen"]
            dist = data.get("district") or "statewide"
            safe_dist = str(dist).lower().replace(" ", "_")[:24]
            sid = f"market_screen_{safe_dist}_{rid}"
            if sid not in emitted_surface_ids:
                props = {
                    "district": data.get("district"),
                    "project_type": data.get("project_type"),
                    "total_matched": data.get("total_matched", 0),
                    "rows": (data.get("rows") or [])[:10],
                }
                surface = A2UISurface(
                    surfaceId=sid,
                    component=A2UIComponent(
                        type="MarketScreenTable",
                        properties=_scrub_leaves(props),
                    ),
                )
                surfaces.append(surface.model_dump())
                emitted_surface_ids.add(sid)

        # 8. MarketStatsCard
        if "market_stats" in card_data:
            data = card_data["market_stats"]
            dist = data.get("district") or "statewide"
            safe_dist = str(dist).lower().replace(" ", "_")[:24]
            sid = f"market_stats_{safe_dist}_{rid}"
            if sid not in emitted_surface_ids:
                props = {
                    "district": data.get("district"),
                    "aggregates": data.get("aggregates") or {},
                }
                surface = A2UISurface(
                    surfaceId=sid,
                    component=A2UIComponent(
                        type="MarketStatsCard",
                        properties=_scrub_leaves(props),
                    ),
                )
                surfaces.append(surface.model_dump())
                emitted_surface_ids.add(sid)

    return surfaces
