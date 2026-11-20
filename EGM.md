# gujRERA Blueprint

## System Overview

This workspace holds the GujRERA sovereign real-estate intelligence platform for Gujarat (India) regulatory filings, organized as **two decoupled git repositories**:

1. **Public repo** (`gujrera-intelligence`, this root): the `real_estate_intelligence/` analysis platform plus shared docs.
2. **Private repo** (`gujrera-pipeline`, sibling repository at `../gujrera_pipeline`): the collection pipeline that crawls `https://gujrera.gujarat.gov.in` into immutable, hash-verified run archives and ZSTD Parquet data lakes.

Data architecture: The curated SQLite database (`real_estate_intelligence/data/intelligence.sqlite`) provides the local fact base from which analytics, knowledge graph, MCP tools, copilot agent, and FastAPI web application read. All shared database access and analytical rollups are centralized in the single SQL seam [`real_estate_intelligence/db/queries.py`](real_estate_intelligence/real_estate_intelligence/db/queries.py).

Execution surfaces:
- A 14-subcommand CLI (`python -m real_estate_intelligence`).
- A high-throughput FastAPI ASGI dashboard (`api/index.py`) launched via `uvicorn` (`run_server.py` or CLI `serve`), bound to `127.0.0.1:8765`, serving the static single-page interface and vendored offline assets from `ui/static/`.
- An in-process MCP tool class (`RealEstateIntelligenceMCP`, no network listener).

Root-level files:

- [README.md](./README.md) - human-facing platform introduction (kept separate from this contract; do not merge)
- [GLOSSARY.md](./GLOSSARY.md), [SHOWCASE.md](./SHOWCASE.md) - terminology and feature walkthrough
- [requirements.txt](./requirements.txt) / [requirements-dev.txt](./requirements-dev.txt) - installs `./real_estate_intelligence` editable plus `fastapi`, `uvicorn`, `pypdf`, `pytest`, and `httpx2`
- `docs/` - `LEARNINGS.md`, `SPEC.md`, `adr/0001-run-reader-ingestion-seam.md`, `adr/0002-columnar-parquet-data-lake-and-document-manifest.md`, `adr/0003-fastapi-consolidation.md`, and `reviews/` (audit trail kept locally, not distributed in the repo)

## Local Interface & Invariants

- `run_server.py` - launcher: launches uvicorn with `api.index:app` on `127.0.0.1:{port}` (default 8765); CLI `serve` (`real-estate-intelligence serve`) also delegates to uvicorn with `api.index:app` [run_server.py]
- Invariant: no Python source or synchronization wrapper scripts live at the workspace root other than `run_server.py`; all platform code lives in `real_estate_intelligence/` and `api/`
- Side effect: `run_server.py` starts the local dashboard server (TCP bind on `127.0.0.1:{port}`, default 8765)

## Subdirectories & System Boundaries

- `real_estate_intelligence/`: [./real_estate_intelligence/EGM.md](./real_estate_intelligence/EGM.md) - public-repo analysis platform: curated SQLite schema, FTS document search, knowledge graph, seven read-only analytics engines, MCP tool class, LLM copilot agent, operational scripts, and shared query seam
- `api/`: FastAPI web application (`api/index.py`), mounting `ui/static` and exposing 15 core JSON API routes
- `docs/`: documentation-only, no code contracts
- `../gujrera_pipeline/`: separate **private repository** (`gujrera-pipeline` on GitHub) - collection pipeline: rate-limited fetch layer, immutable hash-verified run archives, ZSTD Parquet lakes, dossiers, offline readers

## Global Invariants

- **Dual-repo boundary**: the private pipeline and public platform are sovereign, decoupled git repositories; each is version-controlled and pushed independently using standard Git commands
- **Single SQL seam**: all database queries, facet extractions, project dossier queries, and revision-state heuristics are centralized in `real_estate_intelligence/db/queries.py`
- **FastAPI / ASGI runtime**: the application uses a single FastAPI application (`api/index.py`) launched via uvicorn; stdlib `ThreadingHTTPServer` is retired
- **15 Active Routes**: `/`, `/static/{path}`, `/api/health`, `/api/map/pins`, `/api/projects`, `/api/project/{pid}`, `/api/pricing/{pid}`, `/api/explore`, `/api/explore/facets`, `/api/graph`, `/api/analytics/survival`, `/api/analytics/pricing_trend`, `/api/analytics/ml_pricing`, `/api/verify_claim`, `/api/search`, `/api/map/config`, `/api/maptiler/{path}`, `/api/copilot`
- **Privacy redaction in code**: identity documents (`pancard`, `photograph`, `aadhar/aadhaar`, `kyc`, `passport`), booking/photos/promoter endpoints are excluded from public distribution
- **Write-boundary discipline**: only ingestion and document workers mutate state; analytics, MCP, copilot, and FastAPI are read-only over the shared database connection
- **Escrow semantics encoded once**: `banks.account_type` `1` = 70% retention/escrow, `2` = 100% collection, interpreted identically across all layers

## Global Side Effects

- **Network**: `https://gujrera.gujarat.gov.in` (pipeline collectors), Gemini/OpenAI APIs when an API key is provided (`agent/copilot.py` or copilot UI drawer), and optional MapTiler basemap proxy; all frontend assets (Tailwind, Font Awesome, vis-network, Chart.js, MapLibre GL) are vendored under `real_estate_intelligence/real_estate_intelligence/ui/static/vendor/` and served locally
- **Disk**: `real_estate_intelligence/data/intelligence.sqlite` (+ WAL/SHM), `graph_nodes` (21,836 nodes) / `graph_edges` (51,069 edges; 1,612 shared cross-project professionals) tables in the curated DB
- **Sockets**: local dashboard binds `127.0.0.1:8765` (default)

## System Verification

- Public platform tests: `python -m pytest real_estate_intelligence/tests` (62 passing tests)
- Launch dashboard: `python run_server.py` (or `python -m real_estate_intelligence serve --port 8765`)
