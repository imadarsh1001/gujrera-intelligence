# documents — PDF Extraction, Classification & Async Indexing

## Overview
Document processing layer for sworn GujRERA PDF filings. `parser.py` extracts and sanitizes page-level text (pypdf when available, stdlib zlib fallback otherwise) and classifies each document's semantic role; `worker.py` drains the SQLite `document_jobs` queue so heavy binary extraction never blocks tabular ingestion or the web UI; `search.py` re-exports the FTS search interface from the `db` layer as the package's public search surface.

## Interface
- `sanitize_pdf_page_text(text) -> str` — strips binary/CAD artifacts, enforces a 25,000-character page cap, and drops non-linguistic pages [parser.py:sanitize_pdf_page_text]
- `extract_pages_pypdf(file_bytes) -> List[Tuple[int, str]]` — page-indexed extraction via `pypdf.PdfReader` [parser.py:extract_pages_pypdf]
- `extract_pages_stdlib(file_bytes) -> List[Tuple[int, str]]` — fallback extraction from zlib-decompressed PDF streams; synthesizes a single page `1` [parser.py:extract_pages_stdlib]
- `extract_pdf_pages(file_path) -> List[Tuple[int, str]]` — main entry point; validates the `%PDF-` magic bytes and prefers pypdf when `HAS_PYPDF` is true [parser.py:extract_pdf_pages]
- `classify_document_type(json_path, request_key, file_name) -> str` — maps request keys to semantic doc types: `form_one_architect`, `form_two_engineer`, `form_three_ca`, `form_five_annual_audit`, `form_four_completion`, `bu_permission_noc`, `title_search_report`, `title_clearance_certificate`, `approved_building_plan`, `approved_layout_plan`, `encumbrance_certificate`, `sale_agreement_proforma`, `loan_sanction_or_charge`, `bank_escrow_passbook`, `other_regulatory_doc` [parser.py:classify_document_type]
- `HAS_PYPDF` — module flag, `True` only when `pypdf` imports successfully [parser.py:HAS_PYPDF]
- `DocumentWorker(con_or_path=None, base_runs_dir=None, prune_binaries=False)` — queue consumer with `process_next_job()`, `process_batch(max_jobs=10)`, `get_queue_status()`, and `close()` [worker.py:DocumentWorker]
- Re-exports from `db.fts`: `DocumentSearchEngine`, `sanitize_fts_query`, `search_documents` [search.py:__all__]

## Invariants
- pypdf is an optional dependency: extraction silently degrades to `extract_pages_stdlib` when `HAS_PYPDF` is false or pypdf raises [parser.py:extract_pdf_pages]
- A page shorter than 15 characters is discarded, and a page longer than 200 characters with fewer than 2 `COMMON_LEGAL_MARKERS` vocabulary hits is treated as a CAD raster dump and discarded [parser.py:sanitize_pdf_page_text]
- `extract_pdf_pages` returns `[]` for missing, empty, or non-PDF files (no `%PDF-` header) [parser.py:extract_pdf_pages]
- `DocumentWorker` job status is a strict state machine over `document_jobs.status`: `PENDING -> PROCESSING -> COMPLETED`, with `FAILED` assigned only when `attempts >= max_attempts`; otherwise the job reverts to `PENDING` [worker.py:process_next_job]
- Jobs are claimed oldest-first: `WHERE status = 'PENDING' AND attempts < max_attempts ORDER BY id ASC LIMIT 1` [worker.py:process_next_job]
- File resolution accepts absolute paths or paths relative to `base_runs_dir` (default `Path.cwd()` when not provided) [worker.py:DocumentWorker]
- The worker closes the connection on `close()` only when it opened it itself (`_owns_con`); a passed-in `sqlite3.Connection` is never closed [worker.py:close]

## Side Effects
- Reads PDF binaries from disk during `process_next_job` [worker.py:process_next_job]
- Writes FTS rows into `document_fts` via `db.fts.index_page_text` and mutates `document_jobs` status/attempts/error columns, committing after each state change [worker.py:process_next_job]
- With `prune_binaries=True`, deletes the source PDF from disk after successful extraction (`target_path.unlink()`); `OSError` is swallowed [worker.py:process_next_job]
- `DocumentWorker.__init__` runs `init_schema` and, when constructed without a connection, opens (and later owns) a connection to [../config.py:DEFAULT_DB_PATH] [worker.py:DocumentWorker]

## Verification
- Run: `python -m pytest real_estate_intelligence/tests`
