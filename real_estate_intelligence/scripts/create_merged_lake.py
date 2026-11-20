"""Create merged recovery source for statewide ingestion.

Backfills null raw_json payloads in the 2026-11-13 crawl using complete 2026-10-11 payloads.
Original lake is strictly read-only.
Merged datasets live only in this repository under data/merged_2026-11-13/.
"""

import os
import shutil
import time
from pathlib import Path
import duckdb

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
PIPELINE_DATA = WORKSPACE_ROOT.parent / "gujrera_pipeline" / "data"
MERGED_DIR = WORKSPACE_ROOT / "data" / "merged_2026-11-13"


def create_merged_lake():
    start_time = time.time()
    print("=== Creating Merged Recovery Lake ===")
    print(f"Source Pipeline Lake: {PIPELINE_DATA}")
    print(f"Destination Merged Dir: {MERGED_DIR}")

    if not PIPELINE_DATA.exists():
        raise FileNotFoundError(f"Producer data lake not found at {PIPELINE_DATA}")

    con = duckdb.connect()

    # Create target directories
    for sub in ["form3", "form2", "governance"]:
        (MERGED_DIR / sub / "2026-11-13").mkdir(parents=True, exist_ok=True)

    # 1. Backfill Form 3
    print("\n[1/3] Merging Form 3 parquet files...")
    nov_f3_dir = PIPELINE_DATA / "form3" / "2026-11-13"
    oct_f3_dir = PIPELINE_DATA / "form3" / "2026-10-11"
    for nov_file in sorted(nov_f3_dir.glob("*.parquet")):
        out_file = MERGED_DIR / "form3" / "2026-11-13" / nov_file.name
        oct_file = oct_f3_dir / nov_file.name
        nov_p = nov_file.as_posix()
        oct_p = oct_file.as_posix()

        query = f"""
            COPY (
                WITH nov AS (
                    SELECT * FROM read_parquet('{nov_p}')
                ),
                oct AS (
                    SELECT project_id, endpoint, raw_json AS oct_raw_json
                    FROM read_parquet('{oct_p}')
                    WHERE raw_json IS NOT NULL
                )
                SELECT 
                    nov.project_id,
                    nov.district,
                    nov.endpoint,
                    nov.url,
                    nov.http_status,
                    nov.api_status,
                    nov.fetched_at_utc,
                    nov.sha256,
                    COALESCE(nov.raw_json, oct.oct_raw_json) AS raw_json,
                    CASE 
                        WHEN nov.raw_json IS NOT NULL THEN '2026-11-13'
                        WHEN oct.oct_raw_json IS NOT NULL THEN '2026-10-11-backfill'
                        ELSE '2026-11-13'
                    END AS source_run
                FROM nov
                LEFT JOIN oct ON nov.project_id = oct.project_id AND nov.endpoint = oct.endpoint
                ORDER BY nov.project_id ASC
            ) TO '{out_file.as_posix()}' (FORMAT PARQUET)
        """
        con.execute(query)
        print(f"  Merged {nov_file.name} -> {out_file.name}")

    # 2. Backfill Governance
    print("\n[2/3] Merging Governance parquet files...")
    nov_gov_dir = PIPELINE_DATA / "governance" / "2026-11-13"
    oct_gov_dir = PIPELINE_DATA / "governance" / "2026-10-11"
    for nov_file in sorted(nov_gov_dir.glob("*.parquet")):
        out_file = MERGED_DIR / "governance" / "2026-11-13" / nov_file.name
        oct_file = oct_gov_dir / nov_file.name
        nov_p = nov_file.as_posix()
        oct_p = oct_file.as_posix()

        query = f"""
            COPY (
                WITH nov AS (
                    SELECT * FROM read_parquet('{nov_p}')
                ),
                oct AS (
                    SELECT project_id, endpoint, raw_json AS oct_raw_json
                    FROM read_parquet('{oct_p}')
                    WHERE raw_json IS NOT NULL
                )
                SELECT 
                    nov.project_id,
                    nov.district,
                    nov.endpoint,
                    nov.url,
                    nov.http_status,
                    nov.api_status,
                    nov.fetched_at_utc,
                    nov.sha256,
                    COALESCE(nov.raw_json, oct.oct_raw_json) AS raw_json,
                    CASE 
                        WHEN nov.raw_json IS NOT NULL THEN '2026-11-13'
                        WHEN oct.oct_raw_json IS NOT NULL THEN '2026-10-11-backfill'
                        ELSE '2026-11-13'
                    END AS source_run
                FROM nov
                LEFT JOIN oct ON nov.project_id = oct.project_id AND nov.endpoint = oct.endpoint
                ORDER BY nov.project_id, nov.endpoint ASC
            ) TO '{out_file.as_posix()}' (FORMAT PARQUET)
        """
        con.execute(query)
        print(f"  Merged {nov_file.name} -> {out_file.name}")

    # 3. Form 2 (Nov copy with source_run column)
    print("\n[3/3] Processing Form 2 files (Nov baseline)...")
    nov_f2_dir = PIPELINE_DATA / "form2" / "2026-11-13"
    for nov_file in sorted(nov_f2_dir.glob("*.parquet")):
        out_file = MERGED_DIR / "form2" / "2026-11-13" / nov_file.name
        nov_p = nov_file.as_posix()

        query = f"""
            COPY (
                SELECT 
                    *,
                    '2026-11-13' AS source_run
                FROM read_parquet('{nov_p}')
                ORDER BY project_id ASC
            ) TO '{out_file.as_posix()}' (FORMAT PARQUET)
        """
        con.execute(query)
        print(f"  Processed {nov_file.name} -> {out_file.name}")

    # 4. Create junctions for indexes, runs, and self-data
    print("\n[4/4] Establishing layout compatibility junctions...")
    import _winapi
    for junc_name, target_path in [
        ("indexes", PIPELINE_DATA / "indexes"),
        ("runs", PIPELINE_DATA / "runs"),
        ("data", MERGED_DIR),
    ]:
        junc_path = MERGED_DIR / junc_name
        if junc_path.exists():
            try:
                os.rmdir(junc_path)
            except OSError:
                pass
        if not junc_path.exists():
            _winapi.CreateJunction(str(target_path.resolve()), str(junc_path.resolve()))
            print(f"  Created junction: {junc_name} -> {target_path}")

    elapsed = round(time.time() - start_time, 2)
    print(f"\nMerged recovery lake created in {elapsed}s at: {MERGED_DIR}")


