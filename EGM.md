# gujRERA Blueprint

## System Overview

This workspace holds the GujRERA sovereign real-estate intelligence platform for Gujarat (India) regulatory filings, organized as **two git repositories in one tree**:

1. **Public repo** (`gujrera-intelligence`, this root): the `real_estate_intelligence/` analysis platform plus shared docs. Its `.gitignore` excludes the private pipeline, raw data, and legacy material.
2. **Private repo** (`gujrera-pipeline`, nested at `gujrera_pipeline/.git`): the `gujrera_pipeline/` collection pipeline that crawls `https://gujrera.gujarat.gov.in` into immutable, hash-verified run archives.

The data seam between the repos is a **run directory**: the pipeline writes `gujrera_pipeline/data/runs/<run-id>/` (gzip raw responses + `manifest.sqlite`); the intelligence platform's read-side (`DiskRunReader`, read-only SQLite `mode=ro`) consumes those run directories and ingests them into a curated SQLite database (`real_estate_intelligence/data/intelligence.sqlite`), from which analytics, knowledge graph, MCP tools, agent, and UI read.

Execution surfaces (all grounded in child contracts): a 14-subcommand CLI (`python -m real_estate_intelligence`), a stdlib multi-threaded HTTP dashboard (`ThreadingHTTPServer`, bound to `127.0.0.1:8765`, serving `ui/static/` with vendored assets), an in-process MCP tool class (no network listener), and a rate-limited curl-based collector with bounded `ThreadPoolExecutor` fan-out.

Root-level files:

- [README.md](./README.md) - human-facing platform introduction (kept separate from this contract; do not merge)
- [GLOSSARY.md](./GLOSSARY.md), [SHOWCASE.md](./SHOWCASE.md) - terminology and feature walkthrough
- [requirements.txt](./requirements.txt) / [requirements-dev.txt](./requirements-dev.txt) - installs `./real_estate_intelligence` editable plus `pypdf` and `pytest`
- `docs/` - `LEARNINGS.md`, `SPEC.md`, `adr/0001-run-reader-ingestion-seam.md`, `adr/0002-columnar-parquet-data-lake-and-document-manifest.md`, and `reviews/` (the EGM review audit trail: drift report + review report) (documentation-only, no code contract)
- `collected_data/`, `raw_data/` - raw CSV captures (private, gitignored, no code contract)

## Local Interface & Invariants

- `run_server.py` - launcher: inserts the sibling `real_estate_intelligence` package root into `sys.path`, then calls `cli.main()`; with no arguments it rewrites `sys.argv` to `serve --port 8765` [run_server.py:main]
- `push_all.bat` / `push_all.ps1` - dual-repo sync helpers: `git add .` + conditional commit + `git push origin main` in the outer repo, then the same inside `gujrera_pipeline/` [push_all.bat:sync sections], [push_all.ps1:Push-Location block]
  - Invariant: both scripts are branch-safe: they `git fetch origin` first, abort when the checked-out branch is not `main` (unless `-AllowNonMain` / `--allow-non-main` is passed), push `git push origin HEAD:main`, abort on a non-fast-forward (`origin/main` ahead of local), and print success only after `ls-remote` confirms the remote ref matches local HEAD; the two pushes are independent and never auto-retried
- Invariant: no Python source lives at the workspace root other than `run_server.py`; all code lives in the two repo trees documented below
- Side effect: `run_server.py` starts the local dashboard server (TCP bind on `127.0.0.1:{port}`, default 8765)

## Subdirectories & System Boundaries

- `real_estate_intelligence/`: [./real_estate_intelligence/EGM.md](./real_estate_intelligence/EGM.md) - public-repo analysis platform: curated SQLite schema, FTS document search, knowledge graph, seven read-only analytics engines, MCP tool class, LLM copilot agent, stdlib HTTP UI, operational scripts
- `gujrera_pipeline/`: separate **private repository** (`gujrera-pipeline` on GitHub; not present in this public clone) - collection pipeline: rate-limited curl fetch layer, immutable hash-verified run archives, redacted exports, dossiers, legacy importer, offline readers, experiments; its contract tree (`EGM.md` at the repo root, `experiments/`, `data/`, `data/discovery/`) lives in that repository
- `legacy/`: deprecated archive kept local via `.gitignore` (2023-2026 scrapy crawler, research capture scripts, EDA notebooks/Streamlit prototype; superseded by `gujrera_pipeline`) - its contract tree is local-only and not published
- `docs/`, `collected_data/`, `raw_data/` - no code contracts (docs-only / pure data captures)

## Global Invariants

- **Dual-repo boundary**: the private pipeline and public platform are separate git repos; `.gitignore` (outer) excludes `gujrera_pipeline/`, `legacy/`, `raw_data/`, `collected_data/`; `push_all.bat`/`push_all.ps1` synchronize both repos to their respective `origin main`
- **Run-archive seam**: pipeline runs are immutable and SHA-256 hash-verified (gzip written via `.part` + `os.replace`); the read side opens `manifest.sqlite` strictly `mode=ro` and raises `FileNotFoundError` when absent [storage.py:write_json], [export.py:verify], [reader.py:DiskRunReader]
- **Cross-repo source seam**: `real_estate_intelligence/config.py` and `__init__.py` insert `WORKSPACE_ROOT` into `sys.path` so the sibling `gujrera_pipeline` package is importable; `DEFAULT_SOURCE_RUN` resolves to `WORKSPACE_ROOT/gujrera_pipeline/data/runs/nine_projects_2026_10_15` [config.py]
- **Privacy redaction in code**: both pipeline generations exclude identity documents (`pancard`, `photograph`, `aadhar/aadhaar`, `kyc`, `passport`), booking/photos/promoter endpoints, and fixed redacted export field lists [export.py:FIELDS], [documents.py:EXCLUDED_PATH_TERMS], [download_project_documents.py:IDENTITY_TERMS]
- **Write-boundary discipline**: only the pipeline (collection/exports), the ingest path (`db.loader`, `db.fts`, `graph`, `documents.worker`, `scripts/run_ingest.py`), and agent-side LLM calls mutate state; analytics/MCP/UI read-only over the shared connection
- **Escrow semantics encoded once**: `banks.account_type` `1` = 70% retention/escrow, `2` = 100% collection, interpreted identically by loader, audit, and MCP layers [schema.py:BankRecord]

## Global Side Effects

- **Network**: `https://gujrera.gujarat.gov.in` (pipeline collectors, both generations), Gemini/OpenAI APIs via `urllib.request` when an API key is present (`agent/copilot.py`), CDN assets fetched browser-side by the UI template (Tailwind, vis-network, Chart.js)
- **Disk**: `gujrera_pipeline/data/runs/<run-id>/` archives (manifest.sqlite WAL + `.json.gz` + exports/reports/derived), `gujrera_pipeline/data/indexes/*.parquet` + `documents_manifest.parquet`, `real_estate_intelligence/data/intelligence.sqlite` (+ WAL/SHM; created at `config.py` import time), `graph_nodes`/`graph_edges` tables in the curated DB
- **Sockets**: local dashboard binds `127.0.0.1:8765` (default); `scripts/verify_server.py` probes `127.0.0.1:8999`; legacy ScrapydWeb settings bind `0.0.0.0:5000` when deployed

## System Verification

- Public platform tests: `python -m pytest real_estate_intelligence/tests`
- Private pipeline tests: `python -m pytest gujrera_pipeline/tests`
- Launch dashboard: `python run_server.py` (or `python -m real_estate_intelligence serve --port 8765`)
