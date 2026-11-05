# 0002. Columnar Parquet Data Lake & Project-Granular Document Architecture

## Context & Problem Statement

The GujRERA project accumulated over 10.5 GB of heterogeneous historical data spanning four years of scraping runs (December 2023, October 2024, March 2025, and October 2026):
1. **Uncompressed Text Bloat**: Raw statutory Form 3 JSON/JSONL dumps and CSV indexes occupied over 5 GB of uncompressed text. The crawler generated multiple partial checkpoint dumps (e.g., three separate dumps on 2026-10-11 totaling 3.3 GB) with high overlap.
2. **Duplicate Encodings**: `legacy/eda_prototypes/EDA/` contained a 426 MB uncompressed CSV alongside an identical 32 MB Parquet file of 1.8M unit-level transactions.
3. **Monolithic Document Bundles**: 789 statutory PDF filings (1.57 GB) across 9 benchmark research projects were stored as uncompressed loose files. If an analyst or automated pipeline needed to inspect a single project, downloading or reading a monolithic multi-gigabyte bundle was required.
4. **Git Repository Bloat**: Git cannot efficiently version multi-gigabyte volatile binary or JSON files, and GitHub enforces a hard 100 MB per-file push limit.

## Decision

We adopt a modern, sovereign **Columnar Data Lake** architecture powered by **PyArrow** and **DuckDB**, coupled with an **Evidentiary Document Manifest**:

1. **Date-Stamped Columnar Project Indexes (`gujrera_pipeline/data/indexes/`)**:
   - All statewide project registry snapshots (`all_projects_YYYY-MM-DD.parquet`) and form ID mappings are converted from CSV to ZSTD-compressed Parquet.
   - Each row explicitly embeds `snapshot_date` (e.g. `'2026-10-11'`) and `quarter` (e.g. `'2026-Q4'`).
   - The entire statewide historical index spanning 2023–2026 (17,634 projects) consumes only **17.8 MB** total across 11 files (down from ~60 MB uncompressed), well below GitHub's 100 MB limit, and is tracked directly in the private `gujrera-pipeline` Git repository.

2. **Master Quarterly Form 3 Filings (`gujrera_pipeline/data/filings/`)**:
   - Master historical crawl runs are parsed into date-stamped Parquet datasets:
     - `formthree_2023-12-01_q4.parquet` (12,912 filings, 56.6 MB)
     - `formthree_2024-10-13_q4.parquet` (14,435 filings, 69.3 MB)
     - `formthree_2025-03-01_q1.parquet` (15,057 filings, 72.7 MB)
     - `formthree_2026-10-11_q4.parquet` (16,337 filings, 51.5 MB)
   - Total rows across history: **58,741 filings** representing **17,632 unique projects** (99.99% statewide coverage).
   - Each dataset embeds top-level indexed fields (`project_id`, `snapshot_date`, `quarter`, `form_three_id`, `form_three_status`) alongside the full ZSTD-compressed `raw_json` payload, providing zero-loss fidelity while reducing disk footprint from **4.1 GB to 250 MB** (a 16.4x reduction).

3. **Project-Granular Document Architecture (`legacy/research_samples/archives/`)**:
   - Replaced loose uncompressed document directories with isolated, CRC32-verified per-project zip archives: `project_{project_id}_docs.zip` (100–270 MB each).
   - Generated a lightweight metadata index: [`documents_manifest.parquet`](file:///d:/Code%20Projects/Miscellaneous/Real%20Estate%20Data/gujRERA/gujrera_pipeline/data/indexes/documents_manifest.parquet) (**46.8 KB** for 789 documents).
   - Analysts query `documents_manifest.parquet` via DuckDB in $< 2\text{ ms}$ and retrieve only the target project's bundle without ever downloading a 1.5 GB monolith.

4. **Sovereign Environment & Tooling**:
   - Standardized on `pyarrow` (v26.0.1) and `duckdb` (v2.0.0) in `.venv` for zero-copy SQL queries and columnar analytics.

## Consequences & Verification

- **Storage Reclaimed**: Immediately freed **~5.28 GB** of local disk space by removing redundant crawler intermediate dumps, duplicate CSVs, and loose uncompressed PDFs.
- **Zero Data Loss**: Mathematically verified that master completed runs contain 100% of projects from all partial intermediate runs (0 missing projects).
- **Dual-Repo Boundary Maintained**: The public platform (`gujrera-intelligence`) remains completely pristine with zero raw data or filings. The private pipeline (`gujrera-pipeline`) holds the versioned lightweight indexes in Git and manages heavy Parquet filings and document archives locally or via cloud release assets.
