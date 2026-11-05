import gzip
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_PROJECTS_DIR = BASE_DIR / "gujrera_pipeline" / "data" / "runs" / "nine_projects_2026_10_15" / "raw" / "projects"

doc_types = {}
for p in sorted(RAW_PROJECTS_DIR.iterdir()):
    if not p.is_dir(): continue
    f = p / "documents.json.gz"
    if not f.exists(): continue
    raw = gzip.decompress(f.read_bytes())
    d = json.loads(raw.decode("utf-8-sig"))
    inner = d.get("data", d)
    if isinstance(inner, list):
        for item in inner:
            t = item.get("docType") or item.get("documentType") or item.get("name") or "Unknown"
            doc_types[t] = doc_types.get(t, 0) + 1
    elif isinstance(inner, dict):
        for k, v in inner.items():
            if isinstance(v, list):
                for item in v:
                    t = item.get("docType") or item.get("docName") or item.get("name") or k
                    doc_types[t] = doc_types.get(t, 0) + 1

print("=== DOCUMENT CATEGORIES IN RAW DATASET ===")
for dt, count in sorted(doc_types.items(), key=lambda x: -x[1])[:30]:
    print(f"  {dt:<40}: {count} documents")
