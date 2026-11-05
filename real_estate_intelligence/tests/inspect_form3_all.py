import gzip
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_PROJECTS_DIR = BASE_DIR / "gujrera_pipeline" / "data" / "runs" / "nine_projects_2026_10_15" / "raw" / "projects"

def safe_float(v):
    if v is None: return None
    try: return float(v)
    except: return None

for p in sorted(RAW_PROJECTS_DIR.iterdir()):
    if not p.is_dir(): continue
    f = p / "latest_form_three.json.gz"
    if not f.exists(): continue
    raw = gzip.decompress(f.read_bytes())
    d = json.loads(raw.decode("utf-8-sig"))
    inner = d.get("data", d)
    if not isinstance(inner, dict): continue

    print(f"\n==================== PROJECT {p.name}: {inner.get('projectName')} ====================")
    print(f"  CA Auditor: {inner.get('caName')} ({inner.get('caFirmName')}), UDIN: {inner.get('caUdiNo')}, MemberNo: {inner.get('caMemberShipNumber')}")
    print(f"  Inventory: Resi={inner.get('totalResidential')}, Shops={inner.get('totalShop')}, Offices={inner.get('totalOffice')}, Total={inner.get('numberOfUnits')}")
    print(f"  Sales: Booked={inner.get('bookedUnit')}, Unbooked={inner.get('unBookedUnit')}")
    
    recv = safe_float(inner.get('receivedAmountTotal'))
    bal = safe_float(inner.get('balanceAmountTotal'))
    booked_val = safe_float(inner.get('totalBookedUnitConside'))
    unbooked_val = safe_float(inner.get('totalUnbookedUnitConside'))
    print(f"  Cash Collected from Buyers: Rs. {recv:,.2f}" if recv is not None else f"  Cash Collected: {recv}")
    print(f"  Pending Receivables from Buyers: Rs. {bal:,.2f}" if bal is not None else f"  Pending Receivables: {bal}")
    print(f"  Booked Inventory Value: Rs. {booked_val:,.2f}" if booked_val is not None else f"  Booked Value: {booked_val}")
    print(f"  Unsold Inventory Value: Rs. {unbooked_val:,.2f}" if unbooked_val is not None else f"  Unsold Value: {unbooked_val}")
    print(f"  Covered Parking: Proposed={inner.get('noCoveredParkProposed')}, Booked={inner.get('noCoveredParkBooked')} | Open Parking: Proposed={inner.get('noOpenParkProposed')}, Booked={inner.get('noOpenParkNoBooked')}")
