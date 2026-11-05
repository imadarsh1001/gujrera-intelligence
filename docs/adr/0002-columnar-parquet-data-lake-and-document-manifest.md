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
   - Master historical crawl runs are parsed and partitioned into 16 sub-22MB Parquet parts:
     - `data/filings/2023-12-01/part_01.parquet` .. `part_04.parquet` (12,912 filings, 49.3 MB)
     - `data/filings/2024-10-13/part_01.parquet` .. `part_04.parquet` (14,435 filings, 72.6 MB)
     - `data/filings/2025-03-01/part_01.parquet` .. `part_04.parquet` (15,057 filings, 76.2 MB)
     - `data/filings/2026-10-11/part_01.parquet` .. `part_04.parquet` (16,337 filings, 54.0 MB)
   - Total rows across history: **58,741 filings** representing **17,632 unique projects** (99.99% statewide coverage).
   - Each dataset embeds top-level indexed fields (`project_id`, `snapshot_date`, `quarter`, `form_three_id`, `form_three_status`, `total_units`, `total_cost_incurred`) alongside the full ZSTD-compressed `raw_json` payload, providing zero-loss fidelity while reducing disk footprint from **4.1 GB to 252 MB** (a 16.3x reduction).
   - All 16 parts are versioned directly in the private `gujrera-pipeline` Git repository.

3. **Project-Granular Document Architecture (`gujrera_pipeline/data/samples/`)**:
   - Replaced loose uncompressed document directories and monolithic archives with sub-24MB per-project bundles:
     - `meta.zip`: Structured JSON and markdown dossiers (~1–15 MB per project, versioned in Git).
     - `docs_part_XX.zip`: PDF bundles strictly $< 24\text{ MB}$ each (97 bundles total across 9 projects).
   - Generated a lightweight metadata index: [`documents_manifest.parquet`](file:///d:/Code%20Projects/Miscellaneous/Real%20Estate%20Data/gujRERA/gujrera_pipeline/data/indexes/documents_manifest.parquet) (**63.58 KB** for 1,204 documents).
   - Analysts query `documents_manifest.parquet` via DuckDB in $< 2\text{ ms}$ and resolve the exact sub-24MB bundle containing any document without downloading full project histories.

4. **Sovereign Environment & Tooling**:
   - Standardized on `pyarrow` (v26.0.1) and `duckdb` (v2.0.0) in `.venv` for zero-copy SQL queries and columnar analytics.

## Consequences & Verification

- **Storage Reclaimed**: Systematically freed **~10.79 GB** of local disk space by removing redundant crawler intermediate dumps (3.27 GB), raw uncompressed JSONs (4.10 GB), duplicate CSVs (0.43 GB), loose uncompressed PDFs (1.57 GB), and monolithic archives (1.39 GB).
- **Zero Data Loss**: Mathematically verified via CRC32 and SHA-256 that master completed runs contain 100% of projects from all partial intermediate runs and 100% byte-for-byte fidelity of all 1,204 project documents (0 missing files or records).
- **Dual-Repo Boundary Maintained**: The public platform (`gujrera-intelligence`) remains completely pristine with zero raw data or filings. The private pipeline (`gujrera-pipeline`) holds the versioned lightweight indexes, 16 Form 3 Parquet filing partitions, and project structured metadata in Git.
