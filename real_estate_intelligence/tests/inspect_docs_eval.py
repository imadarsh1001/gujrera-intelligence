import gzip
import json
import ast
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
f = BASE_DIR / "gujrera_pipeline" / "data" / "runs" / "nine_projects_2026_10_15" / "raw" / "projects" / "13560" / "documents.json.gz"
raw = gzip.decompress(f.read_bytes())
d = json.loads(raw.decode("utf-8-sig"))
data_str = d.get("data")
parsed = ast.literal_eval(data_str) if isinstance(data_str, str) else data_str

print("--- ALL KEYS IN findoc ---")
findoc = parsed.get("findoc", {})
for k, v in findoc.items():
    if v not in (None, "", "null") and not k.endswith("UId") and not k.endswith("_UId"):
        print(f"  {k}: {v}")

print("\n--- ALL KEYS IN projectdoc ---")
pdoc = parsed.get("projectdoc", {})
for k, v in pdoc.items():
    if v not in (None, "", "null") and not k.endswith("UId") and not k.endswith("_UId"):
        print(f"  {k}: {v}")
