import gzip
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_PROJECTS_DIR = BASE_DIR / "gujrera_pipeline" / "data" / "runs" / "nine_projects_2026_10_15" / "raw" / "projects"

for p in sorted(RAW_PROJECTS_DIR.iterdir()):
    if not p.is_dir(): continue
    f = p / "annual_compliance.json.gz"
    if not f.exists(): continue
    raw = gzip.decompress(f.read_bytes())
    d = json.loads(raw.decode("utf-8-sig"))
    print(f"\n--- Project {p.name} Form 5 Compliance ---")
    if isinstance(d, list):
        for item in d:
            yr = item.get("projectFinancialYear")
            st = item.get("projectFinancialYearStatus")
            sub = item.get("submittedOn")
            print(f"  FY {yr}: Status={st}, Submitted={sub}")
