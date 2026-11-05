import gzip
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_PROJECTS_DIR = BASE_DIR / "gujrera_pipeline" / "data" / "runs" / "nine_projects_2026_10_15" / "raw" / "projects"

for p in sorted(RAW_PROJECTS_DIR.iterdir()):
    if not p.is_dir(): continue
    f = p / "locations.json.gz"
    if f.exists():
        raw = gzip.decompress(f.read_bytes())
        d = json.loads(raw.decode("utf-8-sig"))
        print(f"Project {p.name} locations keys: {list(d.keys())}")
        inner = d.get("data", d)
        if isinstance(inner, dict):
            print(f"  inner keys: {list(inner.keys())}")
            for k, v in inner.items():
                if v:
                    print(f"    {k}: {str(v)[:150]}")
        break
