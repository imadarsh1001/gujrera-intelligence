# EGM Implementation Readiness Review Report: Detailed Implementation Plan

**Target Document:** `docs/PROPOSED_NEXT_STEPS_PLAN.md`  
**Review Scope:** `DetailedRange` (Lines 42..107: Detailed Implementation Plan, Steps 1, 2, 3, Risk Analysis, Review Criteria)  
**Reviewer:** EGM Implementation Readiness Reviewer (Goldfish Subagent)  
**Status:** Completed (Stage 9)  
**Baseline Contracts:** Root `EGM.md`, `real_estate_intelligence/EGM.md`  
**Overall Verdict:** **REJECT — NOT IMPLEMENTATION READY (5 Blockers, 5 Majors, 4 Nits)**

---

## Executive Summary

A line-by-line, code-level implementation readiness audit of `docs/PROPOSED_NEXT_STEPS_PLAN.md` (Lines 42..107) reveals that **an engineer attempting to execute this plan sequentially will fail at every single step**. 

The plan contains critical code-level defects, invalid file paths, syntax/signature errors, ungrounded DOM targets, SQLite constraint violations, and architectural impossibilities:
1. **Step 1 Aborts on Execution:** Step 1 asserts that zero uncommitted changes exist, but the workspace currently has an uncommitted modification to a tracked binary file (`real_estate_intelligence/data/intelligence.sqlite`). Because commit `73c8639` on `origin/main` also touched this binary file, running `git pull --ff-only` will immediately abort. Furthermore, the test runner command prescribed (`python -m unittest discover -s real_estate_intelligence/tests ...`) fails with an `ImportError`.
2. **Step 2 Calls Invalid Python and Targets Nonexistent DOM Elements:** The backend instructions invoke `calculate_escrow_runway(con, pid)` as a standalone function; in `real_estate_intelligence/analytics/audit.py:298`, it is an instance method requiring `self.auditor.calculate_escrow_runway(pid)`. In the frontend, the plan instructs placing cards in a nonexistent "Project Detail tab" without specifying element IDs or updating the `loadProject` JavaScript controller.
3. **Step 3 Triggers a Cascading System Crash:**
   - **Environment Barrier:** Mandates `DuckDB` and `PyArrow`, which are not in `pyproject.toml` and are actively blocked by Windows Application Control (WDAC) on the host.
   - **Path Hallucination:** Mandates reading `data/filings/*/*.parquet`, which does not exist anywhere in the repository.
   - **Database Constraint Violations:** Form 3 filings lack master project registration fields (`name`, `registration_number`, `promoter_id`, `promoter_name`), which will trigger immediate SQLite `NOT NULL` constraint violations on `projects`.
   - **Query Engine Collapse:** Ingesting 1,500 projects triggers an unpaginated $O(N)$ query storm in `_explore_rows()` (**6,001 synchronous queries per request**), making the sub-50ms latency gate physically impossible, while Vis.js freezes under 10,000+ nodes.
   - **Evaluation Harness Invalidation:** Training survival and pricing models on 1,500 unvalidated, partial records will degrade the Harrell C-index and pricing RMSE thresholds in `eval_harness.py`.

The plan completely lacks error handling, database backups, rollback procedures, and environment isolation.

---

## 1. Codebase Details Audit (`egm-codebase-details`)

### 1.1 Inaccurate File Paths
The implementation plan omits the inner package namespace directory across all Step 2 and Step 3 paths:
* **Line 60:** Cites `real_estate_intelligence/ui/server.py`.  
  *Actual Codebase Path:* `real_estate_intelligence/real_estate_intelligence/ui/server.py`.
* **Line 62:** Cites `real_estate_intelligence/ui/static/index.html`.  
  *Actual Codebase Path:* `real_estate_intelligence/real_estate_intelligence/ui/static/index.html`.
* **Line 78:** Cites `real_estate_intelligence/scripts/ingest_district_slice.py`.  
  *Actual Codebase Path:* Should be `real_estate_intelligence/scripts/ingest_district_slice.py` (scripts folder) or inside the package under `real_estate_intelligence/real_estate_intelligence/db/`.
* **Line 79:** Cites `data/filings/*/*.parquet`.  
  *Actual Codebase Path:* Nonexistent. The pipeline data lake resides in the sibling repository at `../gujrera_pipeline/data/form3/2026-11-13/form3_ahmedabad.parquet`.

