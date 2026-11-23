"""Model Context Protocol (MCP) standardized response envelope.

Enforces sovereign response envelope across all MCP tools:
{
    "data": ...,
    "data_coverage": {
        "coverage_tier": "pilot_deep_audit" | "statewide_core",
        "tier": "pilot_deep_audit" | "statewide_core",
        "is_legacy_grandfathered": bool,
        "is_govt_authority": bool,
        "caveats": [...],
        "warning": str | None
    },
    "provenance": {
        "source_tables": [...],
        "query_project_ids": [...],
        "timestamp_utc": "..."
    },
    "pagination": {
        "offset": int,
        "limit": int,
        "total": int,
        "truncated": bool
    },
    "token_estimate": int
}
"""

import json
import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Union

from ..db.redaction import redact_payload

# 9 deep audit pilot seed projects with comprehensive statutory Form 1-5 filings
DEEP_AUDIT_IDS = {13560, 13705, 16104, 16562, 17255, 17830, 17855, 20523, 24508}

# Tables populated exclusively for the 9 pilot projects
TINY_PILOT_TABLES = {
    "applications",
    "documents_catalog",
    "document_jobs",
    "finances",
    "form5_compliance",
    "inventory_blocks",
    "previous_projects",
    "promoters",
    "quarterly_timeline",
}

GOVT_AUTHORITY_REGEX = re.compile(
    r"\b(VUDA|AUDA|SUDA|RUDA|GIDC|PMAY|GHB|GUJARAT HOUSING BOARD|URBAN DEVELOPMENT AUTHORITY)\b",
    re.IGNORECASE,
)


def estimate_tokens(payload: Any) -> int:
    """Accurately estimate token count for JSON payload (4 characters per token heuristic)."""
    try:
        raw = json.dumps(payload, default=str)
        return max(1, math.ceil(len(raw) / 4.0))
    except Exception:
        return 1


