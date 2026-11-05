import os
import gzip
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RUN_DIR = BASE_DIR / "gujrera_pipeline" / "data" / "runs" / "nine_projects_2026_10_15"
RAW_PROJECTS_DIR = RUN_DIR / "raw" / "projects"

def examine(name, filename):
    print(f"\n{'='*30} {name} ({filename}) {'='*30}")
    for pf in RAW_PROJECTS_DIR.iterdir():
        if not pf.is_dir(): continue
        f = pf / filename
        if f.exists():
            try:
                raw = gzip.decompress(f.read_bytes())
                data = json.loads(raw.decode("utf-8-sig"))
                inner = data.get("data", data)
                print(f"\n--- Project {pf.name} ---")
                if isinstance(inner, list):
                    print(f"Count of items: {len(inner)}")
                    if inner:
                        print("Sample item:", json.dumps(inner[0], indent=2)[:500])
                elif isinstance(inner, dict):
                    print("Dict keys:", list(inner.keys()))
                    print("Sample content:", json.dumps(inner, indent=2)[:500])
                else:
                    print(f"Value: {inner}")
            except Exception as e:
                print(f"Error reading {f}: {e}")

def main():
    examine("LOAN DETAILS", "latest_loan_details.json.gz")
    examine("QUARTER INDEX (PENALTIES / DEFAULTS)", "quarter_index.json.gz")
    examine("UNIT OVERVIEW", "unit_overview.json.gz")
    examine("LOCATIONS (SURVEY / TP / FP)", "locations.json.gz")
    examine("COLLECTION ACCOUNT", "collection_account.json.gz")
    examine("NOC / BU", "latest_noc_bu.json.gz")
    examine("APPLICATIONS (EXTENSIONS / ALTERATIONS)", "all_applications.json.gz")

if __name__ == "__main__":
    main()