### 1.2 Function Signature & Method Invocation Mismatches (Step 2, Line 61)
* **The Error:** Line 61 directs the engineer to include:  
  `ProjectAuditor(con).audit_credential_coverage(pid)` and `calculate_escrow_runway(con, pid)`.
* **Actual Codebase Implementation:**
  1. In `real_estate_intelligence/analytics/audit.py:298-305`:
     ```python
     class ProjectAuditor:
         def __init__(self, con: sqlite3.Connection):
             self.con = con
         ...
         def calculate_escrow_runway(self, project_id: int) -> dict:
     ```
     `calculate_escrow_runway` is an **instance method** of `ProjectAuditor` that accepts only `project_id: int`. Calling `calculate_escrow_runway(con, pid)` as a standalone function raises `NameError: name 'calculate_escrow_runway' is not defined`.
  2. In `real_estate_intelligence/real_estate_intelligence/ui/server.py:128-139`:
     ```python
     @classmethod
     def setup_backends(cls, db_path=None):
         cls.con = get_connection(db_path)
         ...
         cls.auditor = ProjectAuditor(cls.con)
     ```
     `self.auditor` is already instantiated on the request handler. Instantiating `ProjectAuditor(con)` manually inside the route handler is redundant and references an unbound variable `con` (the handler uses `self.con`).
  3. **Correct Call Pattern:**
     ```python
     "credential_coverage": self.auditor.audit_credential_coverage(pid),
     "escrow_runway": self.auditor.calculate_escrow_runway(pid),
     ```

### 1.3 UI DOM Structure & Template Mismatch (Step 2, Lines 62–68)
* **The Error:** Line 63 directs adding a card to the "Project Detail tab".
* **Actual Codebase Implementation:**
  - `index.html` has no tab named "Project Detail". The 9 tabs in `index.html:108-117` are:
    1. `tab-explore` (`content-explore` / Explore Projects)
    2. `tab-compare` (`content-compare` / Shortlist & Compare)
    3. `tab-dossier` (`content-dossier` / Executive 4-Quadrant)
    4. `tab-pricing` (`content-pricing` / Unit Pricing)
    5. `tab-analytics` (`content-analytics` / Quantitative ML & Curves)
    6. `tab-claims` (`content-claims` / Claim Fact-Checker)
    7. `tab-discrepancies` (`content-discrepancies` / Audit Discrepancies)
    8. `tab-graph` (`content-graph` / Knowledge Graph)
    9. `tab-vault` (`content-vault` / Document Vault)
    10. `tab-search` (`content-search` / Document Search)
  - Detailed project information is hosted in `content-dossier` (Executive 4-Quadrant Analysis), with top-level KPI metrics displayed in `#projectBanner` (`kpiBooking`, `kpiProgress`, `kpiVelocity`, `kpiEscrowBal`, `kpiDeadline`).
  - The plan specifies zero DOM element IDs for the new badges, and fails to instruct updating `loadProject(pid)` (lines 980-1110 in `index.html`), which binds API JSON data to DOM elements.

### 1.4 Step 1 Git State & Test Runner Verification (Lines 47, 50, 55)
* **Dirty Tracked Binary:** Line 47 requires verifying that zero uncommitted modifications exist. In reality, `git status --porcelain` outputs:  
  ` M real_estate_intelligence/data/intelligence.sqlite`.  
  Because commit `73c8639` on `origin/main` also modifies `intelligence.sqlite`, executing `git pull --ff-only origin main` (Line 49) aborts with:  
  `error: Your local changes to the following files would be overwritten by merge`.
* **Hardcoded Machine Path:** Line 50 mandates `git worktree remove "C:/Users/adars/.gemini/antigravity/worktrees/gujRERA/cleanup_pipeline_files"`. This absolute path is specific to a single local machine and environment; it is invalid on any other workstation or CI.
* **Broken Unittest Command:** Line 55 instructs running:  
  `python -m unittest discover -s real_estate_intelligence/tests -p "test_*.py"`.  
  When run from the repo root, Python fails with:  
  `ImportError: Start directory is not importable: '...real_estate_intelligence/tests'`.  
  The command requires `-t .` or `-t real_estate_intelligence`, or using pytest as specified in `EGM.md` (`python -m pytest real_estate_intelligence/tests`).

