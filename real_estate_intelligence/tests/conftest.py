"""Pytest configuration and shared fixtures for sovereign forensic agent tests."""

import json
import os
import shutil
import socket
import tempfile
from pathlib import Path
from typing import Generator

import pytest

# Ensure real_estate_intelligence package and root are importable
root_dir = Path(__file__).resolve().parent.parent.parent
sys_paths = [str(root_dir), str(root_dir / "real_estate_intelligence")]
import sys
for p in sys_paths:
    if p not in sys.path:
        sys.path.insert(0, p)

from api.index import AppState, app
from real_estate_intelligence.graph.network import KnowledgeGraph


# Socket security gate: block all outbound non-local network access
_ORIG_SOCKET_CONNECT = socket.socket.connect


def _guarded_connect(self, address):
    host = address[0] if isinstance(address, tuple) and len(address) > 0 else str(address)
    # Allow local loopback for asyncio / uvicorn / httpx
    if host in ("127.0.0.1", "localhost", "::1"):
        return _ORIG_SOCKET_CONNECT(self, address)
    raise RuntimeError(
        f"Security Gate Violation: Outbound non-local network connection blocked in test harness: {address}"
    )


@pytest.fixture(autouse=True)
def guard_outbound_network(monkeypatch):
    """Enforce strict socket gate rejecting external network connections."""
    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)


