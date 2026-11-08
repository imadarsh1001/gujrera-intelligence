# real_estate_intelligence — Subtree Blueprint

## Overview
`real_estate_intelligence` is an installable Python package (setuptools, `requires-python >= 3.11`, runtime dependency `pypdf>=5.0.0`, dev dependency `pytest>=8.0.0`) implementing an evidence-backed due-diligence platform for GujRERA (the Gujarat Real Estate Regulatory Authority; see [GLOSSARY.md](../GLOSSARY.md)): raw collection runs are ingested into a curated WAL-mode SQLite database with an FTS5 document index and a relational knowledge graph, and eight subsystems (`models`, `db`, `documents`, `analytics`, `graph`, `mcp`, `agent`, `ui`) expose analytics, an MCP tool server, an agentic LLM copilot, and a local web dashboard on top of it. The console script `real-estate-intelligence` maps to `real_estate_intelligence.cli:main` [pyproject.toml].

Data flow: `gujrera_pipeline` raw runs (sibling package outside this subtree, resolved by [real_estate_intelligence/config.py:DEFAULT_SOURCE_RUN]) -> `db.loader.ingest_from_run` -> `data/intelligence.sqlite` (tables + `document_fts` + `graph_nodes`/`graph_edges`) -> `analytics`, `graph`, `documents`, `mcp`, `agent`, and `ui` subsystems (read-side except `documents.worker`, which mutates job rows; see Global Invariants) -> `cli.py` subcommands and `ui/server.py` HTTP routes.

## Subdirectories & Boundaries
- [real_estate_intelligence](./real_estate_intelligence/EGM.md) - Application core package: CLI (14 subcommands), configuration constants, and composition root linking the eight subsystem contracts
- [scripts](./scripts/EGM.md) - Operational maintenance scripts: destructive DB rebuild, graph rebuild/inspect, and dashboard endpoint smoke test
- `data/` - Generated SQLite artifacts (`intelligence.sqlite`, `test_intelligence.sqlite`); build outputs of ingestion, pruned from documentation by design
- `tests/` - Pytest suite and `eval_harness.py`; test-only, referenced solely through the Verification section
- `pyproject.toml` - Package manifest: dependencies, console script, setuptools package discovery
- `README.md` - Human-maintained project README (non-contract asset; intentionally not modified by this blueprint)

## Global Invariants
- All subsystems share a single SQLite database contract defined in `db.database.init_schema` (15 tables, 2 views); the WAL pragma, `foreign_keys = ON`, and schema auto-migration apply to every connection in the process [real_estate_intelligence/db/EGM.md]
- `WORKSPACE_ROOT` is inserted into `sys.path` by both `real_estate_intelligence/__init__.py` and `config.py`, so the sibling `gujrera_pipeline` raw-data package is always importable [real_estate_intelligence/EGM.md]
- Read/write boundary: only `db.loader`, `db.fts`, `graph.build_graph`, `documents.worker`, and the `ingest` and `docworker` CLI subcommands (`cli.py:cmd_ingest`, `cli.py:cmd_docworker`) mutate the database — plus the `eval` subcommand's harness, which seeds benchmark FTS rows via `db.fts.index_page_text` when the index is empty [tests/eval_harness.py:128-152]; `analytics`, `mcp`, `ui`, and `agent` are read-only consumers (their constructors may apply idempotent schema/DDL — via `get_connection`, or directly on the injected connection in `KnowledgeGraph.__init__`) [real_estate_intelligence/mcp/EGM.md]
- Escrow semantics are encoded once and reused everywhere: `banks.account_type = 1` is the 70% RERA retention escrow, `2` is the 100% collection account [real_estate_intelligence/models/EGM.md]
- Subsystem dependency direction is strict, with one deliberate seam. Import edges: `models` has no intra-package imports (neither does `config`); `db` imports `config`; `documents` imports `config` and `db`; `analytics` imports `config`, `db`, `models` (`audit.py` consumes `DiscrepancyLead`), and `graph` (`investor_dossier.py` composes `KnowledgeGraph`); `mcp` imports `analytics`, `db`, `documents`, and `graph`; `ui` imports `agent` (lazily, in `setup_backends`), `analytics`, `config`, `db`, `documents`, `graph`, and `mcp`; `cli` imports `analytics`, `db`, `documents`, `graph`, and `ui` (reaching `models` and `mcp` only transitively via `ui.server`, and `agent` never — it loads only inside `ui`'s `setup_backends`). `graph` and `agent` receive their collaborators by injection (`KnowledgeGraph` is handed a live connection; `AgenticCopilot` is handed the MCP server). The seam: `db.loader` imports `documents.parser` for inline PDF text extraction during ingestion, while `documents.worker` imports `db` for queue persistence — a mutual `db` ↔ `documents` dependency [real_estate_intelligence/db/loader.py:16, real_estate_intelligence/documents/worker.py:12-13]

## Global Side Effects
- Primary shared resource: `real_estate_intelligence/data/intelligence.sqlite` (plus WAL/SHM journals), created on demand by [real_estate_intelligence/config.py:DEFAULT_DB_PATH]; the directory itself is created at import time of `config.py`
- Outbound network calls occur only in `agent/copilot.py` (Gemini/OpenAI HTTP APIs, key-gated); the `ui` dashboard HTML additionally embeds browser-side CDN assets, and the server itself binds to `127.0.0.1` only [real_estate_intelligence/agent/EGM.md], [real_estate_intelligence/ui/EGM.md]
- `scripts/run_ingest.py` is destructive by design (deletes and rebuilds the default database) [real_estate_intelligence/scripts/EGM.md]
- Read-side input: `DiskRunReader` opens `manifest.sqlite` read-only and decompresses `.json.gz` raw filings from the `gujrera_pipeline` run directory [real_estate_intelligence/db/EGM.md]

## System Verification
- Run: `python -m pytest real_estate_intelligence/tests`
- The `eval` CLI subcommand imports `tests.eval_harness.EvaluationHarness` directly [cli.py:cmd_eval]
