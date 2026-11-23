"""FastAPI serverless entrypoint and API router for GujRERA Intelligence.

Deployable to Vercel Serverless Functions (@vercel/python) and runnable locally via Uvicorn.
Supports:
- /api/health: Probe returning database status and total project count
- /api/map/pins: Compact 6-tuple map coordinate feed (< 380 KB)
- /api/explore: High-speed server-paginated project exploration
- /api/projects: Catalog for dropdowns and project navigation
- /api/project/{pid}: Institutional dossier data with graceful statewide fallbacks
- /api/pricing/{pid}: Longitudinal price summary and transaction trends
- /api/graph: Network nodes and edges for Vis.js / ego-network exploration
- /api/analytics/survival: Semi-parametric Cox Proportional Hazards delay forecast
- /api/analytics/pricing_trend: Multi-year registered deeds appreciation & CAGR
- /api/analytics/ml_pricing: Hedonic GBDT ML pricing model with Tree SHAP
- /api/verify_claim: Statutory claim verification against certified filings
- /api/search: Full-text search across Form 1/2/3 statutory filings
- /api/map/config: MapTiler proxy availability probe
- /api/maptiler/{path}: Upstream MapTiler vector tile & style proxy
- /api/copilot: Dual-mode statutory copilot (Agentic LLM with deterministic local fallback)
- Static asset delivery for sovereign offline frontend
"""

import http.client
import json
import logging
import math
import os
import sys
import threading
from collections import OrderedDict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastmcp.utilities.lifespan import combine_lifespans

logger = logging.getLogger(__name__)

# Ensure real_estate_intelligence package is discoverable
pkg_root = Path(__file__).resolve().parent.parent / "real_estate_intelligence"
if pkg_root.exists() and str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

from real_estate_intelligence.analytics.audit import ProjectAuditor
from real_estate_intelligence.analytics.claims_checker import SalesClaimVerifier
from real_estate_intelligence.analytics.pricing import PricingIntelligence
from real_estate_intelligence.analytics.spatial_pricing import SpatialEmpiricalPricer
from real_estate_intelligence.agent.copilot import AgenticCopilot, handle_copilot_query
from real_estate_intelligence.config import DEFAULT_DB_PATH
from real_estate_intelligence.db.database import get_connection
from real_estate_intelligence.db.queries import (
    SORT_COLUMN_MAP,
    get_developer_clusters_data,
    get_explore_facets,
    get_explore_rows,
    get_graph_data,
    get_map_pins,
    get_markup_spread_data,
    get_project_detail,
    get_project_truth_flags,
    get_projects_list,
    get_zombie_radar_data,
    normalize_data_tier,
    search_project_summaries,
    sort_explore_rows,
)
from real_estate_intelligence.db.redaction import redact_payload
from real_estate_intelligence.documents.search import DocumentSearchEngine
from real_estate_intelligence.graph.network import KnowledgeGraph
from real_estate_intelligence.mcp.fastmcp_app import mcp
from real_estate_intelligence.mcp.server import RealEstateIntelligenceMCP


class AppState:
    db_path: Optional[Any] = None
    con: Any = None
    pricing_engine: Any = None
    verifier: Any = None
    auditor: Any = None
    spatial_pricer: Any = None
    search_engine: Any = None
    graph_engine: Any = None
    mcp_server: Any = None
    agentic_copilot: Optional[AgenticCopilot] = None
    markup_spread_cache: Optional[Dict[str, Any]] = None
    zombie_radar_cache: Optional[List[Dict[str, Any]]] = None
    developer_clusters_cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

    @classmethod
    def setup_backends(cls, db_path: Optional[Any] = None, read_only: bool = True) -> None:
        cls.db_path = db_path
        cls.con = get_connection(db_path, read_only=read_only)
        cls.pricing_engine = PricingIntelligence(cls.con)
        cls.verifier = SalesClaimVerifier(cls.con)
        cls.auditor = ProjectAuditor(cls.con)
        cls.spatial_pricer = SpatialEmpiricalPricer(cls.con)
        cls.search_engine = DocumentSearchEngine(cls.con)
        cls.graph_engine = KnowledgeGraph(cls.con)
        cls.mcp_server = RealEstateIntelligenceMCP(cls.con)
        cls.agentic_copilot = AgenticCopilot(cls.mcp_server)
        cls.markup_spread_cache = None
        cls.zombie_radar_cache = None
        cls.developer_clusters_cache = OrderedDict()

    @classmethod
    def get_backends(cls) -> "AppState":
        if cls.con is None:
            cls.setup_backends(read_only=True)
        return cls


