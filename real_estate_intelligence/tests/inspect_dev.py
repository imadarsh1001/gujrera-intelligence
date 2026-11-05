import gzip
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_PROJECTS_DIR = BASE_DIR / "gujrera_pipeline" / "data" / "runs" / "nine_projects_2026_10_15" / "raw" / "projects"

for p in sorted(RAW_PROJECTS_DIR.iterdir()):
    if not p.is_dir(): continue
    f = p / "project_details.json.gz"
    if not f.exists(): continue
    raw = gzip.decompress(f.read_bytes())
    d = json.loads(raw.decode("utf-8-sig"))
    data = d.get("data", d)
    print(f"\n--- Project {p.name} Professionals & Development ---")
    archs = data.get("archlist") or []
    engs = data.get("englist") or []
    cas = data.get("calist") or []
    contrs = data.get("contr") or []
    devs = data.get("dev") or []
    print(f"  Architects ({len(archs)}): {[a.get('name') + ' (' + str(a.get('licenceNO')) + ')' for a in archs]}")
    print(f"  Engineers ({len(engs)}): {[e.get('name') + ' (' + str(e.get('licenceNO')) + ')' for e in engs]}")
    print(f"  CAs ({len(cas)}): {[c.get('name') + ' (Mem: ' + str(c.get('membershipNo')) + ')' for c in cas]}")
    print(f"  Contractors ({len(contrs)}): {[co.get('name') for co in contrs]}")
    if devs:
        d0 = devs[0]
        print(f"  Water Supply: {d0.get('waterSplyFlag')}, Source: {d0.get('waterSplyFromSource')}, Sewage: {d0.get('sewDisposalFlag')}, SwimPool: {d0.get('sewSwimCapacityFlag')} ({d0.get('sewSwimCapLiter')} L)")
