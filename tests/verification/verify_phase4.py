"""Phase 4 Live Server & API Integration Verification.

Purpose: Boots local FastAPI server in a background thread and validates /api/health,
/api/map/pins compact 6-tuple array, and /api/explore pagination.
Usage: python tests/verification/verify_phase4.py
"""

import asyncio
import json
import os
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "real_estate_intelligence"))

from api.index import app
import uvicorn

def get_free_port():
    for p in [8000, 8001, 8080, 8765, 9000, 8911]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except Exception:
                continue
    return 8911

port = int(os.getenv("PORT", str(get_free_port())))
print(f"Starting local FastAPI server on port {port}...")

class ServerThread(threading.Thread):
    def __init__(self, app, host="127.0.0.1", port=port):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.app = app

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        config = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="warning")
        self.server = uvicorn.Server(config)
        loop.run_until_complete(self.server.serve())

    def stop(self):
        if hasattr(self, "server"):
            self.server.should_exit = True

server = ServerThread(app, port=port)
server.start()

ready = False
for _ in range(30):
    try:
        r = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1)
        if r.status == 200:
            ready = True
            break
    except Exception:
        time.sleep(0.1)

assert ready, f"Server failed to start on port {port}"

# Phase 4 Automated Verification Assertions:
res = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health")
assert res.status == 200
data = json.loads(res.read())
assert data["status"] == "ok" and data["projects"] == 17787, f"Health assertion failed: {data}"

pins_res = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/map/pins?district=Ahmedabad")
assert pins_res.status == 200
pins_data = json.loads(pins_res.read())
assert len(pins_data) > 0 and len(pins_data[0]) == 6, f"Pins assertion failed: len={len(pins_data)}"

exp_res = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/explore?limit=5")
assert exp_res.status == 200
exp_data = json.loads(exp_res.read())
assert exp_data["total_count"] == 17787 and len(exp_data["items"]) == 5, f"Explore assertion failed: {exp_data}"

server.stop()
print("Phase 4 Health Probe & 6-Tuple Map Route Verified")
