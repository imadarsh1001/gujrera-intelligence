# ui — Zero-Dependency HTTP Dashboard & Deterministic Copilot

## Overview
Standard-library web server (`http.server`) serving an embedded single-page dashboard (`HTML_TEMPLATE`: Tailwind CDN, vis-network, Chart.js 4.4.4) plus a JSON API over the analytics stack. Also hosts a deterministic, keyword-routed diligence copilot (`_handle_copilot_query`) that first tries the agentic LLM from `agent.copilot` when an API key is available and otherwise synthesizes cited answers offline. Bound to `127.0.0.1` only.

## Interface
HTTP routes on `IntelligenceRequestHandler` [server.py:IntelligenceRequestHandler]:

| Method | Route | Handler / Source |
|---|---|---|
| GET | `/`, `/index.html` | serves `HTML_TEMPLATE` [server.py:do_GET] |
| GET | `/api/projects` | project list rows [server.py:do_GET] |
| GET | `/api/project/{pid}` | aggregated payload: `project`, `blocks`, `timeline`, `finances`, `professionals`, `banks`, `prior_projects`, `form5`, `bu_records`, `leads`, `contagion`; 400 on invalid ID, 404 if missing [server.py:do_GET] |
| GET | `/api/graph` | vis.js `{"nodes", "edges"}` with fixed color map keyed on node kind (`Project`, `Promoter`, `Engineer`, `Architect`, `Ca`, `Bank`, `PriorProject`) [server.py:do_GET] |
| GET | `/api/pricing/{pid}` | `PricingIntelligence.get_project_pricing_summary` [server.py:do_GET] |
| GET | `/api/verify_claim?project_id&claimed_rate&claimed_sold&claimed_date` | `SalesClaimVerifier.verify_claim` [server.py:do_GET] |
| GET | `/api/search?query&project_id` | FTS search, `limit=10` [server.py:do_GET] |
| GET | `/api/analytics/survival?project_id` | MCP `forecast_completion_delay` [server.py:do_GET] |
| GET | `/api/analytics/pricing_trend?project_id` | `get_longitudinal_pricing_trend` [server.py:do_GET] |
| GET | `/api/analytics/ml_pricing?project_id&asset_class&carpet_area_sqft` | MCP `predict_pricing_benchmark` (carpet falls back to 1200.0 on parse error) [server.py:do_GET] |
| POST | `/api/copilot` | JSON body `{query, project_id, api_key}`; 400 on invalid JSON [server.py:do_POST] |

- `IntelligenceRequestHandler.setup_backends(db_path=None)` — classmethod wiring one shared connection plus `PricingIntelligence`, `SalesClaimVerifier`, `ProjectAuditor`, `DocumentSearchEngine`, `KnowledgeGraph`, `RealEstateIntelligenceMCP`, and `AgenticCopilot` [server.py:setup_backends]
- `start_server(port=8765, db_path=None)` — constructs `HTTPServer(("127.0.0.1", port), ...)` and serves until KeyboardInterrupt [server.py:start_server]
- Package export: `start_server` [__init__.py:__all__]

## Invariants
- All backends are class-level attributes shared by every request; `setup_backends` must be called before serving (it is invoked by `start_server`) [server.py:IntelligenceRequestHandler]
- Unknown routes return HTTP 404 (`send_error(404, "Endpoint not found")`); JSON responses are always HTTP 200 with `Content-Type: application/json; charset=utf-8`, serialized with `default=str` [server.py:_send_json]
- Copilot API key fallback chain: request body `api_key`, then env `GEMINI_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY` [server.py:do_POST]
- `_handle_copilot_query` tries `AgenticCopilot.run_query` first when a key and backend exist and silently falls back to the deterministic keyword router on failure; with no key it is fully offline and deterministic [server.py:_handle_copilot_query]
- The deterministic router matches intents in fixed order (greeting/help, architecture/credentials, buy-advice, lifecycle, launch date, sales/inventory, title/mortgage, escrow, delay/survival, pricing/CAGR, contagion/network) with a full-text-search fallback; a `project_id <= 0` is replaced by the lowest project ID in the database [server.py:_handle_copilot_query]
- The server binds to `127.0.0.1` (not `0.0.0.0`) and is single-threaded (`HTTPServer`, not `ThreadingHTTPServer`) [server.py:start_server]
- The entire dashboard HTML is embedded in the Python source as `HTML_TEMPLATE`; no static files are read from disk [server.py:HTML_TEMPLATE]

## Side Effects
- Opens a shared SQLite connection and instantiates all analytics backends in `setup_backends` (schema/pragmas applied via `get_connection`) [server.py:setup_backends]
- Listens on a TCP socket at `127.0.0.1:{port}` (default 8765) and prints `[READY] ...` to stdout [server.py:start_server]
- `POST /api/copilot` may trigger outbound LLM API calls through `AgenticCopilot` when a key is present (network side effect) [server.py:_handle_copilot_query]
- Serves CDN assets client-side (Tailwind, Font Awesome, vis-network, Chart.js from public CDNs) — fetched by the browser, not the server [server.py:HTML_TEMPLATE]

## Verification
- Run: `python -m pytest real_estate_intelligence/tests`
