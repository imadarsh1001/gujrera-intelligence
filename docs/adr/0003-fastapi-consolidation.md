# 0003. Single FastAPI Architecture Consolidation

## Context & Problem Statement

Prior to consolidation, the codebase suffered from architectural dual-server drift:
1. **Dual-Server Drift**: Two parallel HTTP server implementations co-existed:
   - `real_estate_intelligence/ui/server.py`: A standard-library `ThreadingHTTPServer` (bound to `127.0.0.1:8765`), historically maintained as the sovereign, zero-dependency dashboard runtime.
   - `api/index.py`: An untested, aspirational FastAPI application deployed or targeted for cloud serverless (Vercel).
2. **Route & Schema Mismatch**: Over time, endpoint implementations drifted. The frontend (`ui/static/index.html`) sent requests matching routes and payloads that worked on one server or the other, but not both. Specifically, `POST /api/copilot` expected `{query, project_id, api_key}` in the JSON body, which the aspirational FastAPI lacked or handled differently, and several analytics routes used inconsistent hyphen/underscore naming conventions (`/api/analytics/pricing_trend`, `/api/analytics/ml_pricing`, `/api/verify_claim`).
3. **Explore Timeout**: Under the standard-library multi-threaded server, aggregation queries for `/api/explore` across 17,787 projects suffered latency issues approaching 30-second client timeouts due to duplicate, unindexed SQL joins and repeated in-process Python loops.
4. **Duplicated SQL & Domain Logic**: Complex analytical aggregations (explore row building, revision state heuristics, project dossier collation, pricing summaries) were copy-pasted across servers rather than residing in a single, authoritative query seam.

## Decision

We eliminate the dual-server architecture entirely in favor of a single, unified **FastAPI** application (`api/index.py`), with an asynchronous ASGI architecture powered by `uvicorn`:

1. **Retire `ui/server.py`**: The stdlib `ThreadingHTTPServer` implementation is completely removed.
2. **Canonical SQL Seam (`real_estate_intelligence/db/queries.py`)**: All project aggregation queries, facet queries, explore rollups, and revision-state heuristics are centralized into a single tested query layer.
3. **Unified ASGI Launcher**: Both `run_server.py` at workspace root and `real-estate-intelligence serve` in `cli.py` launch `uvicorn.run("api.index:app", host="127.0.0.1", port=port)`.
4. **Exact Frontend Parity**: All 15 active routes required by the static single-page interface (`ui/static/index.html`) are natively implemented in FastAPI with exact route naming and typed request/response handling, including local offline fallback for the Copilot.
5. **Static Asset Mounting**: `ui/static/` is mounted via Starlette `StaticFiles` at `/static`, with `/` and `/index.html` serving the primary dashboard directly.
6. **Modern Async HTTP & TestClient Stack**: Adopted `httpx2` (migrated from `httpx` after community deprecation and verified through an identity and provenance gate) for test client verification.

## Consequences & Operational Reality

- **Launcher & Server Model**: All local serving is ASGI via `uvicorn`. The historic "zero external dependencies for serving" invariant is intentionally retired in favor of high-throughput ASGI, OpenAPI introspection, and async concurrency.
- **Vercel / Turso Reality**: The full statewide SQLite database (`intelligence.sqlite`) is **235 MB**, which approaches and often exceeds serverless uncompressed lambda limits (~250 MB). For serverless edge deployment (e.g. Vercel), remote Turso via `libsql` is required. Local development and sovereign workstation runs continue to execute directly against local SQLite with WAL mode.
- **Dependency Provenance**: `httpx` was deprecated by upstream tooling in favor of `httpx2`. We established an explicit provenance verification gate: verifying the PyPI package identity (`Tom Christie`, `Pydantic Services Inc.` / `pydantic/httpx2`) prior to installing `httpx2==2.16.2`.
- **Test Suite Verification**: Test coverage consolidated into `real_estate_intelligence/tests/test_fastapi_server.py` (36 tests), covering every endpoint, error handling, static asset delivery, and copilot fallback, bringing the full suite to 60 passing pytest tests.
