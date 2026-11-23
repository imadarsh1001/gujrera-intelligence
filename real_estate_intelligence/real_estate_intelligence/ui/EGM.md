# ui — Single Static Asset Directory & Dashboard Front-End

## Overview
Hosts the single-page dashboard static interface (`ui/static/index.html`), the modular insights script (`ui/static/insights.js`), and vendored, version-pinned front-end assets in `static/vendor/` (Tailwind Play runtime, Font Awesome 6.4.0 + webfonts, vis-network 9.1.9, Chart.js 4.4.4, MapLibre GL 5.24.0) so the workstation renders 100% offline. Backend routing and JSON API endpoints are consolidated into the single FastAPI ASGI application (`api/index.py`), with all database queries executing through the shared SQL seam [`real_estate_intelligence/db/queries.py`](../db/queries.py). The server is launched via `run_server.py` or the CLI (`real-estate-intelligence serve`), binding `uvicorn` to `127.0.0.1:8765`.

## Interface

### Static Assets Directory (`ui/static/`)
- `ui/static/index.html`: Complete single-page application dashboard (Explore table, 4-quadrant project dossier, Chart.js quantitative ML curves, Vis.js knowledge graph, MapLibre GIS map with SVG offline fallback, Statewide Insights Radar tab, and floating AI Diligence Copilot drawer).
- `ui/static/insights.js`: Modular front-end engine for Statewide Insights Radar (Zombie Projects table, Statewide Asking Price Markup cards and district absorption breakdown, and Developer Portfolio & Brand Cluster Explorer).
- `ui/static/vendor/`: Local, version-pinned static dependencies eliminating all external CDN calls.
- `ui/static/gujarat_map.json`: Local GeoJSON district boundaries for offline map rendering.

### Consolidated FastAPI Routes (`api/index.py`)
Served on `http://127.0.0.1:8765`:

| Method | Route | Description / Seam |
|---|---|---|
| GET | `/`, `/index.html` | Serves `ui/static/index.html` [api/index.py:index] |
| GET | `/static/{path}` | Static asset mount with traversal guard (`ui/static/`) [api/index.py:StaticFiles] |
| GET | `/api/health` | Health check returning status and database connection state [api/index.py:health] |
| GET | `/api/projects` | Lightweight project list `[{id, name, district, status}]` via `queries.get_projects_list` [api/index.py:get_projects] |
| GET | `/api/explore` | Pre-aggregated project rows with district, completion dates, revisions, and pricing via `queries.get_explore_rows` [api/index.py:explore] |
| GET | `/api/explore/facets` | District and status facet counts for filtering via `queries.get_explore_facets` [api/index.py:explore_facets] |
| GET | `/api/project/{pid}` | Comprehensive project dossier payload via `queries.get_project_detail` [api/index.py:get_project] |
| GET | `/api/pricing/{pid}` | Unit transaction distribution and pricing summaries via `PricingIntelligence` [api/index.py:pricing] |
| GET | `/api/graph` | Knowledge graph nodes and edges (`{nodes, edges}`) via `queries.get_graph_data` [api/index.py:graph] |
| GET | `/api/insights/zombie_radar` | High-risk modern private schemes past completion deadline with no BU/NOC via `queries.get_zombie_radar_data` [api/index.py:api_insights_zombie_radar] |
| GET | `/api/insights/markup_spread` | Statewide unbooked asking markup vs. registered booked deeds via `queries.get_markup_spread_data` [api/index.py:api_insights_markup_spread] |
| GET | `/api/insights/developer_clusters` | Partitioned brand clusters via Composite Key (c) or brand overview via `queries.get_developer_clusters_data` [api/index.py:api_insights_developer_clusters] |
| GET | `/api/analytics/survival` | Completion delay forecast via Cox PH model (`RealEstateIntelligenceMCP.forecast_completion_delay`) [api/index.py:analytics_survival] |
| GET | `/api/analytics/pricing_trend` | Longitudinal median quarterly price appreciation via `PricingIntelligence.get_longitudinal_pricing_trend` [api/index.py:analytics_pricing_trend] |
| GET | `/api/analytics/ml_pricing` | GBDT pricing benchmark via `RealEstateIntelligenceMCP.predict_pricing_benchmark` [api/index.py:analytics_ml_pricing] |
| GET | `/api/verify_claim` | Empirical sales claim verification via `SalesClaimVerifier.verify_claim` [api/index.py:verify_claim] |
| GET | `/api/search` | Full-text search over indexed statutory PDFs via `DocumentSearchEngine.search` [api/index.py:search] |
| GET | `/api/map/config` | Returns `{"maptiler_proxy": bool}` indicating whether MapTiler API proxy is active [api/index.py:map_config] |
| GET | `/api/maptiler/{path}` | Proxies tile requests to MapTiler server-side, keeping API keys private [api/index.py:proxy_maptiler] |
| POST | `/api/copilot` | Diligence copilot accepting `{query, project_id, api_key}` with LLM agentic tool calling and deterministic offline fallback [api/index.py:copilot] |
| ALL | `/mcp` | FastMCP 4.2 Streamable HTTP gateway endpoint mounting all 14 tools and resources [api/index.py:mcp_app] |

## Invariants
- Launcher: `run_server.py` and `cli.py` (`cmd_serve`) execute `uvicorn.run("api.index:app", host="127.0.0.1", port=port)`.
- SQL Seam: No SQL queries are embedded in route handlers; all domain queries execute through `real_estate_intelligence/db/queries.py`.
- Sub-200ms Warm Response Latency: `/api/insights/*` endpoints leverage `AppState` in-memory caching and covering index `idx_unit_status_rates`.
- Bounded Cache: `developer_clusters_cache` uses an `OrderedDict` LRU cache capped at 256 entries to prevent memory leaks [api/index.py:_put_cached_developer_cluster].
- PII Sanitization: All responses pass through `redact_payload()` before serialization.
- Copilot fallback: When no API key is passed (or on agent failure), the copilot executes deterministic keyword routing with zero hallucination.
- Static offline rendering: All assets are served from `ui/static/vendor/`; no runtime internet access is required.

## Side Effects
- Mounts static files from `ui/static/` at `/static` and index at `/` and `/index.html` [api/index.py]
- Mounts FastMCP HTTP application at `/mcp` [api/index.py]

## Verification
- Run: `python -m pytest real_estate_intelligence/tests` (103 passing tests)
- Launch server: `python run_server.py`
