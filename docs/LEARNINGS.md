# Engineering Learnings & Architectural Notes: GujRERA Pipeline

**Date**: November 2026  
**Topic**: High-Performance Columnar Data Lake, Git Protocol Optimization, Document Partitioning, and Zero-Loss Space Reclamation  

---

## 1. Git HTTP/HTTPS Protocol & Large File Ingestion Learnings

### 1.1 The Pitfall of `http.postBuffer`
- **Issue Encountered**: When attempting to push 250 MB of binary Parquet files to GitHub over HTTPS, Git stalled indefinitely after reporting `Writing objects: 100% ... done. Total 25 ...`.
- **Root Cause**: Setting `git config http.postBuffer 524288000` (500 MB) instructed Git to buffer the entire commit payload in memory and send it as a single non-chunked HTTP POST with a fixed `Content-Length`. Intermediate reverse proxies (e.g., Azure Front Door, Cloudflare, Fastly) and GitHub's ingress servers frequently drop or timeout non-chunked large HTTP POSTs or enforce strict proxy body buffer limits.
- **The Fix**:
  1. Unset `http.postBuffer`: `git config --unset http.postbuffer`.
  2. Enforce HTTP/1.1 chunked streaming: `git config http.version HTTP/1.1`.
  3. Git immediately streams using `POST git-receive-pack (chunked)`, allowing steady, uninterrupted packfile transmission.

### 1.2 The Sub-25MB Partitioning Rule
- GitHub enforces a strict 100 MB per-file push limit and warns on files $> 50\text{ MB}$.
- Pushing monolithic multi-hundred-megabyte commits in a single transaction risks transport failure over residential connections.
- **Rule Adopted**: Partition all data lake artifacts into **sub-25MB chunks**:
  - Quarterly Form 3 Parquet filings: 4 parts per quarter (~10–20 MB each).
  - Project document bundles: PDF chunks strictly $< 22\text{ MB}$ each.
  - Push commits quarter-by-quarter or bundle-by-bundle: each transaction completes in 1–3 minutes reliably.

---

## 2. Columnar Parquet Data Lake (PyArrow & DuckDB)

### 2.1 Schema Design: Hybrid Typed Columns + Embedded Compressed JSON
- **Problem**: Statutory GujRERA filings contain deeply nested, highly variable JSON structures with duplicate keys (e.g. duplicate `kycid` keys across nested promoters), causing standard database auto-detection to fail.
- **Solution**:
  - Extract the highest-cardinality indexing fields into typed, indexed Parquet columns:
    - `project_id` (string)
    - `form_three_id` (string)
    - `form_three_status` (string)
    - `snapshot_date` (string)
    - `quarter` (string)
    - `total_units` (int64)
    - `total_cost_incurred` (double)
  - Store the complete, unaltered JSON payload in a compressed `raw_json` column.
- **Benefits**:
  - **Zero Data Loss**: 100% of raw fields, nested dictionaries, and audit trails are preserved.
  - **16.3x Storage Reduction**: 4.1 GB of raw JSON compressed down to 252 MB in Parquet.
  - **Zero-Copy SQL**: DuckDB extracts any nested JSON attribute on the fly in $< 5\text{ ms}$ using `json_extract_string(raw_json, '$.promoterName')`.

### 2.2 Statewide Registry Coverage & Historical Snapshot Model
- Across four historical scrape snapshots (2023-12-01, 2024-10-13, 2025-03-01, 2026-10-11):
  - Total statutory Form 3 filings: **58,741**.
  - Total unique projects covered: **17,632** out of 17,634 statewide registered projects (**99.99% coverage**).
  - Snapshot date and quarter tags must always be embedded in both filenames and row-level metadata to distinguish repeat crawls within the same quarter.

---

## 3. Project-Granular Document Architecture

### 3.1 Two-Tier Project Bundling
Instead of storing monolithic multi-hundred-megabyte archives that require downloading gigabytes to inspect one project:
1. **Tier 1: Structured Metadata (`meta.zip`)**:
   - Contains all structured JSON files (`all_data.json`, `documents.json`, `banks.json`, `block_progress.json`, `DOSSIER.md`).
   - Size: 1–15 MB per project (55 MB total across all 9 sample projects).
   - Tracked directly in Git in `gujrera-pipeline` for immediate access.
2. **Tier 2: PDF Document Bundles (`docs_part_XX.zip`)**:
   - PDF files grouped into volume parts strictly $< 22\text{ MB}$ each (97 bundles across 9 projects).
   - Largest bundle across the entire repository is only 23.58 MB.