### 1.5 Step 3 Parquet Schema & SQL Constraint Violations (Lines 79–81)
* **SQLite NOT NULL Constraint Crash:** Line 80 instructs: *"Upsert projects into projects, quarterly filings into quarterly_timeline, and unit transactions into unit_transactions."*  
  In `real_estate_intelligence/db/database.py:27-40`, the `projects` table defines:
  ```sql
  name TEXT NOT NULL,
  registration_number TEXT NOT NULL,
  promoter_id INTEGER NOT NULL,
  promoter_name TEXT NOT NULL,
  ```
  Form 3 Parquet filings are CA cost certificates containing financial expenditure totals and unit counts. They do NOT contain `registration_number`, `promoter_id`, or `promoter_name`. Attempting to insert into `projects` directly from Form 3 Parquet files triggers:  
  `sqlite3.IntegrityError: NOT NULL constraint failed: projects.registration_number`.
* **Foreign Key Violations:** `database.py:18` enforces `PRAGMA foreign_keys = ON;`. In `quarterly_timeline` and `unit_transactions`, `FOREIGN KEY (project_id) REFERENCES projects(project_id)` is strictly enforced. If `projects` cannot be populated first, inserts into child tables will crash with foreign key errors.
* **Unit Transactions Mismatch:** Form 3 filings do not contain granular per-unit transaction logs (`carpet_area_sqft`, `unit_consideration`, `rate_per_sqft`, `agreement_date`). Expecting to populate `unit_transactions` from Form 3 Parquet files is a data mapping impossibility.
* **FTS5 Indexing Hallucination:** Line 81 requires building FTS5 index entries for newly ingested documents. Form 3 Parquet files contain zero document text or PDFs. Full PDFs exist strictly for the 9 seed benchmark projects in `gujrera_pipeline/data/samples/`.

### 1.6 False Claim of Read-Only SQLite (`mode=ro`) (Line 97)
* Table 4 claims: *"UI connections open with `mode=ro` and `timeout=30.0`."*
* In `real_estate_intelligence/real_estate_intelligence/ui/server.py:130` and `db/database.py:10-21`, `IntelligenceRequestHandler.setup_backends()` calls `get_connection()`, which connects in read-write mode, executes `PRAGMA journal_mode = WAL;`, and runs DDL schema migrations via `init_schema()`.
* If a true `mode=ro` connection were opened today, the server would immediately throw `sqlite3.OperationalError: attempt to write a readonly database`.

---

## 2. Implementation Readiness Evaluation (`egm-implementation-readiness`)

### 2.1 Can an Engineer Blindly Follow These Instructions and Succeed?
**NO.** The workflow halts at multiple gates:
1. **At Step 1, Action 1 & 3:** Fails on tracked `intelligence.sqlite` dirty state.
2. **At Step 1, Action 4:** Fails if the user or CI path does not match `C:/Users/adars/...`.
3. **At Step 1, Verification Gate:** Fails with `ImportError: Start directory is not importable`.
4. **At Step 2, Action 1:** Fails with `NameError: name 'calculate_escrow_runway' is not defined`.
5. **At Step 2, Action 2:** Engineer cannot locate the "Project Detail tab" in `index.html`.
6. **At Step 3, Action 1:** Fails with `ModuleNotFoundError: No module named 'duckdb'` / WDAC C-extension block, followed by `FileNotFoundError` on `data/filings/*/*.parquet`, followed by SQLite `NOT NULL constraint failed`.
7. **At Step 3, Action 2:** Fails the $<50\text{ ms}$ latency benchmark due to the 6,001-query cascade in `_explore_rows`.
8. **At Step 3, Verification Gate:** Fails `run_server.py eval` due to survival model C-index and pricing RMSE degradation.

### 2.2 Error Recovery, Fallbacks, and Rollbacks
* **Database Backup:** The plan provides **zero instructions** for snapshotting `intelligence.sqlite` prior to executing the 1,500-project ingestion in Step 3. If the script corrupts the database or fails midway, the developer has no recovery path other than a destructive full rebuild.
* **Undefined "Error Table":** Risk 3 states that malformed records will be logged to "an error table." The plan does not specify table name, schema, database destination, or cleanup policy.
* **Latency Degradation Fallback:** If `/api/explore` exceeds 50 ms or `/api/search` exceeds 100 ms, no remediation path (e.g. indexing, query rewrite, rollback) is defined.

