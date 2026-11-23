"""Generate read-only snapshot for /api/insights/markup_spread.

Pre-aggregates the statewide unbooked vs. booked price markup from the curated
SQLite fact base (DEFAULT_DB_PATH) and writes a sanitized JSON snapshot to
real_estate_intelligence/data/markup_spread_snapshot.json.
Enables sub-50ms cold-start responses on serverless and runtime startup.
"""

import json
import math
import sys
import time
from pathlib import Path

# Ensure package root is discoverable
pkg_root = Path(__file__).resolve().parent.parent
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))

from real_estate_intelligence.config import DEFAULT_DB_PATH
from real_estate_intelligence.db.database import get_connection
from real_estate_intelligence.db.queries import get_markup_spread_data


def sanitize_floats(obj):
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: sanitize_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_floats(v) for v in obj]
    return obj


def generate_snapshot(db_path: Path = DEFAULT_DB_PATH, output_file: Path = None) -> Path:
    if output_file is None:
        output_file = pkg_root / "data" / "markup_spread_snapshot.json"

    print(f"Connecting to database: {db_path} (read_only=True)")
    t0 = time.time()
    con = get_connection(db_path, read_only=True)
    try:
        data = get_markup_spread_data(con)
    finally:
        con.close()

    sanitized = sanitize_floats(data)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(sanitized, f, indent=2)

    elapsed = time.time() - t0
    print(f"Wrote snapshot to {output_file} in {elapsed:.2f}s ({output_file.stat().st_size} bytes)")
    return output_file


if __name__ == "__main__":
    out = generate_snapshot()
