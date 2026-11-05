import gzip
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_PROJECTS_DIR = BASE_DIR / "gujrera_pipeline" / "data" / "runs" / "nine_projects_2026_10_15" / "raw" / "projects"

for p in sorted(RAW_PROJECTS_DIR.iterdir()):
    if not p.is_dir(): continue
    f = p / "qpr_progress.json.gz"
    if not f.exists(): continue
    raw = gzip.decompress(f.read_bytes())
    d = json.loads(raw.decode("utf-8-sig"))
    inner = d.get("data", d)
    print(f"\nProject {p.name} qpr_progress:")
    if isinstance(inner, list):
        print(f"  Count: {len(inner)}")
        for it in inner[:4]:
            print(f"    {it.get('qtr_name')}: {it.get('project_progress')}%")
