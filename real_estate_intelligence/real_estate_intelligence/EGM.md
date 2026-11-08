# real_estate_intelligence — Application Core: CLI, Configuration & Composition Root

## Overview
Application core of the GujRERA Real Estate Intelligence platform. `cli.py` defines the `real-estate-intelligence` console entry point (declared in `pyproject.toml` as `real_estate_intelligence.cli:main`) with 14 subcommands covering ingestion, every analytics engine, the dashboard server, and an evaluation harness. `config.py` resolves all filesystem constants; `__init__.py`/`__main__.py` handle package identity and `python -m` execution. This directory composes all eight child subsystems below.

## Interface
### CLI subcommands (argparse, `main()` dispatches via `args.func`) [cli.py:main]
- `ingest` `--source --target` — `DiskRunReader` + `ingest_from_run`, then builds the Knowledge Graph [cli.py:cmd_ingest]
- `dossier` `--project-id --db --output` — prints or writes the institutional Markdown dossier [cli.py:cmd_dossier]
- `pricing` `--project-id --db` — registered unit-rate benchmarks [cli.py:cmd_pricing]
- `claims` `--project-id --claimed-rate --claimed-sold --claimed-date --db` — broker claim fact-check [cli.py:cmd_claims]
- `search` `--query --project-id --db --limit` — FTS document search (limit default 5) [cli.py:cmd_search]
- `network` `--project-id --db` — shared-entity and contagion trace [cli.py:cmd_network]
- `audit` `--project-id --db` — discrepancy audit; audits all projects when `--project-id` is omitted [cli.py:cmd_audit]
- `serve` `--port --db` — launches the dashboard (port default 8765) [cli.py:cmd_serve]
- `runway` `--project-id --db` — escrow burn-rate and cash runway [cli.py:cmd_runway]
- `spatial` `--project-id --radius --db` — micro-market radius analysis (radius default 3.0 km) [cli.py:cmd_spatial]
- `docworker` `--batch-size --db` — drains the `document_jobs` queue (batch default 10) [cli.py:cmd_docworker]
- `ml-price` `--project-id --asset-class --carpet-area --estimators --depth --db` — GBDT SHAP valuation (`--asset-class` restricted to `Residential`, `Commercial_Office`, `Commercial_Retail`, `Industrial_Warehouse`) [cli.py:cmd_ml_price]
- `survival` `--project-id --db` — Cox delay forecast with Harrell C-index [cli.py:cmd_survival]
- `eval` `--db` — imports and runs `tests.eval_harness.EvaluationHarness` [cli.py:cmd_eval]

### Configuration constants [config.py]
- `PACKAGE_ROOT`, `WORKSPACE_ROOT` — path anchors derived from `__file__` [config.py:PACKAGE_ROOT]
- `DEFAULT_SOURCE_RUN` — `WORKSPACE_ROOT/gujrera_pipeline/data/runs/nine_projects_2026_10_15` (raw input from the sibling `gujrera_pipeline` package, outside this subtree) [config.py:DEFAULT_SOURCE_RUN]
- `DEFAULT_DATA_DIR`, `DEFAULT_DB_PATH` (`data/intelligence.sqlite`), `DEFAULT_GRAPH_DB_PATH` [config.py:DEFAULT_DB_PATH]
- `__version__ = "0.1.0"` [__init__.py:__version__]
- `python -m real_estate_intelligence` entry: imports `main` from `cli` [__main__.py]

### Child subsystem contracts
- [agent](./agent/EGM.md) — Agentic LLM copilot with MCP tool calling
- [analytics](./analytics/EGM.md) — forensic audit, claims, dossier, ML pricing, spatial, survival
- [db](./db/EGM.md) — SQLite persistence, FTS5, loader, RunReader seam
- [documents](./documents/EGM.md) — PDF extraction, classification, async indexing worker
- [graph](./graph/EGM.md) — knowledge graph and contagion tracing
- [mcp](./mcp/EGM.md) — MCP tool server facade over analytics
- [models](./models/EGM.md) — typed dataclass contracts
- [ui](./ui/EGM.md) — HTTP dashboard and deterministic copilot

## Invariants
- Every subcommand is required: `add_subparsers(dest="command", required=True)` — running with no command exits with an argparse error [cli.py:main]
- All database-touching subcommands accept `--db` defaulting to [config.py:DEFAULT_DB_PATH]; `ingest` alone writes (`--target`), everything else reads [cli.py:main]
- `main()` reconfigures `sys.stdout`/`sys.stderr` to UTF-8 with `errors="replace"` before any output [cli.py:main]
- Both `config.py` and `__init__.py` insert `WORKSPACE_ROOT` into `sys.path` so the sibling `gujrera_pipeline` package stays importable [config.py], [__init__.py]
- `cmd_eval` deliberately reaches into the pruned test tree (`tests.eval_harness`), with a fallback to the installed-package path [cli.py:cmd_eval]
- `cmd_dossier` creates the parent directory of `--output` before writing the report file [cli.py:cmd_dossier]

## Side Effects
- `config.py` creates `real_estate_intelligence/data/` at import time (`DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)`) [config.py]
- `ingest` writes the target SQLite database, FTS index, and graph tables, then prints JSON stats [cli.py:cmd_ingest]
- `serve` binds a TCP socket on `127.0.0.1:{port}` and blocks until interrupted (see [ui/server.py:start_server]) [cli.py:cmd_serve]
- `dossier --output` writes a Markdown file to an arbitrary caller-specified path [cli.py:cmd_dossier]
- `ml-price` / `survival` perform CPU-heavy model training over the database on each invocation (no caching across CLI runs) [cli.py:cmd_ml_price], [cli.py:cmd_survival]

## Verification
- Run: `python -m pytest real_estate_intelligence/tests`
- Console script declared in `pyproject.toml`: `real-estate-intelligence = "real_estate_intelligence.cli:main"` (dev dependency `pytest>=8.0.0`)