def wrap_tool_response(
    data: Any,
    *,
    project_ids: Sequence[int],
    tables: Sequence[str],
    con: Any = None,
    pagination: Optional[Dict[str, Any]] = None,
    max_tokens: int = 6000,
) -> Dict[str, Any]:
    """Wrap tool payload in standard sovereign MCP envelope with PII redaction and token caps.

    Args:
        data: Raw tool return payload (dict, list, or primitive).
        project_ids: List of GujRERA project IDs queried.
        tables: List of database tables accessed.
        con: Optional SQLite connection to look up project cohort flags.
        pagination: Optional dict with pagination metadata (offset, limit, total, truncated).
        max_tokens: Maximum token ceiling (default 6,000; graph payloads capped at 4,000).

    Returns:
        Structured envelope dict with data, data_coverage, provenance, pagination, token_estimate.
    """
    pids = [int(p) for p in (project_ids or []) if p is not None]
    tbls = [str(t) for t in (tables or []) if t is not None]

    # 1. Detect coverage tier
    if pids and all(pid in DEEP_AUDIT_IDS for pid in pids):
        coverage_tier = "pilot_deep_audit"
    else:
        coverage_tier = "statewide_core"

    # 2. Compute cohort & statutory entity caveats
    is_legacy = False
    is_govt = False
    caveats: List[str] = []

    if con is not None and pids:
        try:
            placeholders = ",".join("?" for _ in pids)
            rows = con.execute(
                f"SELECT project_id, name, promoter_name, completion_date FROM projects WHERE project_id IN ({placeholders})",
                pids,
            ).fetchall()
            for r in rows:
                comp = str(r["completion_date"] or "").strip()
                if comp[:4].isdigit() and int(comp[:4]) <= 2019:
                    is_legacy = True
                pname = str(r["promoter_name"] or "")
                proj_name = str(r["name"] or "")
                if GOVT_AUTHORITY_REGEX.search(pname) or GOVT_AUTHORITY_REGEX.search(proj_name):
                    is_govt = True
        except Exception:
            pass

    if is_legacy:
        caveats.append(
            "Project completed <= 2019 under grandfathered pre-RERA regime; Form 1-5 filing histories may be absent or partial."
        )
    if is_govt:
        caveats.append(
            "Project promoted by statutory urban development / housing authority; commercial escrow and private promoter default rules do not apply."
        )

    # Note if tiny pilot tables were queried for statewide projects
    pilot_queried = sorted(set(tbls) & TINY_PILOT_TABLES)
    if pilot_queried and coverage_tier == "statewide_core":
        caveats.append(
            f"Statutory filing tables ({', '.join(pilot_queried)}) are only populated for 9 pilot deep-audit projects statewide."
        )

    # 3. Apply PII redaction
    redacted_data = redact_payload(data)

    # 4. Token limit & truncation enforcement
    is_graph = (
        "graph_nodes" in tbls
        or "graph_edges" in tbls
        or (isinstance(redacted_data, dict) and "nodes" in redacted_data and "edges" in redacted_data)
    )
    effective_max_tokens = min(max_tokens, 4000) if is_graph else max_tokens

    is_truncated = False
    if estimate_tokens(redacted_data) > effective_max_tokens:
        if isinstance(redacted_data, list):
            # Cleanly truncate list items
            low, high = 1, len(redacted_data)
            best_idx = 1
            while low <= high:
                mid = (low + high) // 2
                if estimate_tokens(redacted_data[:mid]) <= effective_max_tokens:
                    best_idx = mid
                    low = mid + 1
                else:
                    high = mid - 1
            redacted_data = redacted_data[:best_idx]
            is_truncated = True

        elif isinstance(redacted_data, dict):
            if "nodes" in redacted_data and "edges" in redacted_data:
                # Graph truncation: truncate edges first, then cull dangling non-root nodes
                edges = list(redacted_data.get("edges", []))
                nodes = list(redacted_data.get("nodes", []))
                while edges and estimate_tokens({**redacted_data, "edges": edges, "nodes": nodes}) > effective_max_tokens:
                    new_len = max(0, min(len(edges) - 1, int(len(edges) * 0.8)))
                    edges = edges[:new_len]
                referenced_ids = {e.get("src_id") for e in edges} | {e.get("dst_id") for e in edges}
                nodes = [
                    n for n in nodes
                    if n.get("id") in referenced_ids or str(n.get("id", "")).startswith("project:")
                ]
                redacted_data["edges"] = edges
                redacted_data["nodes"] = nodes
                redacted_data["truncated"] = True
                is_truncated = True
            else:
                # Truncate largest list field inside dict if present
                candidate_key = None
                max_len = 0
                for k, v in redacted_data.items():
                    if isinstance(v, list) and len(v) > max_len:
                        max_len = len(v)
                        candidate_key = k

                if candidate_key and max_len > 1:
                    l_val = list(redacted_data[candidate_key])
                    while l_val and estimate_tokens({**redacted_data, candidate_key: l_val}) > effective_max_tokens:
                        new_len = max(0, min(len(l_val) - 1, int(len(l_val) * 0.8)))
                        l_val = l_val[:new_len]
                    redacted_data[candidate_key] = l_val
                    is_truncated = True
                elif isinstance(redacted_data.get("dossier_markdown"), str):
                    redacted_data["dossier_markdown"] = (
                        redacted_data["dossier_markdown"][: effective_max_tokens * 4]
                        + "\n\n... [TRUNCATED DUE TO TOKEN LIMIT]"
                    )
                    is_truncated = True
                else:
                    is_truncated = True

    # 5. Format pagination block
    if pagination:
        pag_dict = dict(pagination)
        pag_dict["truncated"] = is_truncated or pag_dict.get("truncated", False)
    else:
        total_count = len(data) if isinstance(data, list) else 1
        current_count = len(redacted_data) if isinstance(redacted_data, list) else 1
        pag_dict = {
            "offset": 0,
            "limit": current_count,
            "total": total_count,
            "truncated": is_truncated,
        }

    # 6. Final token estimate
    tok_est = estimate_tokens(redacted_data)

    return {
        "data": redacted_data,
        "data_coverage": {
            "coverage_tier": coverage_tier,
            "tier": coverage_tier,
            "is_legacy_grandfathered": is_legacy,
            "is_govt_authority": is_govt,
            "caveats": caveats,
            "warning": "; ".join(caveats) if caveats else None,
        },
        "provenance": {
            "source_tables": tbls,
            "query_project_ids": pids,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        },
        "pagination": pag_dict,
        "token_estimate": tok_est,
    }
