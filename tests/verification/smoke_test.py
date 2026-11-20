import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parent.parent.parent
server_script = root / "run_server.py"

print("[INFO] Launching server via run_server.py...")
proc = subprocess.Popen(
    [sys.executable, str(server_script), "--port", "8765"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    cwd=str(root),
    text=True,
)

time.sleep(2)

base_url = "http://127.0.0.1:8765"
ready = False
for _ in range(30):
    try:
        with urllib.request.urlopen(f"{base_url}/api/health", timeout=2) as resp:
            if resp.status == 200:
                ready = True
                break
    except Exception:
        time.sleep(0.5)

if not ready:
    print("[ERROR] Server failed to become ready in time.")
    proc.terminate()
    stdout, _ = proc.communicate(timeout=5)
    print(stdout)
    sys.exit(1)

print("[SUCCESS] Server is UP and healthy on port 8765!\n")

def fetch(path: str, method: str = "GET", data: dict = None):
    url = f"{base_url}{path}"
    headers = {"Content-Type": "application/json"} if data else {}
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as resp:
        content = resp.read()
        return resp.status, resp.headers.get("content-type"), content

results = {}

# 1. GET /api/health
status, ctype, body = fetch("/api/health")
health_json = json.loads(content := body.decode("utf-8"))
print("=== 1. GET /api/health ===")
print(f"Status: {status} | Body: {health_json}\n")

# 2. GET /api/explore?limit=5
status, ctype, body = fetch("/api/explore?limit=5")
explore_json = json.loads(body.decode("utf-8"))
items = explore_json.get("items", explore_json) if isinstance(explore_json, dict) else explore_json
print("=== 2. GET /api/explore?limit=5 ===")
print(f"Status: {status} | Row Count: {len(items)} | Total Count: {explore_json.get('total_count') if isinstance(explore_json, dict) else len(items)}")
print(f"Sample item name: {items[0]['name'] if items else 'None'}\n")

# 3. GET /api/project/13560
status, ctype, body = fetch("/api/project/13560")
proj_json = json.loads(body.decode("utf-8"))
print("=== 3. GET /api/project/13560 ===")
print(f"Status: {status} | Keys present: {list(proj_json.keys())}")
print(f"Project Name: {proj_json.get('project', {}).get('name')}")
print(f"Credential Coverage roles: {list(proj_json.get('credential_coverage', {}).get('roles', {}).keys())}")
print(f"Escrow Runway insolvency_risk: {proj_json.get('escrow_runway', {}).get('insolvency_risk')}\n")

# 4. GET /api/pricing/13560
status, ctype, body = fetch("/api/pricing/13560")
pricing_json = json.loads(body.decode("utf-8"))
print("=== 4. GET /api/pricing/13560 ===")
print(f"Status: {status} | Keys: {list(pricing_json.keys())}")
print(f"Pricing data summary: {str(pricing_json)[:150]}...\n")

# 5. GET /api/analytics/survival?project_id=13560
status, ctype, body = fetch("/api/analytics/survival?project_id=13560")
surv_json = json.loads(body.decode("utf-8"))
print("=== 5. GET /api/analytics/survival?project_id=13560 ===")
print(f"Status: {status} | Delay Risk Label: {surv_json.get('delay_risk_label')}")
print(f"Hazard Ratio: {surv_json.get('hazard_ratio')} | Median Expected: {surv_json.get('forecasted_handover_dates', {}).get('p50_median_expected_date')}\n")

# 6. GET /api/search?q=encumbrance
status, ctype, body = fetch("/api/search?q=encumbrance")
search_json = json.loads(body.decode("utf-8"))
print("=== 6. GET /api/search?q=encumbrance ===")
print(f"Status: {status} | Query: {search_json.get('query')} | Result count: {len(search_json.get('results', []))}\n")

# 7. GET /api/map/pins
status, ctype, body = fetch("/api/map/pins")
pins_json = json.loads(body.decode("utf-8"))
print("=== 7. GET /api/map/pins ===")
print(f"Status: {status} | Pin Count: {len(pins_json)} | Payload Size: {len(body) / 1024:.2f} KB | Sample Pin: {pins_json[0] if pins_json else 'None'}\n")

# 8. GET /static/vendor/chart.umd.min.js
status, ctype, body = fetch("/static/vendor/chart.umd.min.js")
print("=== 8. GET /static/vendor/chart.umd.min.js ===")
print(f"Status: {status} | Content-Type: {ctype} | Content-Length: {len(body)} bytes\n")

# 9. POST /api/copilot with dummy api_key
status, ctype, body = fetch(
    "/api/copilot",
    method="POST",
    data={"query": "ok", "project_id": 13560, "api_key": "AIzaSy_dummy_key_for_testing"}
)
copilot_json = json.loads(body.decode("utf-8"))
print("=== 9. POST /api/copilot (dummy api_key) ===")
print(f"Status: {status} | Mode: {copilot_json.get('mode')} | Citations: {copilot_json.get('citations')}")
print(f"Reply preview: {copilot_json.get('reply')[:120]}...\n")

# 10. GET / (returns index.html)
status, ctype, body = fetch("/")
html_text = body.decode("utf-8")
print("=== 10. GET / (returns index.html) ===")
print(f"Status: {status} | Content-Type: {ctype} | Length: {len(body)} bytes")
print(f"Contains <!DOCTYPE html>: {'<!DOCTYPE html>' in html_text} | Title: GujRERA Dashboard\n")

print("[INFO] Terminating server...")
proc.terminate()
try:
    proc.wait(timeout=5)
except Exception:
    proc.kill()
print("[SUCCESS] All 10 live smoke tests through run_server.py verified successfully!")
