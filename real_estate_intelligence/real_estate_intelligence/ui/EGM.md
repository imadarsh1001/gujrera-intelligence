# ui — Single Static Asset Directory & Dashboard Front-End

## Overview
Hosts the single-page dashboard static interface (`ui/static/index.html`) and vendored, version-pinned front-end assets in `static/vendor/` (Tailwind Play runtime, Font Awesome 6.4.0 + webfonts, vis-network 9.1.9, Chart.js 4.4.4, MapLibre GL 5.24.0) so the workstation renders 100% offline. Backend routing and JSON API endpoints are consolidated into the single FastAPI ASGI application (`api/index.py`), while all database queries and data rollups are consolidated in the shared SQL seam [`real_estate_intelligence/db/queries.py`](../db/queries.py). The server is launched via `run_server.py` or the CLI (`real-estate-intelligence serve`), binding `uvicorn` to `127.0.0.1:8765`.

## Interface

### Static Assets Directory (`ui/static/`)
- `ui/static/index.html`: Complete single-page application dashboard (Explore table, 4-quadrant project dossier, Chart.js quantitative ML curves, Vis.js knowledge graph, MapLibre GIS map with SVG offline fallback, and floating AI Diligence Copilot drawer).
- `ui/static/vendor/`: Local, version-pinned static dependencies eliminating all external CDN calls.
- `ui/static/gujarat_map.json`: Local GeoJSON district boundaries for offline map rendering.

### Consolidated FastAPI Routes (`api/index.py`)
Served on `http://127.0.0.1:8765`:

| Method | Route | Description / Seam |
|---|---|---|
| GET | `/`, `/index.html` | Serves `ui/static/index.html` [api/index.py:index] |
| GET | `/static/{path}` | Static asset mount with traversal guard (`ui/static/`) [api/index.py:StaticFiles] |
| GET | `/api/health` | Health check returning status and database connection state [api/index.py:health] |
| GET | `/api/projects` | Lightweight project list `[{id, name, district, status}]` via `queries.get_project_list` [api/index.py:get_projects] |
| GET | `/api/explore` | Pre-aggregated project rows with district, completion dates, revisions, and pricing via `queries.get_explore_rows` [api/index.py:explore] |
| GET | `/api/explore/facets` | District and status facet counts for filtering via `queries.get_explore_facets` [api/index.py:explore_facets] |
| GET | `/api/project/{pid}` | Comprehensive project dossier payload via `queries.get_project_detail` [api/index.py:get_project] |
| GET | `/api/pricing/{pid}` | Unit transaction distribution and pricing summaries via `PricingIntelligence` [api/index.py:pricing] |
| GET | `/api/graph` | Knowledge graph nodes and edges (`{nodes, edges}`) via `queries.get_graph_data` [api/index.py:graph] |
| GET | `/api/analytics/survival` | Completion delay forecast via Cox PH model (`RealEstateIntelligenceMCP.forecast_completion_delay`) [api/index.py:analytics_survival] |
| GET | `/api/analytics/pricing_trend` | Longitudinal median quarterly price appreciation via `PricingIntelligence.get_longitudinal_pricing_trend` [api/index.py:analytics_pricing_trend] |
| GET | `/api/analytics/ml_pricing` | GBDT pricing benchmark via `RealEstateIntelligenceMCP.predict_pricing_benchmark` [api/index.py:analytics_ml_pricing] |
| GET | `/api/verify_claim` | Empirical sales claim verification via `SalesClaimVerifier.verify_claim` [api/index.py:verify_claim] |
| GET | `/api/search` | Full-text search over indexed statutory PDFs via `DocumentSearchEngine.search` [api/index.py:search] |
| GET | `/api/map/config` | Returns `{"maptiler_proxy": bool}` indicating whether MapTiler API proxy is active [api/index.py:map_config] |
| GET | `/api/maptiler/{path}` | Proxies tile requests to MapTiler server-side, keeping API keys private [api/index.py:proxy_maptiler] |
| POST | `/api/copilot` | Diligence copilot accepting `{query, project_id, api_key}` with LLM agentic tool calling and deterministic offline fallback [api/index.py:copilot] |

## Invariants
- Launcher: `run_server.py` and `cli.py` (`cmd_serve`) execute `uvicorn.run("api.index:app", host="127.0.0.1", port=port)`.
- SQL Seam: No SQL queries are embedded in route handlers; all domain queries execute through `real_estate_intelligence/db/queries.py`.
- Copilot fallback: When no API key is passed (or on agent failure), the copilot executes deterministic keyword routing with zero hallucination.
- Static offline rendering: All assets are served from `ui/static/vendor/`; no runtime internet access is required.
- Single static dir: `ui/static/` is the single source of truth for UI assets.

## Verification
- Run: `python -m pytest real_estate_intelligence/tests` (60 passing tests)
- Launch server: `python run_server.py`
