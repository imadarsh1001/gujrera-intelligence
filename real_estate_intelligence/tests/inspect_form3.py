import gzip
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_PROJECTS_DIR = BASE_DIR / "gujrera_pipeline" / "data" / "runs" / "nine_projects_2026_10_15" / "raw" / "projects"

for p in sorted(RAW_PROJECTS_DIR.iterdir()):
    if not p.is_dir(): continue
    f = p / "latest_form_three.json.gz"
    if not f.exists(): continue
    raw = gzip.decompress(f.read_bytes())
    d = json.loads(raw.decode("utf-8-sig"))
    inner = d.get("data", d)
    print(f"\nProject {p.name} latest_form_three keys: {list(inner.keys()) if isinstance(inner, dict) else len(inner)}")
    if isinstance(inner, dict):
        for k in ['estimatedCost', 'incurredCost', 'certIssueDate', 'totalCost', 'paidLandCost', 'otherCost']:
            if k in inner:
                print(f"  {k}: {inner[k]}")
    break
