# db — Curated SQLite Persistence & Run Reader Seam

## Overview
Persistence layer for the curated intelligence database (`real_estate_intelligence/data/intelligence.sqlite` via [../config.py:DEFAULT_DB_PATH]) and the read-side seam over raw GujRERA collection runs. `database.py` owns connection setup and DDL, `fts.py` owns the FTS5 full-text index, `loader.py` maps run snapshots into typed relational facts, and `reader.py` abstracts run access behind the `RunReader` interface (`DiskRunReader` for disk archives, `FakeRunReader` for tests).

## Interface
- `get_connection(db_path=None) -> sqlite3.Connection` — returns the passed connection unchanged if given one; otherwise connects (30 s timeout, `check_same_thread=False`, `row_factory = sqlite3.Row`), creates parent directories, and applies pragmas and schema [database.py:get_connection]
- `init_schema(con)` — creates 15 tables (`projects`, `promoters`, `professionals`, `banks`, `inventory_blocks`, `quarterly_timeline`, `finances`, `form5_compliance`, `noc_bu_records`, `previous_projects`, `applications`, `documents_catalog`, `unit_transactions`, `document_jobs`, `market_listings`), 2 canonical views (`v_current_projects`, `v_current_unit_transactions`), indexes, and forward-migration `ALTER TABLE` guards for `run_id` / `asset_class` [database.py:init_schema]
- `init_fts(con)` / `index_page_text(...)` / `sanitize_fts_query(query)` / `search_documents(con, query, ...)` / `DocumentSearchEngine.search(query, project_id, doc_type, limit)` — FTS5 index over `document_fts` with BM25 ranking and `<b>` snippets [fts.py:init_fts], [fts.py:search_documents], [fts.py:DocumentSearchEngine]
- `mask_account_number(acc)` — masks bank account numbers to `****` + last 4 characters [loader.py:mask_account_number]
- `parse_land_identifiers(address, loc_data)` — regex extraction of `tp_scheme`, `final_plot_no`, `survey_no` from address text when portal JSON lacks them [loader.py:parse_land_identifiers]
- `ingest_from_run(source_run_or_reader, target_db_path, index_documents=True) -> Dict[str, int]` — main ingestion entry point; returns a stats dict keyed by `projects`, `promoters`, `professionals`, `banks`, `inventory_blocks`, `unit_transactions`, `quarterly_progress`, `finances`, `form5_compliance`, `noc_bu_records`, `previous_projects`, `applications`, `documents_cataloged`, `document_pages_indexed`, `document_jobs_queued` [loader.py:ingest_from_run]
- `DocumentRef` — frozen dataclass referencing a cataloged document asset [reader.py:DocumentRef]
- `ProjectSnapshot` — lazy, cached observation of one project's filings; properties `project_details`, `form_three`, `index_form_three`, `form_one`, `form_two`, `locations`, `form_four`, `noc_bu`, `progress_reports`, `applications`, `quarter_index`, `promoter`, `previous_projects`, `banks`, `collection_accounts`, `qpr_progress`, `annual_compliance`, `unit_transactions`, plus `missing_endpoints` [reader.py:ProjectSnapshot]
- `RunReader` — abstract interface: `iter_snapshots`, `get_snapshot`, `iter_document_refs`, `resolve_document_path`, `counts`, `close`; usable as a context manager [reader.py:RunReader]
- `DiskRunReader(run_dir_or_root, run_id=None)` — production adapter over `manifest.sqlite` + `.json.gz` raw files [reader.py:DiskRunReader]
- `FakeRunReader(snapshots, document_refs, document_files, run_id="fake_run")` — in-memory adapter for testing downstream consumers without disk I/O [reader.py:FakeRunReader]

## Invariants
- Every connection enforces `PRAGMA journal_mode = WAL`, `PRAGMA foreign_keys = ON`, and `PRAGMA busy_timeout = 30000` [database.py:get_connection]
- `get_connection` runs `init_schema` on every call, so any obtained connection always has the full DDL applied [database.py:get_connection]
- `DiskRunReader` opens `manifest.sqlite` in read-only URI mode (`file:...?mode=ro`) and raises `FileNotFoundError` if it is absent; given a `runs/` root it selects the latest run by reverse-sorted directory name [reader.py:DiskRunReader]
- `ProjectSnapshot` caches missing endpoints as `{}` and records them in `missing_endpoints`; raw portal envelopes of the form `{"data": ..., "status": 200}` are unwrapped to the inner payload [reader.py:ProjectSnapshot._get_envelope]
- Unit-level rates are derived, not stored raw: `rate_per_sqft = consideration / (carpet_area_sqm * 10.7639)` computed in `ProjectSnapshot.unit_transactions` [reader.py:ProjectSnapshot.unit_transactions]
- `ingest_from_run` uses `INSERT OR REPLACE` for `projects`, `promoters`, `inventory_blocks`, `documents_catalog`, and `document_jobs` (re-ingest overwrites), but deletes-then-inserts `banks` per project and `unit_transactions` per `(project_id, run_id)` [loader.py:ingest_from_run]
- Asset-class classification for `unit_transactions` maps unit-type keywords to `Commercial_Office`, `Commercial_Retail`, `Industrial_Warehouse`, else `Residential` [loader.py:ingest_from_run]
- `documents_catalog.uid_hash` is the primary key; `document_jobs` is unique on `(run_id, uid_hash)` and its `status` is one of `'PENDING'`, `'PROCESSING'`, `'COMPLETED'`, `'FAILED'` [database.py:init_schema]
- FTS queries are sanitized by quoting terms; `search_documents` falls back to a stripped query on `sqlite3.OperationalError` and returns `[]` if that also fails [fts.py:sanitize_fts_query], [fts.py:search_documents]
- `fts.index_page_text` silently skips empty/whitespace-only content [fts.py:index_page_text]

## Side Effects
- Creates and writes the SQLite database at the path passed to `get_connection`/`ingest_from_run` (default `real_estate_intelligence/data/intelligence.sqlite` via [../config.py:DEFAULT_DB_PATH]), including WAL/SHM journal files and parent-directory creation [database.py:get_connection]
- `ingest_from_run` commits and closes the target connection before returning [loader.py:ingest_from_run]
- During ingestion, PDFs are read from disk and page text is inserted into `document_fts`; every cataloged document enqueues a `document_jobs` row marked `COMPLETED` (if indexed inline) or `PENDING` [loader.py:ingest_from_run]
- `DiskRunReader` decompresses `.json.gz` raw files from the run directory on first access per endpoint [reader.py:DiskRunReader._read_compressed_json]
- `FakeRunReader.close()` performs no I/O by design [reader.py:FakeRunReader]

## Verification
- Run: `python -m pytest real_estate_intelligence/tests`
