"""Curated database management with dual-engine (local SQLite3 and remote Turso libSQL) support."""

import os
import sqlite3
from pathlib import Path
from typing import Any, Optional, Union

try:
    import libsql
except ImportError:
    libsql = None

from ..config import DEFAULT_DB_PATH


class LibsqlRow:
    """Row wrapper for libsql query results offering dict and sequence access."""

    def __init__(self, description, values):
        self._desc = description
        self._values = tuple(values)
        self._mapping = {d[0]: v for d, v in zip(description, values)}

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._mapping[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def keys(self):
        return self._mapping.keys()

    def values(self):
        return self._mapping.values()

    def items(self):
        return self._mapping.items()

    def get(self, key, default=None):
        return self._mapping.get(key, default)

    def __repr__(self):
        return f"LibsqlRow({self._mapping})"


class LibsqlCursorWrapper:
    """Cursor wrapper wrapping a libsql cursor to return LibsqlRow objects."""

    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, parameters=()):
        self._cursor.execute(sql, parameters)
        return self

    def executemany(self, sql, seq_of_parameters):
        self._cursor.executemany(sql, seq_of_parameters)
        return self

    def executescript(self, sql_script):
        self._cursor.executescript(sql_script)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        if self._cursor.description:
            return LibsqlRow(self._cursor.description, row)
        return row

    def fetchall(self):
        rows = self._cursor.fetchall()
        if not rows:
            return []
        if self._cursor.description:
            desc = self._cursor.description
            return [LibsqlRow(desc, r) for r in rows]
        return rows

    def fetchmany(self, size=None):
        rows = self._cursor.fetchmany(size) if size is not None else self._cursor.fetchmany()
        if not rows:
            return []
        if self._cursor.description:
            desc = self._cursor.description
            return [LibsqlRow(desc, r) for r in rows]
        return rows

    @property
    def description(self):
        return self._cursor.description

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def close(self):
        return self._cursor.close()

    def __iter__(self):
        while True:
            row = self.fetchone()
            if row is None:
                break
            yield row


class LibsqlConnectionWrapper:
    """Connection wrapper around a libsql.Connection providing consistent behavior."""

    def __init__(self, connection, is_remote: bool = False):
        self._con = connection
        self.is_remote = is_remote

    def cursor(self):
        return LibsqlCursorWrapper(self._con.cursor())

    def execute(self, sql, parameters=()):
        cur = self.cursor()
        cur.execute(sql, parameters)
        return cur

    def executemany(self, sql, seq_of_parameters):
        cur = self.cursor()
        cur.executemany(sql, seq_of_parameters)
        return cur

    def executescript(self, sql_script):
        return self._con.executescript(sql_script)

    def commit(self):
        return self._con.commit()

    def rollback(self):
        return self._con.rollback()

    def close(self):
        return self._con.close()

    def sync(self):
        if hasattr(self._con, "sync"):
            return self._con.sync()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()


def get_connection(db_path: Optional[Union[Path, str, Any]] = None) -> Any:
    """Connection factory returning a local SQLite3 or remote Turso libSQL connection."""
    if hasattr(db_path, "cursor") and hasattr(db_path, "execute"):
        return db_path

    turso_url = os.environ.get("TURSO_DATABASE_URL")
    turso_token = os.environ.get("TURSO_AUTH_TOKEN")

    if turso_url:
        if libsql is None:
            raise ImportError("libsql package is required to connect to Turso. Run: uv pip install libsql>=0.1.11")
        raw_con = libsql.connect(database=turso_url, auth_token=turso_token or "")
        raw_con.execute("SELECT 1")
        con = LibsqlConnectionWrapper(raw_con, is_remote=True)
        init_schema(con)
        return con

    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=30.0, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode = WAL;")
    con.execute("PRAGMA foreign_keys = ON;")
    con.execute("PRAGMA busy_timeout = 30000;")
    init_schema(con)
    return con


