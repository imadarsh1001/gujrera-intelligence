import gzip
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_PROJECTS_DIR = BASE_DIR / "gujrera_pipeline" / "data" / "runs" / "nine_projects_2026_10_15" / "raw" / "projects"

for p in sorted(RAW_PROJECTS_DIR.iterdir()):
    if not p.is_dir(): continue
    f = p / "banks.json.gz"
    if f.exists():
        raw = gzip.decompress(f.read_bytes())
        d = json.loads(raw.decode("utf-8-sig"))
        print(f"\n--- Project {p.name} banks ---")
        inner = d.get("data", d)
        if isinstance(inner, list):
            for b in inner:
                print(f"  Bank: {b.get('bankName')}, Branch: {b.get('branchName')}, Deposit: {b.get('depositAmt')}, Withdrawal: {b.get('withdrwalAmt')}, Opening: {b.get('openingBal')}, Closing: {b.get('closingBal')}, From: {b.get('startDate')}, To: {b.get('endDate')}")
        elif isinstance(inner, dict):
            for k, v in inner.items():
                print(f"  {k}: {str(v)[:100]}")
