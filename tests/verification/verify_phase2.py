"""Phase 2 Ingestion & Data Quality Assertion.

Purpose: Verifies statewide database counts (17,787 projects, 826,162 unit transactions),
ensures zero unmasked bank accounts (PII compliance), and zero stacked GPS pins.
Usage: python tests/verification/verify_phase2.py
"""

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
db_path = ROOT / "data" / "intelligence.sqlite"

con = sqlite3.connect(db_path)
cur = con.cursor()
p_count = cur.execute("SELECT count(*) FROM projects").fetchone()[0]
assert p_count == 17787, f"Expected 17787 projects, got {p_count}"
deep_count = cur.execute('SELECT count(*) FROM projects WHERE tier = "deep_audit"').fetchone()[0]
assert deep_count == 9, f"Expected 9 deep projects, got {deep_count}"
u_count = cur.execute("SELECT count(*) FROM unit_transactions").fetchone()[0]
assert u_count == 826162, f"Expected 826162 units, got {u_count}"
sum_count = cur.execute("SELECT count(*) FROM project_summaries").fetchone()[0]
assert sum_count == 17787, f"Expected 17787 summaries, got {sum_count}"
unmasked_banks = cur.execute(
    'SELECT count(*) FROM banks WHERE account_number_masked NOT LIKE "****%" AND account_number_masked IS NOT NULL'
).fetchone()[0]
assert unmasked_banks == 0, f"Found {unmasked_banks} unmasked bank accounts in target DB"
stacked_pins = cur.execute(
    "SELECT latitude, longitude, count(*) FROM project_summaries GROUP BY latitude, longitude HAVING count(*) > 1"
).fetchall()
assert len(stacked_pins) == 0, f"Found {len(stacked_pins)} stacked coordinate pairs"
print("Phase 2 Ingestion Assertions Passed: 17,787 projects, 9 deep, 826,162 units, zero unmasked accounts, zero stacked pins")
