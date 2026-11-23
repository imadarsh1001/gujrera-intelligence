# db — Curated SQLite Persistence & Run Reader Seam

## Overview
Persistence layer for the curated intelligence database (`real_estate_intelligence/data/intelligence.sqlite` via [../config.py:DEFAULT_DB_PATH]), centralized in-memory PII redaction engine (`redaction.py`), consolidated query seam (`queries.py`), and the read-side seam over raw GujRERA collection runs. `database.py` owns connection setup and DDL, `redaction.py` guarantees 0 PII leaks across API and MCP surfaces, `queries.py` provides high-speed indexed rollups and insights data, `fts.py` owns the FTS5 full-text index, `loader.py` maps run snapshots into typed relational facts, and `reader.py` abstracts run access behind the `RunReader` interface.

## Interface
- `get_connection(db_path=None) -> sqlite3.Connection` — returns the passed connection unchanged if given one; otherwise connects (30 s timeout, `check_same_thread=False`, `row_factory = sqlite3.Row`), creates parent directories, and applies pragmas and schema [database.py:get_connection]
- `redact_value(key, value) -> Any`, `redact_record(record) -> dict`, `redact_payload(obj) -> Any` — Centralized PII scrubbing for PAN, Aadhaar, email, and bank account numbers while whitelisting RERA/CoA registration identifiers [redaction.py:redact_payload]
- `get_zombie_radar_data(con, limit=50) -> List[Dict]` — High-risk modern private schemes past completion deadline with no BU/NOC [queries.py:get_zombie_radar_data]
- `get_markup_spread_data(con) -> Dict` — Aggregate asking price markup and district breakdowns via covering index `idx_unit_status_rates` [queries.py:get_markup_spread_data]
- `get_developer_clusters_data(con, promoter_name=None) -> Dict` — Statewide developer brand overview or targeted Composite Key (c) clusters [queries.py:get_developer_clusters_data]
- `get_explore_rows(con, ...)` / `get_explore_facets(con)` / `get_project_detail(con, project_id)` / `get_graph_data(con, ...)` — Single source of truth SQL queries [queries.py]
- `init_schema(con)` — creates 15 tables (`projects`, `promoters`, `professionals`, `banks`, `inventory_blocks`, `quarterly_timeline`, `finances`, `form5_compliance`, `noc_bu_records`, `previous_projects`, `applications`, `documents_catalog`, `unit_transactions`, `document_jobs`, `market_listings`), 2 canonical views, covering indexes, and migration guards [database.py:init_schema]
- `init_fts(con)` / `index_page_text(...)` / `search_documents(con, query, ...)` / `DocumentSearchEngine.search(...)` [fts.py:DocumentSearchEngine]
- `ingest_from_run(source_run_or_reader, target_db_path, index_documents=True) -> Dict[str, int]` [loader.py:ingest_from_run]
- `RunReader` / `DiskRunReader` / `FakeRunReader` [reader.py:RunReader]

## Invariants
- Immutable Runtime Database: `data/intelligence.sqlite` is strictly read-only at runtime; no write queries are issued during API, MCP, or copilot execution [database.py], [queries.py]
- Zero PII Leakage: `redact_payload` recursively scrubs all dict/list payloads; `SENSITIVE_KEY_NAMES` includes `license_or_reg_no`, `account_no`, `email`, `shared_anchors`, `shared_licenses`, and `shared_banks` [redaction.py:SENSITIVE_KEY_NAMES]
- Covering Index Performance: `get_markup_spread_data` queries `idx_unit_status_rates` (`(project_id, status, unit_consideration, rate_per_sqft)`), guaranteeing fast aggregation across 1.95M unit deeds [queries.py:get_markup_spread_data]
- Verified Date Formatting: `project_summaries.completion_date` is strictly ISO `YYYY-MM-DD` format, enabling direct SQL range filtering and date arithmetic [queries.py:get_zombie_radar_data]
- Every connection enforces `PRAGMA journal_mode = WAL`, `PRAGMA foreign_keys = ON`, and `PRAGMA busy_timeout = 30000` [database.py:get_connection]

## Side Effects
- Database reads only during server execution; WAL journal files may be touched by SQLite engine during concurrent reads [database.py:get_connection]
- Ingestion mode (`ingest_from_run`) modifies curated tables during initial offline data preparation [loader.py:ingest_from_run]

## Verification
- Run test suites:
  - `python -m pytest real_estate_intelligence/tests/test_phase1_5_polish.py`
  - `python -m pytest real_estate_intelligence/tests/test_security_redaction_and_graph.py`
  - `python -m pytest real_estate_intelligence/tests/test_db_queries.py`
