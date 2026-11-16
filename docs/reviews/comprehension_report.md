# EGM Comprehension Test Report: GujRERA Sovereign Platform Next Steps Plan

**Document Under Review:** `docs/PROPOSED_NEXT_STEPS_PLAN.md`  
**Reviewer:** EGM Comprehension Reviewer (Goldfish subagent)  
**Status:** Completed (Stage 6)

---

## 1. Feature Specification Paraphrase

### Scope & Context
The proposal targets the GujRERA Sovereign Platform (`real_estate_intelligence` package), a local intelligence system for Gujarat real estate regulatory data. The system currently runs as a prototype anchored by a small 9-project reference database (`intelligence.sqlite`), a local web UI dashboard, GBDT pricing and survival delay prediction models, and an evaluation suite.

### Problems It Aims to Solve
1. **Repository Drift and Workspace Clutter:** The local repository on `main` lags 5 commits behind `origin/main` (`e8da240`), retains an untracked, obsolete directory (`staging_from_pipeline/`), and is linked to an external git worktree left over from a previous refactoring branch.
2. **Backend-to-Frontend Feature Disconnect:** Statutory audit capabilities (checking architect, structural engineer, and Chartered Accountant Form 3 credentials) and escrow cash runway calculations exist in backend Python modules and pass unit tests on `origin/main`, but have no UI display in the web dashboard.
3. **Data Scaling Bottleneck:** The upstream crawling pipeline contains a large dataset (58,741 Form 3 filings across 17,632 projects), but the platform only runs on 9 projects. Ingesting the full dataset at once would degrade the prototype's sub-50ms query response times and overwhelm the single-page client.

### Target Goals
* Reconcile local git state cleanly with `origin/main` using fast-forward only.
* Display professional credential validation badges (architect, structural engineer, Form 3 CA) in the Project Detail UI view.
* Display Escrow Cash Burn Rate and Runway status alongside project KPIs in the UI.
* Implement a partitioned, district-level ingestion pipeline to load a ~1,500-project slice (Ahmedabad) from Parquet files into SQLite.
* Retain 100% pass rates on unit tests and the 4-component benchmark (`run_server.py eval`).