def init_schema(con: Any) -> None:
    """Initialize structured relational tables, forward migrations, and indexes."""
    con.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            project_id INTEGER PRIMARY KEY,
            run_id TEXT DEFAULT 'default_run',
            name TEXT NOT NULL,
            registration_number TEXT,
            promoter_id INTEGER,
            promoter_name TEXT,
            district TEXT NOT NULL,
            taluka TEXT,
            project_type TEXT,
            project_status TEXT,
            start_date TEXT,
            completion_date TEXT,
            total_units INTEGER,
            booked_units INTEGER,
            unbooked_units INTEGER,
            booking_rate_pct REAL,
            latest_form_one_progress_pct REAL,
            estimated_cost_inr REAL,
            incurred_cost_inr REAL,
            collection_status TEXT DEFAULT 'complete',
            -- Land & Spatial Identity
            tp_scheme TEXT,
            final_plot_no TEXT,
            survey_no TEXT,
            latitude REAL,
            longitude REAL,
            google_maps_url TEXT,
            -- Legal Handover Milestones
            society_reg_date TEXT,
            form_four_status TEXT,
            bu_status TEXT,
            -- Construction Velocity Analytics
            time_elapsed_pct REAL,
            engg_score_pct REAL,
            arch_score_pct REAL,
            velocity_ratio REAL,
            progress_status_label TEXT,
            -- Regulatory & Litigation Radar
            has_complaints INTEGER DEFAULT 0,
            complaints_count INTEGER DEFAULT 0,
            has_alterations INTEGER DEFAULT 0,
            alterations_count INTEGER DEFAULT 0,
            has_extensions INTEGER DEFAULT 0,
            extensions_count INTEGER DEFAULT 0,
            default_quarters_count INTEGER DEFAULT 0,
            tier TEXT NOT NULL DEFAULT 'statewide',
            has_deep_filings INTEGER NOT NULL DEFAULT 0,
            has_bu_noc INTEGER DEFAULT 0,
            bu_certificate_no TEXT,
            created_at_utc TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at_utc TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS project_summaries (
            project_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            registration_number TEXT,
            promoter_name TEXT,
            district TEXT NOT NULL,
            taluka TEXT,
            project_type TEXT,
            project_status TEXT,
            tier TEXT NOT NULL,
            completion_date TEXT,
            total_units INTEGER DEFAULT 0,
            booked_units INTEGER DEFAULT 0,
            unbooked_units INTEGER DEFAULT 0,
            absorption_pct REAL DEFAULT 0.0,
            min_price_booked REAL,
            max_price_booked REAL,
            min_rate_sqft_booked REAL,
            avg_rate_sqft_booked REAL,
            unit_types_json TEXT,
            booked_by_type_json TEXT,
            has_bu_noc INTEGER DEFAULT 0,
            bu_certificate_no TEXT,
            architect_names TEXT,
            engineer_names TEXT,
            ca_name TEXT,
            escrow_bank_name TEXT,
            latitude REAL,
            longitude REAL,
            is_exact_gps INTEGER DEFAULT 0,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE IF NOT EXISTS promoters (
            promoter_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            promoter_type TEXT,
            total_projects_claimed INTEGER,
            completed_projects_claimed INTEGER,
            ongoing_projects_claimed INTEGER,
            linked_gujrera_projects_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS professionals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            name TEXT NOT NULL,
            firm_name TEXT,
            license_or_reg_no TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE IF NOT EXISTS banks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            bank_name TEXT NOT NULL,
            branch_name TEXT,
            ifsc_code TEXT,
            account_type INTEGER DEFAULT 1,
            account_name TEXT,
            account_number_masked TEXT,
            deposit_amt REAL,
            withdrawal_amt REAL,
            opening_bal REAL,
            closing_bal REAL,
            opening_date TEXT,
            closing_date TEXT,
            passbook_id TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE IF NOT EXISTS inventory_blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            block_name TEXT NOT NULL,
            total_units INTEGER NOT NULL,
            booked_units INTEGER NOT NULL,
            unbooked_units INTEGER NOT NULL,
            booking_rate_pct REAL,
            residential_units INTEGER DEFAULT 0,
            commercial_units INTEGER DEFAULT 0,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_inv_block ON inventory_blocks(project_id, block_name);

        CREATE TABLE IF NOT EXISTS quarterly_timeline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            quarter_name TEXT NOT NULL,
            period_label TEXT,
            progress_percentage REAL,
            submission_date TEXT,
            form_one_id INTEGER,
            form_two_id INTEGER,
            form_three_id INTEGER,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE IF NOT EXISTS finances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            filing_date TEXT,
            filing_type TEXT NOT NULL,
            form_three_id INTEGER NOT NULL,
            estimated_cost REAL,
            incurred_and_paid REAL,
            booked_consideration REAL,
            received_amount REAL,
            balance_amount REAL,
            unbooked_consideration REAL,
            total_residential INTEGER DEFAULT 0,
            total_commercial_shop INTEGER DEFAULT 0,
            total_commercial_office INTEGER DEFAULT 0,
            loan_rows_count INTEGER DEFAULT 0,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE IF NOT EXISTS form5_compliance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            financial_year TEXT NOT NULL,
            status TEXT NOT NULL,
            submitted_on TEXT,
            doc_uid TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE IF NOT EXISTS noc_bu_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            block_name TEXT NOT NULL,
            bu_check TEXT,
            bu_date TEXT,
            fire_doc_id TEXT,
            lift_doc_id TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE IF NOT EXISTS previous_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            linked_project_name TEXT,
            linked_project_id INTEGER,
            linked_reg_no TEXT,
            completion_year TEXT,
            district_name TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            application_type TEXT NOT NULL,
            application_status TEXT,
            apply_date TEXT,
            approval_date TEXT,
            final_status TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE IF NOT EXISTS documents_catalog (
            uid_hash TEXT PRIMARY KEY,
            project_id INTEGER NOT NULL,
            doc_type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            raw_bytes INTEGER,
            sha256 TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE IF NOT EXISTS unit_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT DEFAULT 'default_run',
            project_id INTEGER NOT NULL,
            form_three_id INTEGER,
            block_name TEXT NOT NULL,
            unit_type TEXT,
            asset_class TEXT DEFAULT 'Residential',
            carpet_area_sqm REAL,
            carpet_area_sqft REAL,
            unit_consideration REAL,
            rate_per_sqft REAL,
            rate_per_sqm REAL,
            status TEXT NOT NULL,
            agreement_date TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE IF NOT EXISTS document_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL DEFAULT 'default_run',
            project_id INTEGER NOT NULL,
            uid_hash TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            file_path TEXT,
            sha256 TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            attempts INTEGER DEFAULT 0,
            max_attempts INTEGER DEFAULT 3,
            error_message TEXT,
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            completed_at_utc TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE IF NOT EXISTS market_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portal_source TEXT NOT NULL,
            external_id TEXT,
            project_name TEXT NOT NULL,
            promoter_name TEXT,
            locality TEXT,
            district TEXT,
            asking_rate_per_sqft REAL,
            carpet_area_sqft REAL,
            total_price_inr REAL,
            unit_type TEXT,
            asset_class TEXT DEFAULT 'Residential',
            latitude REAL,
            longitude REAL,
            matched_project_id INTEGER,
            match_confidence REAL,
            match_method TEXT,
            scraped_at_utc TEXT,
            FOREIGN KEY (matched_project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE IF NOT EXISTS copilot_embeddings (
            id TEXT PRIMARY KEY,
            project_id INTEGER NOT NULL,
            chunk_type TEXT NOT NULL,
            chunk_text TEXT NOT NULL,
            content_sha256 TEXT NOT NULL,
            embedding F16_BLOB(768),
            created_at TEXT NOT NULL
        );

        CREATE VIEW IF NOT EXISTS v_current_projects AS
        SELECT * FROM projects;

        CREATE VIEW IF NOT EXISTS v_current_unit_transactions AS
        SELECT * FROM unit_transactions;
    """)

    # Safe forward-migrations for existing tables BEFORE creating indexes on newly added columns
    cur = con.cursor()
    proj_cols = {r[1] for r in cur.execute("PRAGMA table_info(projects)").fetchall()}
    for col_name, col_def in [
        ("run_id", "TEXT DEFAULT 'default_run'"),
        ("tier", "TEXT DEFAULT 'statewide'"),
        ("has_deep_filings", "INTEGER DEFAULT 0"),
        ("has_bu_noc", "INTEGER DEFAULT 0"),
        ("bu_certificate_no", "TEXT"),
        ("project_status", "TEXT"),
        ("created_at_utc", "TEXT"),
        ("updated_at_utc", "TEXT"),
    ]:
        if col_name not in proj_cols:
            try:
                con.execute(f"ALTER TABLE projects ADD COLUMN {col_name} {col_def};")
            except Exception:
                pass

    unit_cols = {r[1] for r in cur.execute("PRAGMA table_info(unit_transactions)").fetchall()}
    if "run_id" not in unit_cols:
        try:
            con.execute("ALTER TABLE unit_transactions ADD COLUMN run_id TEXT DEFAULT 'default_run';")
        except Exception:
            pass
    if "asset_class" not in unit_cols:
        try:
            con.execute("ALTER TABLE unit_transactions ADD COLUMN asset_class TEXT DEFAULT 'Residential';")
        except Exception:
            pass

    app_cols = {r[1] for r in cur.execute("PRAGMA table_info(applications)").fetchall()}
    if "approval_date" not in app_cols:
        try:
            con.execute("ALTER TABLE applications ADD COLUMN approval_date TEXT;")
        except Exception:
            pass
    if "final_status" not in app_cols:
        try:
            con.execute("ALTER TABLE applications ADD COLUMN final_status TEXT;")
        except Exception:
            pass

    # Create indexes after columns are guaranteed to exist
    con.executescript("""
        CREATE INDEX IF NOT EXISTS idx_projects_tier ON projects(tier);
        CREATE INDEX IF NOT EXISTS idx_projects_district ON projects(district);
        CREATE INDEX IF NOT EXISTS idx_projects_reg_no ON projects(registration_number);
        CREATE INDEX IF NOT EXISTS idx_projects_run ON projects(run_id);

        CREATE INDEX IF NOT EXISTS idx_sum_district ON project_summaries(district);
        CREATE INDEX IF NOT EXISTS idx_sum_promoter ON project_summaries(promoter_name);
        CREATE INDEX IF NOT EXISTS idx_sum_type ON project_summaries(project_type);
        CREATE INDEX IF NOT EXISTS idx_sum_rate ON project_summaries(min_rate_sqft_booked);

        CREATE INDEX IF NOT EXISTS idx_prof_name ON professionals(name);
        CREATE INDEX IF NOT EXISTS idx_prof_project ON professionals(project_id);

        CREATE INDEX IF NOT EXISTS idx_banks_project_id ON banks(project_id);
        CREATE INDEX IF NOT EXISTS idx_fin_proj_date ON finances(project_id, filing_date);
        CREATE INDEX IF NOT EXISTS idx_noc_bu_project_id ON noc_bu_records(project_id);
        CREATE INDEX IF NOT EXISTS idx_app_proj_type ON applications(project_id, application_type);
        CREATE INDEX IF NOT EXISTS idx_doc_project ON documents_catalog(project_id);
        CREATE INDEX IF NOT EXISTS idx_doc_type ON documents_catalog(doc_type);

        CREATE INDEX IF NOT EXISTS idx_unit_proj ON unit_transactions(project_id);
        CREATE INDEX IF NOT EXISTS idx_unit_proj_block ON unit_transactions(project_id, block_name);
        CREATE INDEX IF NOT EXISTS idx_unit_proj_status ON unit_transactions(project_id, status);
        CREATE INDEX IF NOT EXISTS idx_unit_status_rates ON unit_transactions(project_id, status, unit_consideration, rate_per_sqft);
        CREATE INDEX IF NOT EXISTS idx_unit_asset_class ON unit_transactions(asset_class);
        CREATE INDEX IF NOT EXISTS idx_unit_run ON unit_transactions(run_id);

        CREATE INDEX IF NOT EXISTS idx_doc_jobs_status ON document_jobs(status);
        CREATE INDEX IF NOT EXISTS idx_doc_jobs_proj ON document_jobs(project_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_doc_jobs_run_uid ON document_jobs(run_id, uid_hash);

        CREATE INDEX IF NOT EXISTS idx_listing_proj ON market_listings(matched_project_id);
        CREATE INDEX IF NOT EXISTS idx_listing_portal ON market_listings(portal_source);

        CREATE INDEX IF NOT EXISTS idx_copilot_proj ON copilot_embeddings(project_id);
    """)

    # Vector index (LibSQL native vector support, safely caught if running vanilla sqlite3)
    try:
        con.execute("CREATE INDEX IF NOT EXISTS copilot_vector_idx ON copilot_embeddings(libsql_vector_idx(embedding));")
    except Exception:
        pass

    con.commit()