def _get_cached_developer_cluster(name: str) -> Optional[Dict[str, Any]]:
    key = name.strip().upper()
    if key in AppState.developer_clusters_cache:
        val = AppState.developer_clusters_cache.pop(key)
        AppState.developer_clusters_cache[key] = val
        return val
    return None


def _put_cached_developer_cluster(name: str, val: Dict[str, Any]) -> None:
    key = name.strip().upper()
    if key in AppState.developer_clusters_cache:
        AppState.developer_clusters_cache.pop(key)
    elif len(AppState.developer_clusters_cache) >= 256:
        AppState.developer_clusters_cache.popitem(last=False)
    AppState.developer_clusters_cache[key] = val


def setup_backends(db_path: Optional[Any] = None, read_only: bool = False) -> None:
    """Public helper for test suites to inject custom database paths."""
    AppState.setup_backends(db_path, read_only=read_only)


def sanitize_floats(obj: Any) -> Any:
    """Recursively convert NaN and Inf into None so json serialization never fails."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: sanitize_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_floats(v) for v in obj]
    return obj


MAPTILER_UPSTREAM = "https://api.maptiler.com/"
_MAPTILER_HOST = "api.maptiler.com"
_TLS = threading.local()
_PROXY_CACHE: Dict[str, Any] = {}
_PROXY_CACHE_ORDER: List[str] = []
_PROXY_CACHE_LOCK = threading.Lock()
_PROXY_CACHE_MAX = 300


def _maptiler_key() -> Optional[str]:
    key = os.environ.get("MAPTILER_API_KEY")
    return key.strip() if key and key.strip() else None


def _maptiler_connection() -> http.client.HTTPSConnection:
    conn = getattr(_TLS, "maptiler_conn", None)
    if conn is None:
        conn = http.client.HTTPSConnection(_MAPTILER_HOST, timeout=20)
        _TLS.maptiler_conn = conn
    return conn


def _proxy_cache_get(cache_key: str):
    with _PROXY_CACHE_LOCK:
        return _PROXY_CACHE.get(cache_key)


def _proxy_cache_put(cache_key: str, value: Any):
    with _PROXY_CACHE_LOCK:
        if len(_PROXY_CACHE) >= _PROXY_CACHE_MAX:
            oldest = _PROXY_CACHE_ORDER.pop(0) if _PROXY_CACHE_ORDER else None
            if oldest:
                _PROXY_CACHE.pop(oldest, None)
        _PROXY_CACHE[cache_key] = value
        _PROXY_CACHE_ORDER.append(cache_key)


@asynccontextmanager
async def existing_lifespan(app: FastAPI):
    """Ensure database connection and analytics backends are initialized."""
    AppState.get_backends()
    yield


mcp_app = mcp.http_app(path="/", stateless_http=True)


class MCPGatewayMiddleware:
    """Handles exact /mcp path rewrite (preventing 307 redirect) and optional Bearer auth scoped to /mcp."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path == "/mcp" or path.startswith("/mcp/"):
                mcp_key = os.environ.get("MCP_API_KEY")
                if mcp_key and mcp_key.strip():
                    headers = dict(scope.get("headers", []))
                    auth_header = headers.get(b"authorization", b"").decode("latin1").strip()
                    expected_header = f"Bearer {mcp_key.strip()}"
                    if auth_header != expected_header:
                        resp = JSONResponse(
                            {"jsonrpc": "2.0", "error": {"code": -32001, "message": "Unauthorized"}},
                            status_code=401,
                        )
                        await resp(scope, receive, send)
                        return

                if path == "/mcp":
                    scope["path"] = "/mcp/"

        await self.app(scope, receive, send)


