import gzip
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_PROJECTS_DIR = BASE_DIR / "gujrera_pipeline" / "data" / "runs" / "nine_projects_2026_10_15" / "raw" / "projects"

for p in sorted(RAW_PROJECTS_DIR.iterdir()):
    if not p.is_dir(): continue
    f = p / "collection_account.json.gz"
    if f.exists():
        raw = gzip.decompress(f.read_bytes())
        d = json.loads(raw.decode("utf-8-sig"))
        inner = d.get("data", d)
        print(f"Project {p.name} collection account: {inner}")