### 3.2 O(1) Evidentiary Manifest (`documents_manifest.parquet`)
- **Size**: 63.58 KB for 1,204 files.
- Maps every document to its `project_id`, portal `uid_hash`, file size, cryptographic `sha256`, and exact `archive_bundle` path.
- A user or automated agent can query DuckDB for a specific document and download only the target 18–22 MB volume rather than a 1.4 GB monolith.

---

## 4. Verification & Space Reclamation Audit

### 4.1 Verification Protocol (Karpathy Guidelines)
Before any legacy files were deleted:
1. **Project ID Coverage**: Verified that the master Form 3 snapshots contained 100% of projects present in intermediate partial dumps (0 missing projects).
2. **Byte-for-Byte CRC32 & SHA-256 Validation**: Verified that all 1,204 files in the partitioned bundles matched the original monolithic archives with 0 discrepancies.
3. **Automated Test Suites**: Confirmed 4/4 pipeline tests, 32/32 platform tests, and 100% eval benchmark pass rates.

### 4.2 Local Disk Space vs Remote Repository Status

| Asset Description | Remote Status | Local Disk Status | Size |
|---|---|---|---|
| **16 Form 3 Parquet Partitions** (`data/filings/*/*.parquet`) | Pushed to Git (`gujrera-pipeline`) | **Kept locally** (tracked in Git working tree) | 250 MB |
| **9 Project Metadata Bundles** (`data/samples/*/meta.zip`) | Pushed to Git (`gujrera-pipeline`) | **Kept locally** (tracked in Git working tree) | 55 MB |
| **Date-Stamped Parquet Indexes** (`data/indexes/*.parquet`) | Pushed to Git (`gujrera-pipeline`) | **Kept locally** (tracked in Git working tree) | 17.8 MB |
| **88 Partitioned PDF Bundles** (`data/samples/*/docs_part_*.zip`) | Local data lake (ignored by Git) | **Kept locally** (indexed by manifest) | 1.34 GB |
| **Untouched Reference CSVs** (`raw_data/*.csv`) | Kept as raw benchmark | **Kept locally** (reference layer) | 47.5 MB |
| **Raw Uncompressed Form 3 JSONs** (`legacy/scrapy_crawler/`) | Replaced by Parquet | **DELETED from local disk** | Reclaimed 4.10 GB |
| **Intermediate 2026 Checkpoints** (`collected_data/*.json`) | Replaced by master Parquet | **DELETED from local disk** | Reclaimed 3.27 GB |
| **Loose Uncompressed PDFs** (`legacy/research_samples/`) | Packaged & replaced | **DELETED from local disk** | Reclaimed 1.57 GB |
| **Monolithic Project Archives** (`legacy/research_samples/archives/`) | Replaced by sub-22MB bundles | **DELETED from local disk** | Reclaimed 1.39 GB |
| **Duplicate 426MB CSV** (`legacy/eda_prototypes/EDA/`) | Identical to Parquet | **DELETED from local disk** | Reclaimed 0.43 GB |
| **Scrapy Crawler Partial Artifacts** | Redundant logs & partials | **DELETED from local disk** | Reclaimed 0.03 GB |
| **Total Disk Space Reclaimed** | — | — | **~10.79 GB** |

---

## 5. Architectural Consolidation & Forensic Bug Post-Mortems

### 5.1 Date-Truncation Bug (`[:10]`), Blast Radius & Clean Reproducibility Rebuild
- **Root Cause**: The statewide registry Parquet snapshot (`all_projects_2026-11-13.parquet`) encodes dates in `DD-Month-YYYY` format (e.g. `'20-October-2016'`, `'31-December-2019'`). In `db/statewide_loader.py` (lines ~195-196 and ~451), the ingestion code naively sliced dates using `str(row[7])[:10]` and `str(row[8])[:10]`.
- **Blast-Radius Audit**:
  - Taking `[:10]` of 15-character date strings truncated them to partial strings like `'20-October'`, `'31-Decembe'`, `'30-June-20'`, and `'10-October'`.
  - Database audit revealed:
    - `projects.start_date`: **17,778 corrupted rows** out of 17,787 total.
    - `projects.completion_date`: **17,778 corrupted rows** out of 17,787 total.
    - `project_summaries.completion_date`: **17,787 corrupted rows** out of 17,787 total.
    - Only the **9 deep reference projects** (seeded via `nine_projects` / smoke test) had valid ISO dates in the live DB.
- **The Fix**:
  - Implemented `parse_iso_date()` in `db/statewide_loader.py` using regex and month token maps to handle `DD-Month-YYYY`, `DD-MM-YYYY`, `DD/MM/YYYY`, and ISO formats.
  - Replaced all raw `[:10]` date slices in `startDate`, `endDate`, `approvedOn`, `buDate`, and Form 3 `dateOfAgrrement`.
  - Added unit test `test_statewide_loader_date_parsing_multi_format` verifying `"19-August-2021"`, `"01-04-2025"`, and `"2024-08-19"`.
