import gzip
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_PROJECTS_DIR = BASE_DIR / "gujrera_pipeline" / "data" / "runs" / "nine_projects_2026_10_15" / "raw" / "projects"

def load_gz(p, fname):
    f = p / fname
    if not f.exists(): return None
    try:
        raw = gzip.decompress(f.read_bytes())
        d = json.loads(raw.decode("utf-8-sig"))
        return d.get("data", d)
    except: return None

for p in sorted(RAW_PROJECTS_DIR.iterdir()):
    if not p.is_dir(): continue
    pid = p.name
    
    # 1. Loan details
    loans = load_gz(p, "latest_loan_details.json.gz") or []
    # 2. Location details
    loc = load_gz(p, "locations.json.gz") or {}
    # 3. Quarter index defaults/penalties
    q_idx = load_gz(p, "quarter_index.json.gz") or []
    # 4. Unit overview
    unit_ov = load_gz(p, "unit_overview.json.gz") or {}
    # 5. Collection account
    coll = load_gz(p, "collection_account.json.gz") or {}
    # 6. NOC BU
    noc = load_gz(p, "latest_noc_bu.json.gz") or {}
    # 7. Applications
    apps = load_gz(p, "all_applications.json.gz") or []

    print(f"\n==================== PROJECT {pid} ====================")
    # Loans
    print(f"Loans count: {len(loans) if isinstance(loans, list) else 'dict'}")
    if isinstance(loans, list) and loans:
        for l in loans:
            print(f"  Loan: Bank={l.get('bankName')}, Amount={l.get('sanctionAmt')}, LoanType={l.get('loanType')}, Account={l.get('accountNo') and '***'}")

    # Location Survey / TP / FP
    if isinstance(loc, dict):
        loc_data = loc.get("projectLocation") or loc.get("location") or loc
        print(f"  Location: Dist={loc_data.get('district')}, Taluka={loc_data.get('taluka')}, TPS={loc_data.get('tpScheme')}, FP={loc_data.get('finalPlotNo')}, Survey={loc_data.get('surveyNo')}")
        latlngs = loc.get("latLngList") or []
        print(f"  GPS Coordinates: {len(latlngs)} boundary points")

    # Penalties / Defaults in Quarter Index
    defaults = [q for q in q_idx if isinstance(q, dict) and (q.get("isDefault") == "YES" or (q.get("penaltyAmt") or 0) > 0)]
    print(f"  Quarter Defaults/Penalties: {len(defaults)} quarters flagged")
    for d in defaults[:3]:
        print(f"    Quarter: {d.get('quarterName')}, Default={d.get('isDefault')}, Penalty={d.get('penaltyAmt')}, Remarks={d.get('authRemarks')}")

    # Unit overview stats
    if isinstance(unit_ov, dict) and unit_ov.get("totunit"):
        print(f"  Unit Overview: Total Units={unit_ov.get('totunit')}, Min Area={unit_ov.get('mincararea')}, Max Area={unit_ov.get('maxcararea')}, Min Cost={unit_ov.get('mincost')}, Max Cost={unit_ov.get('maxcost')}")

    # NOC BU
    bu_blocks = []
    if isinstance(noc, dict):
        for b in noc.get("blocksNocDocList") or []:
            if b.get("buCheck") == "YES":
                bu_blocks.append((b.get("blockName"), b.get("buDate"), b.get("buAppNumber")))
    print(f"  BU Permission verified blocks: {bu_blocks if bu_blocks else 'None'}")

    # Application types
    if isinstance(apps, list):
        app_types = [a.get("applicationType") for a in apps if isinstance(a, dict)]
        print(f"  Applications ({len(apps)}): {list(set(app_types))}")