### Explicit Non-Goals
* Statewide ingestion of all 17,632 projects (postponed until server-side pagination and spatial clustering are built).
* Frontend framework migrations (no React, Vue, or build tooling; remains vanilla HTML/JS served by Python's `ThreadingHTTPServer`).
* Alterations to the upstream crawling scripts in `gujrera-pipeline`.

### System Invariants
* SQLite database writes are restricted exclusively to ingestion scripts and batch workers; the UI server and MCP tools remain strictly read-only.
* Privacy redaction must ensure no personal Aadhaar, PAN, or KYC data is exposed in UI payloads.
* Escrow account semantics are fixed: Account Type 1 is the 70% statutory retention escrow; Account Type 2 is the 100% collection account.

---

## 2. Implementation Plan Paraphrase

### Step-by-Step Execution Sequence
1. **Step 1: Git Hygiene and Branch Reconciliation**
   * Check tracked files for uncommitted changes using `git status --porcelain`.
   * Delete the untracked directory `real_estate_intelligence/staging_from_pipeline/`.
   * Fast-forward local `main` to `origin/main` (`git pull --ff-only origin main`).
   * Delete the external worktree and run `git worktree prune`.
   * Delete the local branch `cleanup_pipeline_files`.
   * *Verification:* Clean `git status`, HEAD at `e8da240`, and test suite passes.

2. **Step 2: UI Exposure of Credentials and Escrow Metrics**
   * *Backend:* Update `/api/project/{pid}` in `ui/server.py` to append outputs from `ProjectAuditor.audit_credential_coverage` and `calculate_escrow_runway`.
   * *Frontend:* Update `ui/static/index.html` to add a "Statutory Credentials & Governance" card with verification status badges for the Architect, Structural Engineer, and Form 3 CA certificate, plus a badge showing monthly escrow burn and runway months.
   * *Testing:* Add an assertion to `tests/test_ui_server.py` checking that project `13560` returns `credential_coverage` and `escrow_runway` fields.
   * *Verification:* Run `test_ui_server.py` and query `/api/project/13560` directly.

3. **Step 3: District Ingestion Slice (Ahmedabad)**
   * Create `real_estate_intelligence/scripts/ingest_district_slice.py` using DuckDB/PyArrow to filter Parquet filings for `district = 'Ahmedabad'`.
   * Upsert the parsed data into `projects`, `quarterly_timeline`, and `unit_transactions` tables.
   * Update FTS5 search index entries for the newly inserted records.
   * *Verification:* Ingestion runs without unhandled exceptions; `/api/explore` responds in under 50 ms; `/api/search` responds in under 100 ms; and `run_server.py eval` confirms valuation and survival analysis remain operational without regression.

---

## 3. Comprehension Findings & Ambiguities

### A. Missing Definitions & Unexplained Jargon
1. **"Form 3 Parquet lake":** The document never defines what a "Form 3" filing is. In RERA statutory framework, Form 3 is a Chartered Accountant certificate verifying project costs and escrow withdrawal eligibility. Without this context, an outside engineer cannot know what data fields these 58,741 files contain or why CA verification is bound to Form 3.
2. **"Harrell C-index = 1.0 survival delay model":** The document mentions this metric and model as an existing capability and requires that `run_server.py eval` maintains accuracy after ingestion. However, it does not explain whether ingesting 1,500 new projects retrains this model, evaluates against new data, or only tests the static 9-project baseline.
3. **"10-case evidentiary agent":** Mentioned in Section 1 as part of the system overview, but never defined. It is unclear whether this is an LLM agent, a rules engine, an MCP client, or part of `eval_harness.py`.
4. **Target Project ID `13560`:** Step 2 specifies adding a test for `/api/project/13560`. The document does not clarify why this specific ID is used, whether it exists in the 9-project deep sample, or whether it has the requisite credential and escrow records populated to test both verified and unverified states.
5. **Function Call Signature Error:** Step 2 (line 61) directs the engineer to call `calculate_escrow_runway(con, pid)`. In the actual codebase (`analytics/audit.py`), `calculate_escrow_runway` is an instance method on `ProjectAuditor` that accepts only `project_id` (`self.auditor.calculate_escrow_runway(pid)`). Calling it as a standalone function with `(con, pid)` will cause an immediate `NameError` or `TypeError`.
6. **Escrow Account Type Schema Context:** Section 2.3 notes that Account Type `1` is the 70% retention escrow and `2` is the 100% collection account. It omits the table and column name where this invariant lives (specifically `banks.account_type`).

### B. Unclear Operational Sequences & Hidden Assumptions
1. **Hardcoded User Path in Git Commands:** Step 1 (line 50) specifies an absolute Windows file path: `C:/Users/adars/.gemini/antigravity/worktrees/gujRERA/cleanup_pipeline_files`. This command will fail for any other engineer or CI environment. Git worktree commands should use dynamic worktree discovery (`git worktree list`) or relative paths.
2. **Missing Parquet Lake Source Path:** Step 3 (line 79) instructs the script to read `data/filings/*/*.parquet`. This directory does not exist in the repository root or inside `real_estate_intelligence`. The problem statement references an external "private pipeline" (`../gujrera_pipeline`), but the plan does not state how the Parquet files reach `data/filings/`, whether they need to be copied, symlinked, or passed via a `--data-dir` CLI argument.
3. **Pre-condition Failure on Local Working Copy:** Step 1 requires verifying zero uncommitted modifications via `git status --porcelain`. In the active workspace, `real_estate_intelligence/data/intelligence.sqlite` is already tracked and modified. Running `git status --porcelain` fails this gate immediately. The document gives no guidance on whether to revert (`git restore`), stash, or inspect changes to `intelligence.sqlite` before pulling.
4. **Data Mapping Mismatch for `unit_transactions`:** Step 3 states that reading Form 3 Parquet files will populate `projects`, `quarterly_timeline`, and `unit_transactions`. Form 3 filings are financial cost certificates; they do not contain individual unit sales, floor layouts, or unit transaction logs. The document assumes either that Form 3 contains unit transactions or that other unmentioned Parquet files are being ingested.
5. **Incremental FTS5 Indexing Mechanism:** Step 3 specifies building FTS5 entries "strictly for newly ingested documents." It does not define how new documents are identified (e.g. SQLite rowid ranges, inserted timestamp triggers, or an upsert merge) to prevent duplicate FTS index entries.

### C. Disconnects Between Feature Specification (Goals) and Implementation Plan
1. **Generic District Architecture vs. Hardcoded Script:** Goal 2.1 calls for designing a "partitioned, district-level ingestion mechanism." In contrast, Step 3 specifies a one-off script `ingest_district_slice.py` hardcoding `district = 'Ahmedabad'`. It does not design a reusable, parameterized CLI command (e.g. `--district <name>`) or partition manifest.
2. **Privacy Redaction Invariant vs. Unsanitized Payload:** Invariant 2.3 mandates that no Aadhaar, PAN, or personal KYC records are exposed in UI payloads. Step 2 dumps the dictionary returned by `audit_credential_coverage` directly into the `/api/project/{pid}` response without specifying what fields `audit_credential_coverage` contains or mandating a sanitization/whitelisting step before sending JSON to the browser.
3. **Credential Coverage Missing from Ingested Slice:** Step 2 builds UI cards for architect and structural engineer credentials. Step 3 ingests only Form 3 filings. If Form 3 data lacks architect and engineer license details, all 1,500 newly ingested Ahmedabad projects will display empty or failing credential badges in the UI.

### D. Undefined Failure Modes & Rollback Procedures
1. **No SQLite Backup Procedure:** Ingesting 1,500 projects into `intelligence.sqlite` modifies table structures, row counts, and indexes. If the script crashes mid-stream, corrupts foreign keys, or breaches the 50ms latency ceiling, there is no documented backup or rollback command (e.g. snapshotting `intelligence.sqlite.bak` prior to execution).
2. **Vague Error Table Specification:** Risk 3 states that malformed records will be logged to "an error table." The plan does not state whether this table already exists in `intelligence.sqlite`, what its schema is, or what happens if the script aborts mid-transaction.
3. **No Remedy for Latency Degradation:** If `/api/explore` exceeds 50 ms or `/api/search` exceeds 100 ms after ingesting the Ahmedabad slice, the plan offers no corrective path (e.g. whether to add covering indexes, revert the database, or implement server-side pagination).
4. **Git Conflict Fallback:** The plan assumes `git pull --ff-only` will succeed cleanly once tracked files are clean. If local branch `main` has commit divergences from `origin/main`, `--ff-only` will abort, leaving the engineer with no documented recovery path.