app = FastAPI(
    title="GujRERA Real Estate Intelligence Platform",
    description="Sovereign institutional real estate analytics engine for Gujarat RERA",
    version="1.0.0",
    lifespan=combine_lifespans(existing_lifespan, mcp_app.lifespan),
)

app.add_middleware(MCPGatewayMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Locate static assets directory
candidates_static = [
    Path(__file__).resolve().parent.parent / "real_estate_intelligence" / "real_estate_intelligence" / "ui" / "static",
    Path(__file__).resolve().parent.parent / "real_estate_intelligence" / "ui" / "static",
    Path(__file__).resolve().parent / "static",
]
STATIC_DIR = next((p for p in candidates_static if p.exists() and (p / "index.html").exists()), candidates_static[0])

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Mount MCP Streamable HTTP gateway at /mcp
app.mount("/mcp", mcp_app)


@app.get("/api/health")
def api_health():
    """System health check verifying database connectivity and project counts."""
    backends = AppState.get_backends()
    try:
        cur = backends.con.execute("SELECT count(*) FROM projects")
        cnt = cur.fetchone()[0]
        return {"status": "ok", "projects": cnt}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/map/pins")
def api_map_pins(
    district: Optional[str] = Query(None, description="Optional district filter"),
    tier: Optional[str] = Query(None, description="Optional tier filter ('deep_audit' or 'statewide')"),
    status: Optional[str] = Query(None, description="Optional project status filter"),
):
    """Compact map coordinate feed with coordinate tuples."""
    backends = AppState.get_backends()
    try:
        pins = get_map_pins(backends.con, district=district, tier=tier, status=status)
        return JSONResponse(pins)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/explore/facets")
def api_explore_facets():
    """Facets for explore filters: district counts and unit types."""
    backends = AppState.get_backends()
    try:
        return JSONResponse(get_explore_facets(backends.con))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects")
def api_projects():
    """Concise project catalog for dropdowns and listings."""
    backends = AppState.get_backends()
    try:
        return get_projects_list(backends.con)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/compare")
def api_compare(
    ids: Optional[str] = Query(None, description="Comma-separated project IDs (e.g. ?ids=9036,17207)"),
):
    """Side-by-side project comparison endpoint with truth flags and PII redaction."""
    if not ids or not ids.strip():
        raise HTTPException(status_code=400, detail="Missing or empty 'ids' parameter")

    raw_tokens = [tok.strip() for tok in ids.split(",") if tok.strip()]
    if not raw_tokens:
        raise HTTPException(status_code=400, detail="Empty project IDs provided")

    parsed_ids: List[int] = []
    for tok in raw_tokens:
        try:
            parsed_ids.append(int(tok))
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail=f"Invalid project ID: {tok}")

    if len(parsed_ids) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 project IDs allowed for comparison")

    backends = AppState.get_backends()
    raw_comparison = backends.mcp_server.compare_projects(parsed_ids)
    comp_by_pid = {r["project_id"]: dict(r) for r in raw_comparison}

    results: List[Dict[str, Any]] = []
    for pid in parsed_ids:
        if pid in comp_by_pid:
            item = comp_by_pid[pid]
            item["truth_flags"] = get_project_truth_flags(backends.con, pid)
            results.append(item)
        else:
            results.append({"project_id": pid, "error": "not_found"})

    redacted = redact_payload(results)
    return JSONResponse(sanitize_floats(redacted))


@app.get("/api/search/projects")
def api_search_projects(
    q: Optional[str] = Query(None, description="Search query across name, promoter, reg_no, district, taluka"),
    district: Optional[str] = Query(None, description="Optional case-insensitive district filter"),
    limit: Optional[int] = Query(15, description="Maximum results (1-50, default 15)"),
):
    """Fast search across project_summaries with wildcard escaping and case-insensitive district matching."""
    stripped_q = (q or "").strip()
    if len(stripped_q) < 2:
        return JSONResponse([])

    clamped_limit = min(max(1, limit or 15), 50)
    backends = AppState.get_backends()
    results = search_project_summaries(
        backends.con,
        q=stripped_q,
        district=district,
        limit=clamped_limit,
    )
    return JSONResponse(sanitize_floats(results))