### 2.3 Verification Gates Rigor & Repeatability
* **Gate 1 (Test Suite):** The test runner command is broken.
* **Gate 2 (REST API):** Does not define expected HTTP status codes or assertions for unassigned/unverified credential states.
* **Gate 3 (Explore Latency & Eval):** Contradicted by codebase reality:
  - `ui/server.py:476-569` (`_explore_rows`) runs **4 sequential SQL queries per project in a Python loop**:
    1. `SELECT filing_date FROM finances ...`
    2. `SELECT apply_date FROM applications ...`
    3. `SELECT unit_type, unit_consideration, rate_per_sqft, agreement_date FROM unit_transactions ...`
    4. `SELECT name FROM professionals WHERE role = 'architect' ...`
  - For 1,500 projects, this executes $1 + (1500 \times 4) = \mathbf{6,001\text{ synchronous SQL queries}}$ per request. Sub-50ms latency is physically unattainable.
  - `tests/eval_harness.py:90-124` loops through all projects in `projects` to evaluate survival models. Ingesting 1,500 partial projects without BU records will drop the C-index below the hardcoded 0.75 threshold.

---

## 3. Prioritized Findings Matrix

| Finding ID | Severity | Line Citations | Discrepancy & Impact | Drop-In Replacement Text |
|---|---|---|---|---|
| **IMP-01** | **Blocker** | Lines 47, 49 | Tracked binary `intelligence.sqlite` is modified locally and in upstream commit `73c8639`. `git pull --ff-only` will fail immediately. | Add explicit pre-pull discard: `git checkout HEAD -- real_estate_intelligence/data/intelligence.sqlite` followed by `git pull --ff-only origin main`. |
| **IMP-02** | **Blocker** | Line 61 | Invokes `calculate_escrow_runway(con, pid)` as a standalone function. In `audit.py:298`, it is an instance method of `ProjectAuditor`. | Replace with `self.auditor.calculate_escrow_runway(pid)` and `self.auditor.audit_credential_coverage(pid)`. |
| **IMP-03** | **Blocker** | Lines 79–80 | Parquet filings lack master project fields (`registration_number`, `promoter_id`, `promoter_name`), causing SQLite `NOT NULL` constraint violations on `projects`. | Sever Step 3 from the immediate implementation plan. Ingestion requires a joined multi-table pipeline in a dedicated RFC. |
| **IMP-04** | **Blocker** | Line 79 | Host Windows Defender Application Control (WDAC) blocks DuckDB and PyArrow C-extensions (`_duckdb.pyd`, `_fs.pyd`). Packages not in `pyproject.toml`. | Quarantine analytical ETL dependencies to an optional extras specification or execute conversion out-of-band via pure Python. |
| **IMP-05** | **Blocker** | Lines 84, 89 | `_explore_rows` executes 6,001 synchronous queries per request for 1,500 projects ($O(N)$ N+1 loop). Destroys $<50\text{ ms}$ latency target and breaks `eval_harness.py`. | Quarantine slice ingestion to an isolated database (`ahmedabad_benchmark.sqlite`). Rewrite `_explore_rows` to a single SQL query before UI ingestion. |
| **IMP-06** | **Major** | Lines 60, 62 | Paths omit inner package directory: cites `real_estate_intelligence/ui/...` instead of `real_estate_intelligence/real_estate_intelligence/ui/...`. | Update paths to `real_estate_intelligence/real_estate_intelligence/ui/server.py` and `.../static/index.html`. |
| **IMP-07** | **Major** | Lines 63–68 | Targets nonexistent "Project Detail tab". Omits DOM element IDs and JavaScript binding updates in `loadProject()`. | Specify exact DOM containers: Quadrant 1 in `content-dossier` for Governance card and `#projectBanner` for Escrow Runway badge, with explicit DOM IDs. |
| **IMP-08** | **Major** | Line 50 | Hardcoded absolute Windows user path `C:/Users/adars/...` in git worktree command. | Use dynamic resolution: `git worktree list` and pass discovered worktree path to `git worktree remove --force`. |
| **IMP-09** | **Major** | Line 55 | Test discovery command fails with `ImportError: Start directory is not importable`. | Replace with: `python -m unittest discover -s real_estate_intelligence/tests -t real_estate_intelligence -p "test_*.py"` or pytest. |
| **IMP-10** | **Major** | Lines 36, 97 | Claims UI server opens with `mode=ro`. In reality, `server.py` connects read-write and runs DDL migrations. | Document true connection semantics and create `get_ro_connection()` using SQLite URI `mode=ro`. |
| **IMP-11** | **Nit** | Line 79 | Path `data/filings/*/*.parquet` does not exist; actual pipeline lake is at `../gujrera_pipeline/data/form3/<date>/form3_<district>.parquet`. | Correct lake reference to `../gujrera_pipeline/data/form3/2026-11-13/form3_ahmedabad.parquet`. |
| **IMP-12** | **Nit** | Line 81 | Form 3 Parquet files contain no document text or PDFs for FTS5 indexing. | Remove FTS5 indexing requirement from Form 3 Parquet ingestion. |
| **IMP-13** | **Nit** | Line 70 | Test checks project `13560` but does not specify schema assertions for unverified states. | Specify assertions for both verified (`13560`) and unverified/edge-case projects. |
| **IMP-14** | **Nit** | Lines 95–99 | Risk table claims malformed rows log to "an error table" without defining schema or table name. | Define exact table DDL (`CREATE TABLE IF NOT EXISTS ingestion_errors (...)`). |

