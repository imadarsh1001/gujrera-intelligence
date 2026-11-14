# gujRERA Blueprint

## System Overview

This workspace holds the GujRERA sovereign real-estate intelligence platform for Gujarat (India) regulatory filings, organized as **two decoupled git repositories**:

1. **Public repo** (`gujrera-intelligence`, this root): the `real_estate_intelligence/` analysis platform plus shared docs.
2. **Private repo** (`gujrera-pipeline`, sibling repository at `../gujrera_pipeline`): the collection pipeline that crawls `https://gujrera.gujarat.gov.in` into immutable, hash-verified run archives and ZSTD Parquet data lakes.

The data seam between the repos is a **run directory**: the pipeline writes runs (gzip raw responses + `manifest.sqlite`); the intelligence platform's read-side (`DiskRunReader`, read-only SQLite `mode=ro`) consumes those run directories and ingests them into a curated SQLite database (`real_estate_intelligence/data/intelligence.sqlite`), from which analytics, knowledge graph, MCP tools, agent, and UI read.

Execution surfaces (all grounded in child contracts): a 14-subcommand CLI (`python -m real_estate_intelligence`), a stdlib multi-threaded HTTP dashboard (`ThreadingHTTPServer`, bound to `127.0.0.1:8765`, serving `ui/static/` with vendored assets), an in-process MCP tool class (no network listener), and a rate-limited collector with bounded `ThreadPoolExecutor` fan-out.

Root-level files:

- [README.md](./README.md) - human-facing platform introduction (kept separate from this contract; do not merge)
- [GLOSSARY.md](./GLOSSARY.md), [SHOWCASE.md](./SHOWCASE.md) - terminology and feature walkthrough
- [requirements.txt](./requirements.txt) / [requirements-dev.txt](./requirements-dev.txt) - installs `./real_estate_intelligence` editable plus `pypdf` and `pytest`
- `docs/` - `LEARNINGS.md`, `SPEC.md`, `adr/0001-run-reader-ingestion-seam.md`, `adr/0002-columnar-parquet-data-lake-and-document-manifest.md`, and `reviews/` (the EGM review audit trail: drift report + review report) (documentation-only, no code contract)

## Local Interface & Invariants

- `run_server.py` - launcher: inserts the sibling `real_estate_intelligence` package root into `sys.path`, then calls `cli.main()`; with no arguments it rewrites `sys.argv` to `serve --port 8765` [run_server.py:main]
- Invariant: no Python source or synchronization wrapper scripts live at the workspace root other than `run_server.py`; all platform code lives in `real_estate_intelligence/`
- Side effect: `run_server.py` starts the local dashboard server (TCP bind on `127.0.0.1:{port}`, default 8765)

## Subdirectories & System Boundaries

- `real_estate_intelligence/`: [./real_estate_intelligence/EGM.md](./real_estate_intelligence/EGM.md) - public-repo analysis platform: curated SQLite schema, FTS document search, knowledge graph, seven read-only analytics engines, MCP tool class, LLM copilot agent, stdlib HTTP UI, operational scripts
- `staging_from_pipeline/`: isolated staging folder for candidate consumer modules migrated from `gujrera_pipeline` per ADR-0004; deferred for dedicated review
- `docs/`: documentation-only, no code contracts
- `../gujrera_pipeline/`: separate **private repository** (`gujrera-pipeline` on GitHub) - collection pipeline: rate-limited fetch layer, immutable hash-verified run archives, ZSTD Parquet lakes, dossiers, offline readers; legacy crawler/data captures migrated to `../gujrera_pipeline/staging_from_intelligence/`

## Global Invariants

- **Dual-repo boundary**: the private pipeline and public platform are sovereign, decoupled git repositories (ADR-0004); each is version-controlled and pushed independently using standard Git commands
- **Run-archive seam**: pipeline runs are immutable and SHA-256 hash-verified (gzip written via `.part` + `os.replace`); the read side opens `manifest.sqlite` strictly `mode=ro` and raises `FileNotFoundError` when absent [storage.py:write_json], [export.py:verify], [reader.py:DiskRunReader]
- **Cross-repo source seam**: `real_estate_intelligence/config.py` and `__init__.py` resolve `_PIPELINE_DIR` via `GUJRERA_PIPELINE_DIR` env var or `WORKSPACE_ROOT.parent / "gujrera_pipeline"`; `DEFAULT_SOURCE_RUN` resolves via `GUJRERA_SOURCE_RUN` env var or `_PIPELINE_DIR/data/runs/nine_projects_2026_10_15` [config.py]
- **Privacy redaction in code**: both pipeline generations exclude identity documents (`pancard`, `photograph`, `aadhar/aadhaar`, `kyc`, `passport`), booking/photos/promoter endpoints, and fixed redacted export field lists [export.py:FIELDS], [documents.py:EXCLUDED_PATH_TERMS], [download_project_documents.py:IDENTITY_TERMS]
- **Write-boundary discipline**: only the pipeline (collection/exports), the ingest path (`db.loader`, `db.fts`, `graph`, `documents.worker`, `scripts/run_ingest.py`), and agent-side LLM calls mutate state; analytics/MCP/UI read-only over the shared connection
- **Escrow semantics encoded once**: `banks.account_type` `1` = 70% retention/escrow, `2` = 100% collection, interpreted identically by loader, audit, and MCP layers [schema.py:BankRecord]

## Global Side Effects

- **Network**: `https://gujrera.gujarat.gov.in` (pipeline collectors, both generations), Gemini/OpenAI APIs via `urllib.request` when an API key is present (`agent/copilot.py`), and MapTiler basemap tiles fetched browser-side by the Explore map only when the user configures their own key; all other browser assets (Tailwind, Font Awesome, vis-network, Chart.js, MapLibre GL) are vendored under `real_estate_intelligence/real_estate_intelligence/ui/static/vendor/` and served locally
- **Disk**: `gujrera_pipeline/data/runs/<run-id>/` archives (manifest.sqlite WAL + `.json.gz` + exports/reports/derived), `gujrera_pipeline/data/indexes/*.parquet` + `documents_manifest.parquet`, `real_estate_intelligence/data/intelligence.sqlite` (+ WAL/SHM; created at `config.py` import time), `graph_nodes`/`graph_edges` tables in the curated DB
- **Sockets**: local dashboard binds `127.0.0.1:8765` (default); `scripts/verify_server.py` probes `127.0.0.1:8999`; legacy ScrapydWeb settings bind `0.0.0.0:5000` when deployed

## System Verification

- Public platform tests: `python -m pytest real_estate_intelligence/tests`
- Private pipeline tests: `python -m pytest gujrera_pipeline/tests`
- Launch dashboard: `python run_server.py` (or `python -m real_estate_intelligence serve --port 8765`)
