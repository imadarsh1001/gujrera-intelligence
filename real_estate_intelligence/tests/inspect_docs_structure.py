import gzip
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
f = BASE_DIR / "gujrera_pipeline" / "data" / "runs" / "nine_projects_2026_10_15" / "raw" / "projects" / "13560" / "documents.json.gz"
raw = gzip.decompress(f.read_bytes())
d = json.loads(raw.decode("utf-8-sig"))
print(type(d))
if isinstance(d, dict):
    print("Keys:", list(d.keys()))
    print("Sample:", json.dumps({k: str(v)[:100] for k, v in d.items()}, indent=2))
elif isinstance(d, list):
    print("Length:", len(d))
    print("Sample item 0:", json.dumps(d[0], indent=2)[:500])