---

## 4. Proposed Drop-In Replacement Text for Detailed Implementation Plan

```markdown
## Detailed Implementation Plan (Milestone 1: VCS Reconciliation & UI Credential Surfacing)

### Step 1: Git Reconciliation & Worktree Pruning
* **Objective:** Cleanly fast-forward local `main` to `origin/main` (`e8da240`), eliminate the orphaned staging folder, and safely remove the secondary git worktree without merge conflicts.
* **Pre-Execution Check:**
  1. Inspect working tree: `git status --porcelain`.
  2. Discard uncommitted mutations to the tracked binary database:
     `git checkout HEAD -- real_estate_intelligence/data/intelligence.sqlite`
* **Actions:**
  1. Remove the obsolete untracked staging directory:
     PowerShell: `Remove-Item -Recurse -Force "real_estate_intelligence/staging_from_pipeline"`
     POSIX: `rm -rf real_estate_intelligence/staging_from_pipeline`
  2. Fast-forward local `main` to remote:
     `git pull --ff-only origin main`
  3. Discover and prune the secondary worktree:
     Run `git worktree list`. Identify the worktree linked to branch `cleanup_pipeline_files`.
     Execute: `git worktree remove --force "<worktree_path>"`
     Execute: `git worktree prune`
  4. Delete the local tracking branch:
     `git branch -d cleanup_pipeline_files`
* **Verification Gate:**
  * `git status` reports clean working tree on branch `main` (untracked review docs excepted).
  * `git log -1 --oneline` outputs `e8da240 docs: retire staging_from_pipeline references from root blueprint and README`.
  * Run test suite from repository root:
    `python -m unittest discover -s real_estate_intelligence/tests -t real_estate_intelligence -p "test_*.py"`
    (Reports `Ran 49 tests in ...s - OK`).

---

### Step 2: Surface Credential & Statutory Signer Coverage in Web UI
* **Objective:** Expose statutory signer credentials (`audit_credential_coverage`) and cash burn runway (`calculate_escrow_runway`) in the Web UI dashboard for the 9 curated benchmark projects.
* **Actions:**
  1. **Backend Route Augmentation (`real_estate_intelligence/real_estate_intelligence/ui/server.py`):**
     * In `IntelligenceRequestHandler.do_GET`, locate the `/api/project/` route (lines 199–265).
     * Append the verified analytics payloads using the pre-initialized `self.auditor` instance:
       ```python
       "credential_coverage": self.auditor.audit_credential_coverage(pid),
       "escrow_runway": self.auditor.calculate_escrow_runway(pid),
       ```
     * Enforce privacy redaction invariant: ensure `credential_coverage` returns only whitelisted professional metadata (`name`, `firm`, `license_or_reg_no`, `observed_count`, `verified_count`, `gap_codes`) and zero PAN/Aadhaar identifiers.
  2. **UI Template Integration (`real_estate_intelligence/real_estate_intelligence/ui/static/index.html`):**
     * **Executive 4-Quadrant (Quadrant 1 - Statutory & Escrow):**
       Inside `#content-dossier`, add a "Statutory Professional Credentials" governance card (`#cardGovernanceCredentials`):
       - Architect verification status badge (`#badgeArchitectStatus`)
       - Structural Engineer verification status badge (`#badgeEngineerStatus`)
       - Form 3 CA Certificate archival status badge (`#badgeForm3CAStatus`)
       - Unresolved observation / gap codes warning container (`#containerCredentialGaps`)
     * **Project Header KPI Banner (`#projectBanner`):**
       Add an Escrow Cash Runway indicator badge (`#kpiEscrowRunway`):
       - Displays estimated runway months (`estimated_runway_months`) and monthly construction spend velocity (`monthly_construction_burn_inr`).
       - Color-codes risk severity: Red (< 3 months, Critical), Amber (< 6 months, Moderate), Green (>= 6 months, Low).
     * **Frontend Controller (`loadProject` in `index.html`):**
       Update `loadProject(pid)` around line 1005 to parse `data.credential_coverage` and `data.escrow_runway`, updating the badge text and Tailwind CSS classes dynamically.
  3. **Regression Guard & Unit Testing:**
     * Extend `real_estate_intelligence/tests/test_ui_server.py`:
       Add `test_project_endpoint_credential_and_runway_keys()` asserting that querying `/api/project/13560` returns status 200 with dictionary keys `credential_coverage` and `escrow_runway` matching expected schema types.
