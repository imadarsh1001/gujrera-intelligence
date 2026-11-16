# EGM Zoom-Out Review: GujRERA Sovereign Platform Next Steps Plan

**Document Under Review:** `docs/PROPOSED_NEXT_STEPS_PLAN.md`  
**Reviewer:** EGM Zoom-Out Reviewer (Goldfish subagent)  
**Standard:** Plain-English, zero sycophancy, direct critique first  
**Status:** Completed (Stage 5)

---

## Executive Summary & Verdict

**Verdict: REJECT / MAJOR REVISION REQUIRED.**

The proposed plan presents a superficially orderly three-step progression (Git sync -> UI exposure -> Ingestion) that breaks down immediately upon inspection of the codebase and execution environment:

1. **Step 1 will fail at line 1**: The working tree contains a modified, git-tracked binary file (`real_estate_intelligence/data/intelligence.sqlite`), which was also modified in commit `73c8639` on `origin/main`. `git pull --ff-only` will abort.
2. **Step 2 invents nonexistent UI components and writes invalid Python**: The plan prescribes adding a card to a nonexistent "Project Detail tab" in `index.html`, and calls `calculate_escrow_runway(con, pid)` as a standalone function when it is actually a method on `ProjectAuditor`.
3. **Step 3 is fundamentally unexecutable and architecturally destructive**: 
   - Windows Application Control (WDAC) on the host actively blocks PyArrow (`_fs.pyd`) and DuckDB (`_duckdb.pyd`) compiled C-extensions.
   - The path `data/filings/*/*.parquet` does not exist (the actual pipeline lake is at `gujrera_pipeline/data/form3/<date>/form3_<district>.parquet`).
   - Form 3 filings lack mandatory `projects` table columns (`registration_number`, `promoter_name`, `promoter_id`), which will trigger SQLite `NOT NULL` constraint violations.
   - Dumping 1,500 projects into `intelligence.sqlite` will trigger an $O(N)$ N+1 query storm (~6,000 queries) in `_explore_rows`, inject ~10,000 nodes into a single unclustered Vis.js graph canvas, choke the header dropdown with 1,500 options, and destroy the evaluation harness C-index and pricing benchmarks.

---

## Section-by-Section Evaluation

### 1. System Boundary & Scope
* **Cross-Repo Boundary Violated:** The root contract (`EGM.md`) and ADR-0004 establish `gujrera-intelligence` and `gujrera-pipeline` as sovereign, decoupled repositories where raw/lake data lives strictly in the private pipeline. Step 3 attempts an ad-hoc direct read of private parquet files without respecting the path resolution architecture (`config._PIPELINE_DIR` or environment overrides).
* **Missing Pipeline Handling:** If `real_estate_intelligence` runs in CI or on a machine without the private pipeline repository, the script fails with no defined fallback.
* **Faux FTS5 Requirement:** The plan requires: *"Build FTS5 index entries strictly for newly ingested documents."* Form 3 Parquet files contain zero document text or PDFs. Full PDF bundles exist strictly for the 9 curated research projects (`gujrera_pipeline/data/samples/`). Expecting FTS5 indexing from Form 3 parquet data is a complete misunderstanding of the lake artifacts.

### 2. Architecture Fit & Invariants
* **False Claim of Read-Only SQLite (`mode=ro`):** Section 4 claims UI connections open with `mode=ro`. In reality, `ui/server.py:setup_backends` calls `db.database.get_connection()`, which connects read-write and runs DDL (`init_schema()`). If Step 3 ingests data while the UI runs, database lock contention and write collisions will occur.
* **Binary Database Version Control Antipattern:** `real_estate_intelligence/data/intelligence.sqlite` is tracked in Git. Any write operation, ingestion test, or schema initialization mutates this file, immediately dirtying the git working tree and breaking Git operations.
* **Escrow Semantics Maintained in Backend:** `ProjectAuditor.calculate_escrow_runway` correctly filters for `account_type = 1` (70% statutory retention). This invariant holds in the analytics layer.

### 3. Problem Framing & Strategic Coherence
* **Premature Lake Ingestion:** Step 3 tries to force a 1,500-project slice into a single-node SQLite database designed and tuned around a 9-project benchmark sample. The platform currently lacks:
  1. Server-side pagination for `/api/explore`
  2. Subgraph scoping or clustering for `/api/graph` (Vis.js)
  3. Filterable project search in the UI navigation header