@pytest.fixture(scope="session")
def seeded_test_db() -> Generator[Path, None, None]:
    """Create a temporary test database seeded with projects 9036, 16562, and SHREEJI ASSOCIATES."""
    src_db = Path(__file__).resolve().parent.parent / "data" / "test_intelligence.sqlite"
    tmp_file = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp_file.close()
    shutil.copyfile(src_db, tmp_file.name)
    db_path = Path(tmp_file.name)

    import sqlite3
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row

    # Seed required projects into projects table if missing
    con.execute("""
        INSERT OR REPLACE INTO projects (
            project_id, name, registration_number, promoter_id, promoter_name, district, taluka,
            project_type, project_status, tier, completion_date, latitude, longitude
        ) VALUES 
        (9036, 'SHIVAM ELEGANCE', 'PR/GJ/9036', 8888, 'SHREEJI ASSOCIATES', 'Vadodara', 'Vadodara', 'Residential', 'REGISTERED', 'statewide', '2024-07-12', 22.3072, 73.1812),
        (9037, 'SHREEJI PARK', 'PR/GJ/9037', 8888, 'SHREEJI ASSOCIATES', 'Rajkot', 'Rajkot', 'Residential', 'REGISTERED', 'statewide', '2025-01-01', 22.3039, 70.8022),
        (8001, 'PLACEHOLDER TOWER', 'PR/GJ/8001', 8889, 'DEV 8001', 'Ahmedabad', 'Daskroi', 'Residential', 'REGISTERED', 'statewide', '2023-01-01', 23.0100, 72.5000),
        (8002, 'PARTIAL BLOCKS', 'PR/GJ/8002', 8890, 'DEV 8002', 'Ahmedabad', 'Daskroi', 'Residential', 'REGISTERED', 'statewide', '2023-01-01', 23.0200, 72.5100),
        (14360, 'SHALIGRAM PRIME', 'PR/GJ/14360', 8891, 'SHALIGRAM GROUP', 'Ahmedabad', 'Ahmedabad', 'Residential', 'REGISTERED', 'statewide', '2025-06-01', 23.0300, 72.5800)
    """)

    # Seed noc_bu_records
    con.execute("""
        INSERT OR REPLACE INTO noc_bu_records (
            project_id, block_name, bu_check, bu_date, fire_doc_id, lift_doc_id
        ) VALUES 
        (9036, 'A', 'YES', '2024-07-12', '4095612', NULL),
        (8002, 'A', 'YES', '2023-06-01', '4091111', NULL),
        (8002, 'B', 'NO', NULL, NULL, NULL)
    """)

    # Seed project_summaries table
    con.execute("CREATE TABLE IF NOT EXISTS project_summaries AS SELECT * FROM projects WHERE 1=0")
    # Fetch existing columns of project_summaries
    cols = [r[1] for r in con.execute("PRAGMA table_info(project_summaries)").fetchall()]
    if not cols:
        # Create standard project_summaries schema if empty
        con.execute("""
            CREATE TABLE IF NOT EXISTS project_summaries (
                project_id INTEGER PRIMARY KEY,
                name TEXT,
                registration_number TEXT,
                promoter_name TEXT,
                district TEXT,
                taluka TEXT,
                project_type TEXT,
                project_status TEXT,
                tier TEXT,
                completion_date TEXT,
                total_units INTEGER,
                booked_units INTEGER,
                unbooked_units INTEGER,
                absorption_pct REAL,
                min_price_booked REAL,
                max_price_booked REAL,
                min_rate_sqft_booked REAL,
                avg_rate_sqft_booked REAL,
                unit_types_json TEXT,
                booked_by_type_json TEXT,
                has_bu_noc INTEGER,
                bu_certificate_no TEXT,
                architect_names TEXT,
                engineer_names TEXT,
                ca_name TEXT,
                escrow_bank_name TEXT,
                latitude REAL,
                longitude REAL,
                is_exact_gps INTEGER
            )
        """)

    summaries = [
        (9036, "SHIVAM ELEGANCE", "PR/GJ/9036", "SHREEJI ASSOCIATES", "Vadodara", "Vadodara", "Residential", "REGISTERED", "statewide", "2024-07-12", 100, 80, 20, 80.0, 3000000.0, 6000000.0, 4000.0, 4500.0, json.dumps(["2 BHK"]), json.dumps({"2 BHK": 80}), 1, "4095612", "Arch Shivam", "Eng Shivam", "CA Shivam", "SBI", 22.3072, 73.1812, 1),
        (9037, "SHREEJI PARK", "PR/GJ/9037", "SHREEJI ASSOCIATES", "Rajkot", "Rajkot", "Residential", "REGISTERED", "statewide", "2025-01-01", 50, 40, 10, 80.0, 2500000.0, 5000000.0, 3500.0, 4000.0, json.dumps(["2 BHK"]), json.dumps({"2 BHK": 40}), 0, None, "Arch Rajkot", "Eng Rajkot", "CA Rajkot", "HDFC", 22.3039, 70.8022, 1),
        (16562, "THE BALCONY", "PR/GJ/GANDHINAGAR/GANDHINAGAR/Others/RAA08643/220621", "SHILP INFRASPACE LLP", "Gandhinagar", "Gandhinagar", "Residential", "REGISTERED", "deep_audit", "2026-12-31", 120, 90, 30, 75.0, 5000000.0, 10000000.0, 5500.0, 6000.0, json.dumps(["3 BHK", "4 BHK"]), json.dumps({"3 BHK": 60, "4 BHK": 30}), 0, None, "Arch Shilp", "Eng Shilp", "CA Shilp", "ICICI", 23.2156, 72.6369, 1),
        (8001, "PLACEHOLDER TOWER", "PR/GJ/8001", "DEV 8001", "Ahmedabad", "Daskroi", "Residential", "REGISTERED", "statewide", "2023-01-01", 100, 80, 20, 80.0, 3000000.0, 6000000.0, 4000.0, 4500.0, json.dumps(["2 BHK"]), json.dumps({"2 BHK": 80}), 1, "BU-VERIFIED", "Arch 8001", None, None, "SBI", 23.0100, 72.5000, 1),
        (8002, "PARTIAL BLOCKS", "PR/GJ/8002", "DEV 8002", "Ahmedabad", "Daskroi", "Residential", "REGISTERED", "statewide", "2023-01-01", 200, 150, 50, 75.0, 3500000.0, 7000000.0, 4500.0, 5000.0, json.dumps(["2 BHK"]), json.dumps({"2 BHK": 150}), 0, None, "Arch 8002", None, None, "SBI", 23.0200, 72.5100, 1),
        (14360, "SHALIGRAM PRIME", "PR/GJ/14360", "SHALIGRAM GROUP", "Ahmedabad", "Ahmedabad", "Residential", "REGISTERED", "statewide", "2025-06-01", 150, 100, 50, 66.7, 4000000.0, 8000000.0, 5000.0, 5500.0, json.dumps(["3 BHK"]), json.dumps({"3 BHK": 100}), 1, "4095615", "Arch Shaligram", "Eng Shaligram", "CA Shaligram", "SBI", 23.0300, 72.5800, 1),
    ]

    for s in summaries:
        con.execute("""
            INSERT OR REPLACE INTO project_summaries (
                project_id, name, registration_number, promoter_name, district, taluka,
                project_type, project_status, tier, completion_date, total_units,
                booked_units, unbooked_units, absorption_pct, min_price_booked,
                max_price_booked, min_rate_sqft_booked, avg_rate_sqft_booked,
                unit_types_json, booked_by_type_json, has_bu_noc, bu_certificate_no,
                architect_names, engineer_names, ca_name, escrow_bank_name,
                latitude, longitude, is_exact_gps
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, s)

    # Build knowledge graph tables BEFORE switching to read-only
    kg = KnowledgeGraph(con)
    kg.build_graph()

    con.commit()
    con.close()

    yield db_path

    # Teardown
    if AppState.con:
        try:
            AppState.con.close()
        except Exception:
            pass
    if os.path.exists(tmp_file.name):
        try:
            os.remove(tmp_file.name)
        except Exception:
            pass


@pytest.fixture
def agent_test_env(seeded_test_db, monkeypatch):
    """Set up read-only AppState pointing to seeded_test_db."""
    AppState.setup_backends(seeded_test_db, read_only=True)
    monkeypatch.setenv("ENABLE_FORENSIC_AGENT", "1")
    monkeypatch.setenv("LANGGRAPH_STRICT_MSGPACK", "true")
    yield seeded_test_db
    AppState.setup_backends(seeded_test_db, read_only=True)
