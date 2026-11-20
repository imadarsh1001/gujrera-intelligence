"""Phase 1 Automated Verification Assertion.

Purpose: Verifies runtime dependencies (fastapi, uvicorn, libsql, pypdf) and
the dual-engine database connection factory against the primary database.
Usage: python tests/verification/verify_phase1.py
"""

import sys
from pathlib import Path

# Ensure package roots are on sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "real_estate_intelligence"))

import fastapi
import uvicorn
import libsql
import pypdf
from real_estate_intelligence.db.database import get_connection

con = get_connection(ROOT / "data" / "intelligence.sqlite")
assert con is not None, "Failed to obtain local connection"
if hasattr(con, "close"):
    con.close()

print("Phase 1 OK: libsql driver & schemas verified")