* **False Positive Credential Flags:** Because the 1,500 projects in the Form 3 lake have no linked PDF certificates in `documents`, Step 2's new credential audit will flag 100% of the newly ingested projects with `no_linked_signed_form_three_certificate_in_archive`.

### 4. Blind Spots & Operational Risks
* **Host Application Control Policy (WDAC):** Python packages relying on unapproved C-extension DLLs (`pyarrow`, `duckdb`) throw `ImportError: DLL load failed while importing _duckdb: An Application Control policy has blocked this file`. Step 3 assumes these libraries are available.
* **Hallucinated Test Counts:** The document repeatedly cites "all 49 unit tests". The test suite actually has 23 unit tests.
* **Broken Unittest Discovery Command:** Running `python -m unittest discover -s real_estate_intelligence/tests -p "test_*.py"` fails with `ImportError: Start directory is not importable` unless `PYTHONPATH` or `-t` is explicitly configured.

---

## Findings Categorization & Actionable Fixes

### Blockers (Must fix before proceeding)

1. **BLOCKER 1: Ingestion Toolchain Blocked by Windows Application Control (WDAC)**
   * **Location:** `docs/PROPOSED_NEXT_STEPS_PLAN.md:79`
   * **Rationale:** On the Windows host environment, WDAC blocks loading `_duckdb.pyd` and `_fs.pyd` (PyArrow). Executing `import duckdb` or `import pyarrow` aborts with `ImportError: DLL load failed ... An Application Control policy has blocked this file`. Any ingestion script mandating DuckDB/PyArrow in this runtime will fail immediately.
   * **Fix:** Either execute the parquet-to-sqlite conversion via a standalone signed tool/CLI outside Python, or use a pure-Python parquet reader (or process the conversion on a machine without WDAC restrictions and commit/mount the resulting SQLite file).

2. **BLOCKER 2: Step 1 Git Pull Will Abort on Dirty Tracked Binary SQLite File**
   * **Location:** `docs/PROPOSED_NEXT_STEPS_PLAN.md:47-49`
   * **Rationale:** `real_estate_intelligence/data/intelligence.sqlite` is tracked in git and currently has uncommitted binary modifications in the workspace. Commit `73c8639` on `origin/main` also modified this file. Running `git pull --ff-only origin main` will fail with: `error: Your local changes to the following files would be overwritten by merge`.
   * **Fix:** Add a mandatory pre-pull resolution step: discard local binary modifications via `git checkout HEAD -- real_estate_intelligence/data/intelligence.sqlite`, pull `origin/main`, and formally decide whether `intelligence.sqlite` should be removed from git tracking and placed in `.gitignore` per `EGM.md`.

3. **BLOCKER 3: Form 3 Parquet Schema Violates SQLite NOT NULL Constraints**
   * **Location:** `docs/PROPOSED_NEXT_STEPS_PLAN.md:79-80`
   * **Rationale:** Form 3 filings contain quarterly CA cost certificates and unit counts. They do NOT contain master project registration details (`registration_number`, `promoter_name`, `promoter_id`). Inserting into `projects` from Form 3 parquet will abort with `NOT NULL constraint failed: projects.registration_number`.
   * **Fix:** Do not attempt direct upsert into `projects` from Form 3 parquet files alone. Project metadata must be joined with `all_projects_*.parquet` and `governance_*.parquet`, or loaded into a dedicated staging/filings table.

---

### Major Findings (Must resolve during implementation design)

4. **MAJOR 1: Nonexistent UI Target & Broken Backend Invocation in Step 2**
   * **Location:** `docs/PROPOSED_NEXT_STEPS_PLAN.md:60-68`
   * **Rationale:** 
     1. The plan specifies calling `calculate_escrow_runway(con, pid)`. This is not a top-level function; it is a member method on `ProjectAuditor`. Calling it directly will raise a `NameError`.
     2. `index.html` has no "Project Detail tab". Project information is rendered across `content-dossier` ("Executive 4-Quadrant"), `content-discrepancies`, and the top `#projectBanner`.
   * **Fix:** 
     - Backend: Invoke `self.auditor.calculate_escrow_runway(pid)`.
     - Frontend: Place the "Statutory Credentials & Governance" card inside `content-dossier` Quadrant 1 (Statutory) and the Escrow Runway badge inside `#projectBanner` and Quadrant 4 (Financial).

