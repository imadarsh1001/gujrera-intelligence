# ui — Zero-Dependency HTTP Dashboard & Deterministic Copilot

## Overview
Standard-library web server (`http.server`) serving the single-page dashboard from `ui/static/` (`index.html` plus vendored, version-pinned assets in `static/vendor/` — Tailwind Play runtime, Font Awesome 6.4.0 + webfonts, vis-network 9.1.9, Chart.js 4.4.4 — so the UI renders fully offline) plus a JSON API over the analytics stack. Also hosts a deterministic, keyword-routed diligence copilot (`_handle_copilot_query`) that first tries the agentic LLM from `agent.copilot` when an API key is available and otherwise synthesizes cited answers offline. Bound to `127.0.0.1` only.

## Interface
HTTP routes on `IntelligenceRequestHandler` [server.py:IntelligenceRequestHandler]:

| Method | Route | Handler / Source |
|---|---|---|
| GET | `/`, `/index.html` | serves `static/index.html` from disk (`_read_static`, cached in-process) [server.py:do_GET] |
| GET | `/static/{path}` | serves files under `ui/static/` with a resolved-path traversal guard; typed by suffix (`.html`, `.js`, `.css`, `.woff2`, …), 404 outside the directory [server.py:do_GET] |
| GET | `/api/projects` | project list rows [server.py:do_GET] |
| GET | `/api/explore` | one pre-aggregated row per project for the Explore table: identity/registration/location fields, `completion_date`, `progress_pct`, `latitude`/`longitude` (filings' recorded GPS), `complaints_count`, `extensions_count`, `filings_count`, `latest_filing_date`, `days_since_latest_filing` (server-computed UTC), `revision_state` (`revision_observed` \| `no_revision_observed` \| `insufficient_history`) with `revision_evidence_dates`, `unit_types`, BOOKED-only price aggregates (`min_price_booked`, `min_rate_sqft_booked`, `price_date_min/max`, per-type in `booked_by_unit_type`), `architects` [server.py:_explore_rows] |
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
- `start_server(port=8765, db_path=None)` — constructs `ThreadingHTTPServer(("127.0.0.1", port), ...)`, sets `daemon_threads = True`, and serves until KeyboardInterrupt [server.py:start_server]
- Package export: `start_server` [__init__.py:__all__]

## Invariants
- All backends are class-level attributes shared by every request; `setup_backends` must be called before serving (it is invoked by `start_server`) [server.py:IntelligenceRequestHandler]
- Unknown routes return HTTP 404 (`send_error(404, "Endpoint not found")`); malformed numeric query parameters on `/api/verify_claim`, `/api/search`, and the `/api/analytics/*` routes return HTTP 400; JSON responses are always HTTP 200 with `Content-Type: application/json; charset=utf-8`, serialized with `default=str` and `allow_nan=False` (degenerate NaN/Inf aggregates are nulled out rather than emitted) [server.py:_send_json]
- Copilot API key fallback chain: request body `api_key`, then env `GEMINI_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY` [server.py:do_POST]
- `_handle_copilot_query` tries `AgenticCopilot.run_query` first when a key and backend exist and silently falls back to the deterministic keyword router on failure; with no key it is fully offline and deterministic [server.py:_handle_copilot_query]
- The deterministic router matches intents in fixed order (greeting/help, architecture/credentials, buy-advice, lifecycle, launch date, sales/inventory, title/mortgage, escrow, delay/survival, pricing/CAGR, contagion/network) with a full-text-search fallback; a `project_id <= 0` is replaced by the lowest project ID in the database [server.py:_handle_copilot_query]
- The server binds to `127.0.0.1` (not `0.0.0.0`) and is multi-threaded (`ThreadingHTTPServer` with `daemon_threads = True`) so a slow request such as an agentic LLM copilot call cannot block other dashboard requests; concurrent requests are safe because all handlers share the single SQLite connection created with `check_same_thread=False` and a 30 s `busy_timeout` (SQLite's serialized threading mode is the actual guarantee — WAL governs cross-connection access, and this server opens exactly one connection). Construction-time writes exist (`KnowledgeGraph.__init__` creates graph tables; `get_connection` applies pragmas/schema) but request handling is read-only; the MCP layer's lazy model training is lock-serialized [server.py:start_server]
- The dashboard is served from `ui/static/` on disk (`index.html` + `static/vendor/`), never embedded in the Python source; `_read_static` resolves every request path and refuses anything outside `STATIC_DIR`; file contents are cached in-process after first read [server.py:_read_static]
- Explore revision semantics: `revision_observed` requires ≥2 filings AND ≥1 Extension application row (approval status is not disclosed by the source); `no_revision_observed` requires ≥2 filings and no extension rows; `insufficient_history` is <2 filings. Price aggregates cover `status = 'BOOKED'` unit transactions only [server.py:_explore_rows], [server.py:_revision_state]

## Side Effects
- Opens a shared SQLite connection and instantiates all analytics backends in `setup_backends` (schema/pragmas applied via `get_connection`) [server.py:setup_backends]
- Listens on a TCP socket at `127.0.0.1:{port}` (default 8765) and prints `[READY] ...` to stdout [server.py:start_server]
- `POST /api/copilot` may trigger outbound LLM API calls through `AgenticCopilot` when a key is present (network side effect) [server.py:_handle_copilot_query]
- Serves vendored assets from `ui/static/vendor/` (Tailwind Play runtime, Font Awesome 6.4.0 CSS + webfonts, vis-network 9.1.9, Chart.js 4.4.4) — no client-side CDN fetches; the dashboard renders fully offline [server.py:do_GET]

## Verification
- Run: `python -m pytest real_estate_intelligence/tests`