@app.get("/api/project/{pid}")
def api_project_detail(pid: str):
    """Detailed statutory records for a specific project with graceful statewide fallbacks."""
    try:
        num_pid = int(pid)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid project ID")

    backends = AppState.get_backends()
    detail = get_project_detail(
        backends.con,
        num_pid,
        auditor=backends.auditor,
        graph_engine=backends.graph_engine,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Project not found")
    detail["truth_flags"] = get_project_truth_flags(backends.con, num_pid)
    return JSONResponse(sanitize_floats(detail))


@app.get("/api/pricing/{pid}")
def api_pricing_detail(pid: str):
    """Longitudinal pricing summary and agreement analysis for a specific project."""
    try:
        num_pid = int(pid)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid project ID")

    backends = AppState.get_backends()
    summary = backends.pricing_engine.get_project_pricing_summary(num_pid)
    return JSONResponse(sanitize_floats(summary))


@app.get("/api/explore")
def api_explore(
    limit: Optional[str] = Query(None, description="Page limit (1-500)"),
    offset: Optional[str] = Query("0", description="Page offset"),
    sort_by: Optional[str] = Query(None, description="Column to sort by"),
    sort_dir: Optional[str] = Query("asc", description="Sort direction ('asc' or 'desc')"),
    district: Optional[str] = Query(None, description="District filter"),
    taluka: Optional[str] = Query(None, description="Taluka/subdistrict filter"),
    promoter: Optional[str] = Query(None, description="Promoter/developer name filter"),
    project_type: Optional[str] = Query(None, description="Project type filter"),
    search: Optional[str] = Query(None, description="Free text query matching name, builder, or regNo"),
    q: Optional[str] = Query(None, description="Alias for search query"),
    unit_type: Optional[str] = Query(None, description="Unit type filter"),
    completion_before: Optional[str] = Query(None, description="Completion before date"),
    min_stage: Optional[str] = Query(None, description="Minimum progress percentage"),
    has_complaints: Optional[str] = Query(None, description="Filter for complaints > 0"),
    has_extensions: Optional[str] = Query(None, description="Filter for extensions > 0"),
):
    """Explore table feed supporting join-free pre-aggregated queries, sorting, and pagination."""
    backends = AppState.get_backends()
    rows = get_explore_rows(backends.con)
    filtered = rows
    if district:
        filtered = [r for r in filtered if r.get("district") == district]
    if taluka:
        filtered = [r for r in filtered if r.get("taluka") == taluka]
    if promoter:
        p_lower = promoter.lower()
        filtered = [r for r in filtered if r.get("promoter_name") and p_lower in r["promoter_name"].lower()]
    if project_type:
        filtered = [r for r in filtered if r.get("project_type") == project_type]
    search_term = search or q
    if search_term:
        s_lower = search_term.lower()
        filtered = [
            r for r in filtered
            if (
                (r.get("name") and s_lower in r["name"].lower())
                or (r.get("promoter_name") and s_lower in r["promoter_name"].lower())
                or (r.get("registration_number") and s_lower in r["registration_number"].lower())
            )
        ]
    if unit_type:
        filtered = [r for r in filtered if unit_type in (r.get("unit_types") or [])]
    if completion_before:
        filtered = [r for r in filtered if r.get("completion_date") and str(r["completion_date"])[:10] <= completion_before]
    if min_stage is not None:
        try:
            m_stage = float(min_stage)
            filtered = [r for r in filtered if r.get("progress_pct") is not None and float(r["progress_pct"]) >= m_stage]
        except ValueError:
            pass
    if has_complaints in ("1", "true", "True", True):
        filtered = [r for r in filtered if (r.get("complaints_count") or 0) > 0]
    if has_extensions in ("1", "true", "True", True):
        filtered = [r for r in filtered if (r.get("extensions_count") or 0) > 0]

    if sort_by:
        sort_key_clean = str(sort_by).strip().lower()
        if sort_key_clean not in SORT_COLUMN_MAP:
            allowed = sorted(list(SORT_COLUMN_MAP.keys()))
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sort_by '{sort_by}'. Allowed keys: {', '.join(allowed)}",
            )
        filtered = sort_explore_rows(filtered, sort_by=sort_key_clean, sort_dir=sort_dir)

    if limit is not None:
        try:
            clamped_limit = max(1, min(int(limit), 500))
            clamped_offset = max(0, int(offset or 0))
            total_count = len(rows)
            filtered_count = len(filtered)
            return {
                "total_count": total_count,
                "filtered_count": filtered_count,
                "limit": clamped_limit,
                "offset": clamped_offset,
                "items": filtered[clamped_offset : clamped_offset + clamped_limit],
            }
        except ValueError:
            pass
    return filtered