* **Verification Gate:**
  * Run `python -m unittest real_estate_intelligence/tests/test_ui_server.py` (100% pass).
  * Launch server `python run_server.py` and probe `http://127.0.0.1:8765/api/project/13560` using curl, verifying `roles.architect.verified_count` and `estimated_runway_months` are populated.

---

## Future Architectural Track (Milestone 2: Lake Ingestion & Query Optimization RFC)

*Note: Ingesting the ~1,500-project Ahmedabad district slice from Form 3 Parquet files into the active UI database is strictly deferred to a dedicated RFC to prevent system degradation.*

### Prerequisites to be Addressed in RFC-0001:
1. **Host Security Architecture (WDAC):**
   - Provide an ingestion mechanism compatible with host WDAC policies that block DuckDB/PyArrow C-extensions (e.g. pure-Python parquet parser or standalone out-of-band SQLite generator).
2. **Relational Schema Joining:**
   - Resolve missing `projects` NOT NULL constraints by joining `form3_ahmedabad.parquet` with `all_projects_ahmedabad.parquet` and `governance_ahmedabad.parquet` before database loading.
3. **Database Isolation:**
   - Ingest district slices into a dedicated benchmark database (`real_estate_intelligence/data/ahmedabad_benchmark.sqlite`), preserving `intelligence.sqlite` as the pristine 9-project reference baseline for `eval_harness.py`.
4. **Query Engine Optimization ($O(N) \to O(1)$):**
   - Refactor `ui/server.py:_explore_rows` from its current 4-query-per-project loop into a single SQL query using `GROUP BY` and window aggregations, eliminating the 6,001-query bottleneck.
5. **UI Virtualization & Subgraph Scoping:**
   - Implement server-side pagination (`LIMIT`/`OFFSET`) on `/api/explore`.
   - Scope `/api/graph` to return project ego networks rather than full-database node dumps (preventing Vis.js 10,000-node browser freezes).

---

## 4. Risk Analysis & Contingency Plans

| Risk | Impact | Mitigation & Recovery |
|---|---|---|
| Tracked `intelligence.sqlite` binary conflict during pull | `git pull --ff-only` aborts | Discard local binary changes before pull via `git checkout HEAD -- real_estate_intelligence/data/intelligence.sqlite`. |
| Credential audit returns false positive "missing" for early-stage schemes | Unwarranted HIGH severity flags shown in UI | `ProjectAuditor` checks `incurred_cost_inr > 0` before requiring signed Form 3 CA certs (verified in `test_early_stage_project_no_false_positive_form3`). |
| Accidental mutation of baseline SQLite database | Evaluation harness benchmarks fail | Maintain snapshot `intelligence.sqlite.bak` prior to testing; run UI server with read-only connection helper (`get_ro_connection`). |
| Redaction leak of PII via API | Privacy invariant breach | Enforce strict key whitelisting in `/api/project/{pid}` payload serializer before dispatching JSON. |

---

## 5. Review Criteria & Deliverables

1. Does the implementation order guarantee zero git merge conflicts by resolving tracked binary drift prior to pulling?
2. Does the credential UI addition strictly preserve the read-only boundary of the server and avoid leaking unredacted PII?
3. Are UI components grounded in actual `index.html` tab containers (`content-dossier` Quadrant 1 and `#projectBanner`)?
4. Is large-scale Parquet lake ingestion properly isolated into a separate architectural RFC to prevent query storms and browser freezes?
```