5. **MAJOR 2: N+1 Query Storm and Vis.js Browser Freeze at 1,500 Projects**
   * **Location:** `docs/PROPOSED_NEXT_STEPS_PLAN.md:84-85`
   * **Rationale:**
     - `ui/server.py:_explore_rows` runs 4-5 SQL queries per project in a Python loop. At 1,500 projects, this executes ~6,000 sequential queries per HTTP request, making $<50\text{ ms}$ latency impossible.
     - `/api/graph` returns all database nodes. Ingesting 1,500 projects will dump ~10,000 nodes and edges into Vis.js, freezing the client browser.
     - `<select id="projectSelect">` receives 1,500 unsearchable options.
   * **Fix:** Ingestion of 1,500 projects must NOT target the default `intelligence.sqlite` database used by the current UI until:
     1. `_explore_rows` is rewritten as a single SQL query with joins/aggregations.
     2. `/api/graph` is scoped by project/neighborhood rather than returning the entire database.
     3. Keep the 1,500-project slice in an isolated benchmark database (`data/ahmedabad_benchmark.sqlite`) rather than replacing `intelligence.sqlite`.

6. **MAJOR 3: False Read-Only Claim in Server Backends**
   * **Location:** `docs/PROPOSED_NEXT_STEPS_PLAN.md:97`
   * **Rationale:** The plan asserts that UI connections open with `mode=ro`. In reality, `server.py` calls `get_connection()` which connects read-write and runs DDL.
   * **Fix:** Create a dedicated `get_ro_connection()` that opens SQLite via URI `file:{path}?mode=ro` and avoids calling `init_schema()`.

7. **MAJOR 4: Evaluation Benchmark Degradation**
   * **Location:** `docs/PROPOSED_NEXT_STEPS_PLAN.md:89`
   * **Rationale:** `eval_harness.py` evaluates survival forecasting and pricing on every record in `projects`. Ingesting 1,500 projects with missing unit transactions or partial dates will degrade the Harrell C-index and break pricing cross-validation.
   * **Fix:** Scope `eval_harness.py` to evaluate specifically against the 9 curated benchmark projects (e.g. `WHERE run_id = 'nine_projects_2026_10_15'`).

---

### Minor / Nit Findings

8. **NIT 1: Test Count and Runner Command Error**
   * **Location:** `docs/PROPOSED_NEXT_STEPS_PLAN.md:28, 55`
   * **Rationale:** The test suite contains 23 unit tests, not 49. The unittest command provided fails without setting `PYTHONPATH`.
   * **Fix:** Update the document to state 23 tests and specify: `python -m unittest discover -s real_estate_intelligence/tests -t real_estate_intelligence -p "test_*.py"` (or use `PYTHONPATH=real_estate_intelligence`).

9. **NIT 2: Inaccurate Parquet File Paths**
   * **Location:** `docs/PROPOSED_NEXT_STEPS_PLAN.md:79`
   * **Rationale:** The document references `data/filings/*/*.parquet`. The actual directory in `gujrera_pipeline` is `form3/<snapshot_date>/form3_<district>.parquet`. The lake is already partitioned by district.
   * **Fix:** Update paths to reflect `gujrera_pipeline/data/form3/2026-11-13/form3_ahmedabad.parquet`.

---

## Summary of Required Plan Revisions

1. **Step 1 Revision:** Add a pre-pull checkout to discard local changes to the tracked binary database: `git checkout HEAD -- real_estate_intelligence/data/intelligence.sqlite`.
2. **Step 2 Revision:** Correct method invocation to `self.auditor.calculate_escrow_runway(pid)` and map UI placement to `content-dossier` Quadrant 1 and Quadrant 4.
3. **Step 3 Redesign:** Quarantine large-scale ingestion into an isolated database (`ahmedabad_benchmark.sqlite`) to prevent $O(N)$ query storms, Vis.js canvas collapse, and evaluation harness benchmark failures. Address host WDAC policy blocks on DuckDB/PyArrow.