def report_backfill_coverage():
    con = duckdb.connect()
    print("\n" + "=" * 90)
    print("BACKFILL COVERAGE AND RESIDUAL NULL REPORT")
    print("=" * 90)

    # Form 3
    merged_f3 = (MERGED_DIR / "form3" / "2026-11-13" / "*.parquet").as_posix()
    f3_stats = con.execute(f"""
        SELECT 
            'form3' AS endpoint,
            count(*) AS total_rows,
            count(CASE WHEN source_run = '2026-11-13' AND raw_json IS NOT NULL THEN 1 END) AS nov_native_valid,
            count(CASE WHEN source_run = '2026-10-11-backfill' THEN 1 END) AS oct_backfilled,
            count(raw_json) AS total_valid_after,
            count(*) - count(raw_json) AS residual_null,
            round(100.0 * count(raw_json) / count(*), 2) AS post_coverage_pct
        FROM read_parquet('{merged_f3}')
    """).fetchall()[0]

    # Governance
    merged_gov = (MERGED_DIR / "governance" / "2026-11-13" / "*.parquet").as_posix()
    gov_stats = con.execute(f"""
        SELECT 
            endpoint,
            count(*) AS total_rows,
            count(CASE WHEN source_run = '2026-11-13' AND raw_json IS NOT NULL THEN 1 END) AS nov_native_valid,
            count(CASE WHEN source_run = '2026-10-11-backfill' THEN 1 END) AS oct_backfilled,
            count(raw_json) AS total_valid_after,
            count(*) - count(raw_json) AS residual_null,
            round(100.0 * count(raw_json) / count(*), 2) AS post_coverage_pct
        FROM read_parquet('{merged_gov}')
        GROUP BY endpoint
        ORDER BY endpoint
    """).fetchall()

    # Form 2
    merged_f2 = (MERGED_DIR / "form2" / "2026-11-13" / "*.parquet").as_posix()
    f2_stats = con.execute(f"""
        SELECT 
            'form2' AS endpoint,
            count(*) AS total_rows,
            count(CASE WHEN source_run = '2026-11-13' AND raw_json IS NOT NULL THEN 1 END) AS nov_native_valid,
            count(CASE WHEN source_run = '2026-10-11-backfill' THEN 1 END) AS oct_backfilled,
            count(raw_json) AS total_valid_after,
            count(*) - count(raw_json) AS residual_null,
            round(100.0 * count(raw_json) / count(*), 2) AS post_coverage_pct
        FROM read_parquet('{merged_f2}')
    """).fetchall()[0]

    all_rows = [f3_stats] + gov_stats + [f2_stats]
    print(f"{'Endpoint':<20} | {'Total':<7} | {'Nov Native':<10} | {'Oct Backfill':<12} | {'Total Valid':<11} | {'Null Left':<9} | {'Coverage %':<10}")
    print("-" * 90)
    for r in all_rows:
        print(f"{r[0]:<20} | {r[1]:<7} | {r[2]:<10} | {r[3]:<12} | {r[4]:<11} | {r[5]:<9} | {r[6]:<6}%")
    print("-" * 90)


if __name__ == "__main__":
    create_merged_lake()
    report_backfill_coverage()
