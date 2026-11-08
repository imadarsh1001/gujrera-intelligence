# scripts — Operational Maintenance Scripts

## Overview
Standalone operational scripts (run directly, not installed): rebuild the curated database from the default raw run (`run_ingest.py`), rebuild and inspect the knowledge graph (`build_graph.py`), and smoke-test the dashboard HTTP endpoints against the live database (`verify_server.py`). All three import the installed `real_estate_intelligence` package; `run_ingest.py` and `build_graph.py` reconfigure stdout to UTF-8 before printing (`verify_server.py` does not).

## Interface
- `run_ingest.py::main()` — deletes the existing default database, re-ingests `DEFAULT_SOURCE_RUN` with `index_documents=True`, then `VACUUM`s and reports final DB size and per-metric stats [run_ingest.py:main]
- `build_graph.py::main()` — connects to the default database, runs `KnowledgeGraph.build_graph()`, then lists cross-project shared professionals via a direct SQL group-by over `graph_edges` restricted to relations `ENGINEERED_BY`, `DESIGNED_BY`, `AUDITED_BY` with `p_count > 1` [build_graph.py:main]
- `verify_server.py::test_endpoints()` — initializes backends via `IntelligenceRequestHandler.setup_backends()` on an ephemeral `HTTPServer` at `127.0.0.1:8999` in a daemon thread and exercises `/api/projects`, `/api/graph`, `/api/project/13560`, `/api/search`, `/api/pricing/13560`, and `/` [verify_server.py:test_endpoints]
- Each file is executable as `python scripts/<name>.py` via its `if __name__ == "__main__"` block [run_ingest.py], [build_graph.py], [verify_server.py]

## Invariants
- Scripts always operate on the default paths defined in [../real_estate_intelligence/config.py:DEFAULT_DB_PATH] and [../real_estate_intelligence/config.py:DEFAULT_SOURCE_RUN] — they accept no CLI arguments [run_ingest.py:main], [build_graph.py:main]
- `verify_server.py` probes the fixed project ID `13560` and the fixed port `8999`, and always calls `srv.shutdown()` in a `finally` block [verify_server.py:test_endpoints]
- The shared-professionals query in `build_graph.py` filters to exactly three relations; `CONSTRUCTED_BY` and `ESCROW_AT` overlaps are not reported [build_graph.py:main]

## Side Effects
- Destructive: `run_ingest.py` unlinks `real_estate_intelligence/data/intelligence.sqlite` before re-ingesting ("Removing existing DB to apply upgraded schema..."), rewrites the database and FTS index, and executes `VACUUM` [run_ingest.py:main]
- `build_graph.py` rewrites `graph_nodes`/`graph_edges` rows in the default database [build_graph.py:main]
- `verify_server.py` binds a local TCP socket on port `8999` and issues HTTP requests to it; it writes no data rows, but `setup_backends()` applies schema pragmas/DDL via `get_connection` (which creates the default database if absent) [verify_server.py:test_endpoints]

## Verification
- Run: `python -m pytest real_estate_intelligence/tests`
