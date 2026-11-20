"""Sync local SQLite intelligence database to remote Turso (libSQL) database."""

import os
import sys
import time
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

import libsql

from .database import init_schema
from ..config import DEFAULT_DB_PATH


TARGET_TABLES = [
    "projects",
    "project_summaries",
    "promoters",
    "professionals",
    "banks",
    "inventory_blocks",
    "quarterly_timeline",
    "finances",
    "form5_compliance",
    "noc_bu_records",
    "previous_projects",
    "applications",
    "documents_catalog",
    "document_jobs",
]


def sync_to_turso(
    local_db_path: Path = DEFAULT_DB_PATH,
    database_url: Optional[str] = None,
    auth_token: Optional[str] = None,
    tables: Optional[List[str]] = None,
    batch_size: int = 200,
) -> Dict[str, int]:
    """Sync target tables from local SQLite to remote Turso database."""
    url = database_url or os.environ.get("TURSO_DATABASE_URL")
    token = auth_token or os.environ.get("TURSO_AUTH_TOKEN")

    if not url:
        raise ValueError("TURSO_DATABASE_URL must be provided or set in environment.")
    if not token:
        raise ValueError("TURSO_AUTH_TOKEN must be provided or set in environment.")

    local_path = Path(local_db_path)
    if not local_path.exists():
        raise FileNotFoundError(f"Local database not found at {local_path}")

    print(f"[TURSO SYNC] Connecting to remote Turso: {url}")
    remote_con = libsql.connect(database=url, auth_token=token)

    print("[TURSO SYNC] Initializing remote DDL schema & indexes...")
    init_schema(remote_con)
    if hasattr(remote_con, "commit"):
        remote_con.commit()

    local_con = sqlite3.connect(str(local_path))
    local_con.row_factory = sqlite3.Row
    local_cur = local_con.cursor()

    tables_to_sync = tables or TARGET_TABLES
    sync_stats = {}

    total_start = time.time()

    for table in tables_to_sync:
        # Check if table exists locally
        exists = local_cur.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()[0]
        if not exists:
            print(f"[TURSO SYNC] Skipping {table}: not present in local database.")
            continue

        # Get column names
        col_cur = local_cur.execute(f'SELECT * FROM "{table}" LIMIT 1')
        if not col_cur.description:
            print(f"[TURSO SYNC] Skipping {table}: no columns found.")
            continue
        col_names = [d[0] for d in col_cur.description]
        quoted_cols = ", ".join(f'"{c}"' for c in col_names)

        total_rows = local_cur.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
        if total_rows == 0:
            print(f"[TURSO SYNC] Table '{table}': 0 rows to sync.")
            sync_stats[table] = 0
            continue

        # Calculate optimal batch size given column count (max 30,000 params)
        max_batch_for_cols = max(1, min(batch_size, 30000 // len(col_names)))

        print(f"[TURSO SYNC] Syncing '{table}' ({total_rows:,} rows, {len(col_names)} cols, batch={max_batch_for_cols})...")
        t_table_start = time.time()

        rows_cur = local_con.cursor()
        rows_cur.execute(f'SELECT {quoted_cols} FROM "{table}"')

        inserted = 0
        batch = []

        placeholders_one = "(" + ", ".join(["?"] * len(col_names)) + ")"

        while True:
            rows = rows_cur.fetchmany(max_batch_for_cols)
            if not rows:
                break

            val_placeholders = ", ".join([placeholders_one] * len(rows))
            sql = f'INSERT OR REPLACE INTO "{table}" ({quoted_cols}) VALUES {val_placeholders}'
            flat_vals = [val for row in rows for val in row]

            # Execute with retries for network resilience
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                try:
                    remote_con.execute(sql, flat_vals)
                    break
                except Exception as e:
                    if attempt == max_retries:
                        raise RuntimeError(f"Failed to insert batch into {table} after {max_retries} attempts: {e}")
                    time.sleep(0.5 * attempt)

            inserted += len(rows)
            if inserted % 2000 == 0 or inserted == total_rows:
                if hasattr(remote_con, "commit"):
                    remote_con.commit()
                pct = (inserted / total_rows) * 100
                elapsed = time.time() - t_table_start
                rate = inserted / elapsed if elapsed > 0 else 0
                print(f"  -> '{table}': {inserted:,}/{total_rows:,} ({pct:.1f}%) [{rate:.0f} rows/s]")

        if hasattr(remote_con, "commit"):
            remote_con.commit()

        # Verify remote count
        remote_cnt = remote_con.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
        sync_stats[table] = remote_cnt
        print(f"[TURSO SYNC] [OK] '{table}' verified on Turso: {remote_cnt:,} rows in {time.time() - t_table_start:.2f}s")

    local_con.close()
    if hasattr(remote_con, "close"):
        remote_con.close()

    total_time = time.time() - total_start
    total_synced_rows = sum(sync_stats.values())
    print(f"\n[TURSO SYNC COMPLETE] Synced {total_synced_rows:,} rows across {len(sync_stats)} tables in {total_time:.2f}s")
    return sync_stats