- **Measured Rebuild Time & Reproducibility Verification**:
  - Built clean throwaway database `data/intelligence_rebuild_test.sqlite` in **250.87 seconds (4.18 minutes)**.
  - Per-table row counts matched 100% against live DB:
    - `projects`: 17,787 vs 17,787 (MATCH)
    - `project_summaries`: 17,787 vs 17,787 (MATCH)
    - `unit_transactions`: 826,162 vs 826,162 (MATCH)
    - `banks`: 3,935 vs 3,935 (MATCH)
    - `professionals`: 3,306 vs 3,306 (MATCH)
    - `noc_bu_records`: 13,396 vs 13,396 (MATCH)
  - Corrupted date rows dropped from **17,778 to 0** across all 17,787 projects.
  - Following verified exact match, backed up live DB to `data/intelligence_backup_20261120.sqlite`, swapped in the rebuilt DB, regenerated knowledge graph (`build_graph.py`: 19,084 nodes, 25,025 edges), and verified 60/60 passing pytest tests.

### 5.2 Hallucinated Contagion Query Caught by Repo-Wide Grep
- **Incident**: An automated AI codebase audit report asserted that a critical SQL bug existed in the contagion/network subsystem:
  `SELECT project_id, name, district, status FROM projects WHERE promoter_id = ?`
  claiming that `promoter_id` was an invalid column causing runtime database exceptions.
- **Investigation**: We executed an exhaustive repository-wide search across all `.py`, `.sql`, and `.md` files for `promoter_id` and the claimed query string.
- **Finding**: The query did not exist anywhere in the codebase. The `projects` table stores `promoter_name` and uses entity linking tables for promoter relationships; the claimed bug was a complete hallucination produced by an LLM reviewing a generic relational schema rather than the actual source code.
- **Rule Adopted**: Never accept an AI-reported debt or bug claim without verifying against source code with verifiable grep/AST evidence before changing production code.

### 5.3 The `(status, rate_per_sqft)` Index Trap vs `(project_id, status)`
- **Problem**: Query profiling indicated slow execution in `PricingIntelligence` and `/api/explore` queries querying `unit_transactions` (1.8M rows). Two candidate composite indexes were proposed:
  1. `CREATE INDEX idx_unit_tx_status_rate ON unit_transactions(status, rate_per_sqft);`
  2. `CREATE INDEX idx_unit_tx_pid_status ON unit_transactions(project_id, status);`
- **Evaluation via `EXPLAIN QUERY PLAN`**:
  - The hot analytical query is: `SELECT rate_per_sqft FROM unit_transactions WHERE project_id = ? AND status = 'BOOKED'`.
  - Analyzing candidate 1 `(status, rate_per_sqft)`: Because `status = 'BOOKED'` matches over 80% of rows statewide, the leading column has virtually zero selectivity. SQLite would scan hundreds of thousands of index entries and perform random B-tree lookups back to the table to filter by `project_id`.
  - Analyzing candidate 2 `(project_id, status)`: `project_id` has high selectivity (filtering down to only the units for that specific project, typically 10–500 rows). SQLite seeks directly to the project's units and immediately filters by `status` without table scans.
- **Verification & Outcome**: `EXPLAIN QUERY PLAN` proved `idx_unit_tx_pid_status` performed a direct `SEARCH TABLE unit_transactions USING INDEX`, cutting query latency from hundreds of milliseconds to under 2 ms. Candidate 1 was rejected as an index trap, and candidate 2 was created.

### 5.4 `httpx` Abandonment, Identity Gate & Manual Provenance Verification
- **Context**: Starlette and FastAPI test suites deprecated `httpx` in favor of `httpx2`, triggering persistent `StarletteDeprecationWarning` deprecation alerts during test runs.
- **Security & Identity Gate Protocol**:
  - Before running `pip install httpx2`, we verified package identity on PyPI to prevent supply-chain typo-squatting.
  - PyPI metadata revealed the author as Tom Christie and the maintainer organization as `pydantic` (`pydantic/httpx2`), rather than the historic `encode` organization.
  - Following the security protocol, installation was halted at the verification gate to confirm identity and provenance before making changes to `.venv` or package manifests.
  - Upon explicit verification and approval, `httpx2==2.16.2` (and `httpcore2==2.16.2`) was installed into the virtual environment, `httpx` was cleanly uninstalled, and dev requirements were updated.
- **Result**: All 59 tests in the test suite pass with zero deprecation warnings.
