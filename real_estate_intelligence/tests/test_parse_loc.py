import gzip
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_PROJECTS_DIR = BASE_DIR / "gujrera_pipeline" / "data" / "runs" / "nine_projects_2026_10_15" / "raw" / "projects"

for p in sorted(RAW_PROJECTS_DIR.iterdir()):
    if not p.is_dir(): continue
    f = p / "locations.json.gz"
    if not f.exists(): continue
    raw = gzip.decompress(f.read_bytes())
    d = json.loads(raw.decode("utf-8-sig"))
    inner = d.get("data", d)
    addr = inner.get("address") or ""
    coords = inner.get("coordinates") or []
    lat = coords[0].get("lat") if coords else None
    lng = coords[0].get("lang") if coords else None
    
    # Try regex on address for TP / FP / Survey if not explicit
    fp_match = re.search(r"F\.?P\.?\s*(?:No\.?)?\s*([0-9A-Za-z/]+)", addr, re.IGNORECASE)
    tp_match = re.search(r"T\.?P\.?\s*(?:S\.?)?\s*(?:No\.?)?\s*([0-9A-Za-z/()\s-]+?)(?:Near|Road|,|$)", addr, re.IGNORECASE)
    sr_match = re.search(r"(?:Survey|Block)\s*(?:No\.?)?\s*([0-9A-Za-z/+,]+)", addr, re.IGNORECASE)
    
    fp = fp_match.group(1).strip() if fp_match else inner.get("finalPlotNo")
    tp = tp_match.group(1).strip() if tp_match else inner.get("tpScheme")
    sr = sr_match.group(1).strip() if sr_match else inner.get("surveyNo")
    
    print(f"Project {p.name}:")
    print(f"  Addr: {addr[:70]}...")
    print(f"  Parsed: FP={fp} | TP={tp} | Survey={sr}")
    print(f"  GPS: {lat}, {lng} -> Maps: https://www.google.com/maps/search/?api=1&query={lat},{lng}" if lat and lng else "  GPS: None")