@app.get("/api/graph")
def api_graph(
    project_id: Optional[str] = Query(None, description="Optional project ID for ego-network scoping"),
    depth: Optional[str] = Query("2", description="Network traversal depth (default: 2)"),
):
    """Return nodes and edges formatted for Vis.js (scoped to project ego-network if requested)."""
    backends = AppState.get_backends()
    pid = None
    if project_id and project_id.strip():
        try:
            pid = int(project_id)
        except (ValueError, TypeError):
            pass
    try:
        d_val = int(depth or 2)
    except (ValueError, TypeError):
        d_val = 2

    data = get_graph_data(
        backends.con,
        graph_engine=backends.graph_engine,
        project_id=pid,
        depth=d_val,
    )
    return JSONResponse(sanitize_floats(data))


@app.get("/api/insights/zombie_radar")
def api_insights_zombie_radar(
    limit: int = Query(50, ge=1, le=200, description="Max projects to return"),
):
    """Retrieve high-risk modern private schemes past completion deadline with no BU/NOC."""
    backends = AppState.get_backends()
    if AppState.zombie_radar_cache is not None and limit <= len(AppState.zombie_radar_cache):
        return JSONResponse(AppState.zombie_radar_cache[:limit])
    try:
        data = get_zombie_radar_data(backends.con, limit=limit)
        AppState.zombie_radar_cache = data
        return JSONResponse(sanitize_floats(data))
    except Exception as e:
        logger.exception("Error in /api/insights/zombie_radar: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


_MARKUP_SPREAD_SNAPSHOTS = [
    Path(__file__).resolve().parent.parent / "real_estate_intelligence" / "data" / "markup_spread_snapshot.json",
    Path(__file__).resolve().parent.parent / "data" / "markup_spread_snapshot.json",
]


@app.get("/api/insights/markup_spread")
def api_insights_markup_spread():
    """Statewide unbooked asking rate markup vs. registered booked rate spread."""
    if AppState.markup_spread_cache is not None:
        return JSONResponse(AppState.markup_spread_cache)

    backends = AppState.get_backends()
    is_default_db = (
        backends.db_path is None
        or str(backends.db_path) == str(DEFAULT_DB_PATH)
        or Path(backends.db_path).resolve() == Path(DEFAULT_DB_PATH).resolve()
    )

    if is_default_db:
        for snap_path in _MARKUP_SPREAD_SNAPSHOTS:
            if snap_path.is_file():
                try:
                    with open(snap_path, "r", encoding="utf-8") as f:
                        snap_data = json.load(f)
                    AppState.markup_spread_cache = sanitize_floats(snap_data)
                    return JSONResponse(AppState.markup_spread_cache)
                except Exception as ex:
                    logger.warning("Failed to load markup spread snapshot from %s: %s", snap_path, ex)

    try:
        data = get_markup_spread_data(backends.con)
        AppState.markup_spread_cache = sanitize_floats(data)
        return JSONResponse(AppState.markup_spread_cache)
    except Exception as e:
        logger.exception("Error in /api/insights/markup_spread: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/insights/developer_clusters")
def api_insights_developer_clusters(
    promoter_name: Optional[str] = Query(None, description="Optional promoter brand or company name"),
):
    """Resolve developer portfolio clusters via Composite Key (c) or get statewide brand overview."""
    backends = AppState.get_backends()
    prom_key = (promoter_name or "").strip()
    if prom_key:
        cached = _get_cached_developer_cluster(prom_key)
        if cached is not None:
            return JSONResponse(cached)
        try:
            data = get_developer_clusters_data(backends.con, promoter_name=prom_key)
            cleaned = sanitize_floats(data)
            _put_cached_developer_cluster(prom_key, cleaned)
            return JSONResponse(cleaned)
        except Exception as e:
            logger.exception("Error in /api/insights/developer_clusters: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    # Default overview mode
    cached_overview = _get_cached_developer_cluster("__OVERVIEW__")
    if cached_overview is not None:
        return JSONResponse(cached_overview)
    try:
        data = get_developer_clusters_data(backends.con, promoter_name=None)
        cleaned = sanitize_floats(data)
        _put_cached_developer_cluster("__OVERVIEW__", cleaned)
        return JSONResponse(cleaned)
    except Exception as e:
        logger.exception("Error in /api/insights/developer_clusters overview: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/survival")
def api_analytics_survival(project_id: Optional[str] = Query(None)):
    """Forecast project completion delay via Cox survival analysis."""
    try:
        pid = int(project_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid project ID")

    backends = AppState.get_backends()
    res = backends.mcp_server.forecast_completion_delay(pid)
    return JSONResponse(sanitize_floats(res))


@app.get("/api/analytics/pricing_trend")
def api_analytics_pricing_trend(
    project_id: Optional[str] = Query(None),
    asset_class: Optional[str] = Query("Residential"),
):
    """Longitudinal transaction price trajectory, appreciation, and CAGR."""
    try:
        pid = int(project_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid project ID")

    backends = AppState.get_backends()
    res = backends.pricing_engine.get_longitudinal_pricing_trend(pid, asset_class=asset_class or "Residential")
    return JSONResponse(sanitize_floats(res))


@app.get("/api/analytics/ml_pricing")
def api_analytics_ml_pricing(
    project_id: Optional[str] = Query(None),
    asset_class: Optional[str] = Query("Residential"),
    carpet_area_sqft: Optional[str] = Query("1200"),
):
    """Hedonic GBDT model pricing prediction with exact Tree SHAP attributions."""
    try:
        pid = int(project_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid project ID")

    aclass = asset_class or "Residential"
    try:
        carpet = float(carpet_area_sqft or 1200.0)
    except (ValueError, TypeError):
        carpet = 1200.0

    backends = AppState.get_backends()
    res = backends.mcp_server.predict_pricing_benchmark(pid, asset_class=aclass, carpet_area_sqft=carpet)
    return JSONResponse(sanitize_floats(res))


@app.get("/api/analytics/spatial_pricing")
def api_spatial_pricing(
    project_id: Optional[str] = Query(None, description="Project ID"),
    asset_class: Optional[str] = Query("Residential", description="Asset class (e.g. Residential, Commercial)"),
):
    """Empirical spatial pricing benchmark and comp distribution."""
    if not project_id:
        raise HTTPException(status_code=400, detail="Missing required 'project_id' query parameter")
    try:
        pid = int(project_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid project ID")

    backends = AppState.get_backends()
    res = backends.spatial_pricer.benchmark(pid, asset_class=asset_class or "Residential")
    return JSONResponse(sanitize_floats(res))


@app.get("/api/verify_claim")
def api_verify_claim(
    project_id: Optional[str] = Query(None),
    claimed_rate: Optional[str] = Query(None),
    claimed_sold: Optional[str] = Query(None),
    claimed_date: Optional[str] = Query(None),
    asset_class: Optional[str] = Query("Residential"),
):
    """Statutory sales claim verifier cross-checking Form 3 certified deeds."""
    try:
        pid = int(project_id or 0)
        price = float(claimed_rate) if claimed_rate and claimed_rate.strip() else None
        sold = float(claimed_sold) if claimed_sold and claimed_sold.strip() else None
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid numeric parameter")

    backends = AppState.get_backends()
    date = claimed_date.strip() if claimed_date and claimed_date.strip() else None
    res = backends.verifier.verify_claim(
        project_id=pid,
        claimed_rate_sqft=price,
        claimed_sold_pct=sold,
        claimed_completion_date=date,
        asset_class=asset_class or "Residential",
    )
    return JSONResponse(sanitize_floats(res))


@app.get("/api/search")
def api_search(
    query: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    limit: int = Query(10),
):
    """Full-text BM25 search across indexed Form 1, 2, and 3 statutory filings."""
    search_query = q or query or ""
    pid = None
    if project_id and project_id.strip():
        try:
            pid = int(project_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid project ID")

    backends = AppState.get_backends()
    results = backends.search_engine.search(query=search_query, project_id=pid, limit=limit)
    return {"query": search_query, "results": results}


@app.get("/api/map/config")
def api_map_config():
    """Client map styling configuration."""
    key = _maptiler_key()
    return {"maptiler_proxy": bool(key)}


@app.get("/api/maptiler/{subpath:path}")
def api_maptiler_proxy(subpath: str, request: Request):
    """Stream a MapTiler resource with the server-side key attached."""
    key = _maptiler_key()
    if not key:
        raise HTTPException(status_code=404, detail="Map proxy not configured (set MAPTILER_API_KEY)")
    if not subpath or ".." in subpath or subpath.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid map resource path")

    query_params = dict(request.query_params)
    params = [(k, v) for k, v in query_params.items() if k != "key"]
    params.append(("key", key))
    cache_key = subpath + "?" + urlencode(params)
    cacheable = "/tiles/v3/" not in subpath or subpath.endswith("tiles.json")
    if cacheable:
        hit = _proxy_cache_get(cache_key)
        if hit is not None:
            ctype, cbody = hit
            return Response(
                content=cbody,
                media_type=ctype,
                headers={"Cache-Control": "public, max-age=86400" if "/tiles/" in subpath else "public, max-age=300"},
            )

    url_query = urlencode(params)
    body = ctype = None
    for attempt in (1, 2):
        conn = _maptiler_connection()
        try:
            conn.request("GET", "/" + subpath + "?" + url_query, headers={"User-Agent": "gujrera-intelligence-ui"})
            resp = conn.getresponse()
            body = resp.read()
            ctype = resp.getheader("Content-Type", "application/octet-stream")
            if resp.status != 200:
                raise HTTPException(status_code=resp.status, detail="Upstream map resource error")
            break
        except HTTPException:
            raise
        except (http.client.HTTPException, OSError):
            _TLS.maptiler_conn = None
            if attempt == 2:
                raise HTTPException(status_code=502, detail="Upstream map resource unreachable")

    if ctype and "json" in ctype and body:
        import re as _re
        host = request.headers.get("Host", "127.0.0.1")
        proto = request.headers.get("X-Forwarded-Proto") or (
            "http" if host.split(":")[0] in ("127.0.0.1", "localhost", "::1") else "https"
        )
        origin = f"{proto}://{host}"
        body = body.replace(MAPTILER_UPSTREAM.encode("utf-8"), (origin + "/api/maptiler/").encode("utf-8"))
        body = _re.sub(rb"[?&]key=[^&\"']+", b"", body)

    if cacheable and body and len(body) < 2_000_000 and ctype:
        _proxy_cache_put(cache_key, (ctype, body))

    return Response(
        content=body,
        media_type=ctype,
        headers={"Cache-Control": "public, max-age=86400" if "/tiles/" in subpath else "public, max-age=300"},
    )


@app.post("/api/copilot")
async def api_copilot(request: Request):
    """Institutional due diligence copilot (Agentic LLM with deterministic local fallback)."""
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    query_text = (data.get("query") or "").strip()
    try:
        project_id = int(data.get("project_id", 0))
    except (ValueError, TypeError):
        project_id = 0

    api_key = (
        (data.get("api_key") or "").strip()
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
    )
    backends = AppState.get_backends()
    reply_data = handle_copilot_query(
        query=query_text,
        project_id=project_id,
        con=backends.con,
        mcp_server=backends.mcp_server,
        pricing_engine=backends.pricing_engine,
        auditor=backends.auditor,
        search_engine=backends.search_engine,
        agentic_copilot=backends.agentic_copilot,
        api_key=api_key,
    )
    return JSONResponse(sanitize_floats(reply_data))


@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
def index():
    """Serve the root dashboard HTML."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(
            content=index_file.read_text(encoding="utf-8"),
            status_code=200,
            headers={"Cache-Control": "no-cache"},
        )
    return HTMLResponse(content="<h1>GujRERA Real Estate Intelligence Platform</h1>", status_code=200)
