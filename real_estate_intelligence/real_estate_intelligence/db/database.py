"""Curated SQLite database management with WAL mode and foreign key support."""

import sqlite3
from pathlib import Path
from typing import Optional, Union

from ..config import DEFAULT_DB_PATH


def get_connection(db_path: Optional[Union[Path, str, sqlite3.Connection]] = None) -> sqlite3.Connection:
    if isinstance(db_path, sqlite3.Connection):
        return db_path
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=30.0, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode = WAL;")
    con.execute("PRAGMA foreign_keys = ON;")
    con.execute("PRAGMA busy_timeout = 30000;")
    init_schema(con)
    return con


def init_schema(con: sqlite3.Connection) -> None:
    """Initialize structured relational tables."""
    con.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            project_id INTEGER PRIMARY KEY,
            run_id TEXT DEFAULT 'default_run',
            name TEXT NOT NULL,
            registration_number TEXT NOT NULL,
            promoter_id INTEGER NOT NULL,
            promoter_name TEXT NOT NULL,
            district TEXT,
            taluka TEXT,
            project_type TEXT,
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
            updated_at_utc TEXT
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
        CREATE INDEX IF NOT EXISTS idx_prof_name ON professionals(name);
        CREATE INDEX IF NOT EXISTS idx_prof_project ON professionals(project_id);

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
        CREATE INDEX IF NOT EXISTS idx_doc_project ON documents_catalog(project_id);
        CREATE INDEX IF NOT EXISTS idx_doc_type ON documents_catalog(doc_type);

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
        CREATE INDEX IF NOT EXISTS idx_unit_proj ON unit_transactions(project_id);
        CREATE INDEX IF NOT EXISTS idx_unit_block ON unit_transactions(project_id, block_name);
        CREATE INDEX IF NOT EXISTS idx_unit_status ON unit_transactions(project_id, status);

        -- Asynchronous Heavy Document Processing Queue
        CREATE TABLE IF NOT EXISTS document_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL DEFAULT 'default_run',
            project_id INTEGER NOT NULL,
            uid_hash TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            file_path TEXT,
            sha256 TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',  -- 'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'
            attempts INTEGER DEFAULT 0,
            max_attempts INTEGER DEFAULT 3,
            error_message TEXT,
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            completed_at_utc TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );
        CREATE INDEX IF NOT EXISTS idx_doc_jobs_status ON document_jobs(status);
        CREATE INDEX IF NOT EXISTS idx_doc_jobs_proj ON document_jobs(project_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_doc_jobs_run_uid ON document_jobs(run_id, uid_hash);

        -- External Market Listing Integration Seam (Data-Gated)
        CREATE TABLE IF NOT EXISTS market_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portal_source TEXT NOT NULL,       -- e.g. '99acres', 'MagicBricks', 'Housing'
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
            match_confidence REAL,             -- 0.0 to 1.0
            match_method TEXT,                 -- 'exact_name', 'spatial_token_hybrid', 'manual'
            scraped_at_utc TEXT,
            FOREIGN KEY (matched_project_id) REFERENCES projects(project_id)
        );
        CREATE INDEX IF NOT EXISTS idx_listing_proj ON market_listings(matched_project_id);
        CREATE INDEX IF NOT EXISTS idx_listing_portal ON market_listings(portal_source);

        -- Canonical Views
        CREATE VIEW IF NOT EXISTS v_current_projects AS
        SELECT * FROM projects;

        CREATE VIEW IF NOT EXISTS v_current_unit_transactions AS
        SELECT * FROM unit_transactions;
    """)

    # Safe forward-migrations for existing databases
    cur = con.cursor()
    proj_cols = {r[1] for r in cur.execute("PRAGMA table_info(projects)").fetchall()}
    if "run_id" not in proj_cols:
        con.execute("ALTER TABLE projects ADD COLUMN run_id TEXT DEFAULT 'default_run';")

    unit_cols = {r[1] for r in cur.execute("PRAGMA table_info(unit_transactions)").fetchall()}
    if "run_id" not in unit_cols:
        con.execute("ALTER TABLE unit_transactions ADD COLUMN run_id TEXT DEFAULT 'default_run';")
    if "asset_class" not in unit_cols:
        con.execute("ALTER TABLE unit_transactions ADD COLUMN asset_class TEXT DEFAULT 'Residential';")

    app_cols = {r[1] for r in cur.execute("PRAGMA table_info(applications)").fetchall()}
    if "approval_date" not in app_cols:
        con.execute("ALTER TABLE applications ADD COLUMN approval_date TEXT;")
    if "final_status" not in app_cols:
        con.execute("ALTER TABLE applications ADD COLUMN final_status TEXT;")

    con.execute("CREATE INDEX IF NOT EXISTS idx_unit_asset_class ON unit_transactions(asset_class);")
    con.execute("CREATE INDEX IF NOT EXISTS idx_projects_run ON projects(run_id);")
    con.execute("CREATE INDEX IF NOT EXISTS idx_unit_run ON unit_transactions(run_id);")

    con.commit()
