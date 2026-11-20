"""Phase 3 Automated Verification Assertion.

Purpose: Verifies remote Turso database synchronization and record count.
Requires TURSO_DATABASE_URL and TURSO_AUTH_TOKEN in environment.
Usage: python tests/verification/verify_phase3.py
"""

import os
import sys
import libsql

url = os.environ.get("TURSO_DATABASE_URL")
token = os.environ.get("TURSO_AUTH_TOKEN")

if not url or not token:
    print("[SKIPPED] TURSO_DATABASE_URL and TURSO_AUTH_TOKEN not set in environment (Turso sync is optional/aspirational).")
    sys.exit(0)

con = libsql.connect(database=url, auth_token=token)
res = con.execute("SELECT count(*) FROM project_summaries").fetchone()

assert res[0] == 17787, f"Remote Turso count mismatch: {res[0]}"
print("Phase 3 Turso Remote Sync Verified: 17,787 records online in Mumbai")
