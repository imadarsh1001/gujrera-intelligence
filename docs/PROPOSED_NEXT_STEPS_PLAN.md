# Implementation Specification: GujRERA Intelligence Platform Next Steps

* **Author:** Elephant / Assistant (Revised post-EGM Goldfish Review)
* **Date:** 2026-11-17
* **Status:** Resolved & Implementation Ready (Reviewed across Stages 5–9)
* **Target Package:** `real_estate_intelligence` & root workspace

---

## 1. System Overview & Problem Statement

The platform currently operates an institutional due-diligence engine over a 9-project seed database (`intelligence.sqlite`), supported by a local HTTP dashboard (`ThreadingHTTPServer` on port 8765), GBDT pricing valuation with SHAP breakdowns, delay survival forecasting, and an evaluated 10-case evidentiary agent.

Following the migration of candidate audit logic in commit `73c8639` on `origin/main`, two immediate operational and product gaps exist:

1. **Repository Drift & Local Working Copy Dirty State:**
   - Local `main` is at `91e2d52`, 5 commits behind `origin/main` (`e8da240`).
   - The tracked binary database `real_estate_intelligence/data/intelligence.sqlite` has local uncommitted modifications. Because commit `73c8639` upstream also touched this binary database, a standard `git pull --ff-only` will fail with an unmergeable binary conflict unless local mutations are discarded first.
   - The working copy retains an orphaned, untracked directory (`real_estate_intelligence/staging_from_pipeline/`), and an external worktree (`cleanup_pipeline_files`) remains mounted.
2. **Unsurfaced Statutory Governance & Escrow Runway in UI:**
   - The statutory credential coverage audit (`ProjectAuditor.audit_credential_coverage` in `analytics/audit.py`) and cash runway engine (`ProjectAuditor.calculate_escrow_runway`) are fully integrated and tested in the backend, but are not exposed in the structured `/api/project/{pid}` REST payload or the executive dashboard (`ui/static/index.html`).
3. **Data Lake Scalability Boundary:**
   - The upstream private pipeline contains 58,741 Form 3 filings across 17,632 projects in columnar Parquet format.
   - Direct ingestion of large slices into the active UI database is fundamentally constrained: host Windows Defender Application Control (WDAC) blocks DuckDB/PyArrow compiled C-extensions, `_explore_rows` executes an unpaginated 4-query-per-project loop ($O(N)$ query storm), and Vis.js renders full-database dumps without clustering. Large-scale ingestion is therefore partitioned into a separate architectural track.

---

## 2. Feature Specification (Milestone 1: VCS Sync & UI Governance)

### 2.1 Goals
* Reconcile local git state to match `origin/main` (`e8da240`) cleanly using fast-forward only, eliminating local binary conflicts and pruning dangling worktrees.
* Expose statutory professional credential verification (architect registration, structural engineer registration, Form 3 CA expenditure certification) in the `/api/project/{pid}` response and the Executive Dossier UI view.
* Expose the Escrow Cash Burn Rate and Runway status alongside existing project KPI metrics in `#projectBanner` and the Financial health quadrant.
* Maintain 100% pass rates across all 49 unit tests and the 4-component evaluation benchmark (`run_server.py eval`).

### 2.2 Non-Goals
* No large-scale data lake ingestion in this milestone. Large-scale data ingestion is decoupled into Milestone 2 (RFC track).
* No UI framework migration (no React, Vue, or Vite build toolchains). The UI remains vanilla HTML5/JS with vendored assets served by `ThreadingHTTPServer`.
* No changes to crawler mechanics or upstream private pipeline files in `gujrera_pipeline`.

### 2.3 System Invariants & Constraints
* **Read/Write Boundary:** Only batch ingestion scripts and worker queues mutate `intelligence.sqlite`. The UI server and MCP tools remain strictly read-only.
* **Privacy Redaction:** Invariant 2.3 mandates that no individual Aadhaar, PAN, or personal KYC identifiers are exposed in UI payloads. The `/api/project/{pid}` endpoint must strictly whitelist public professional fields (`name`, `firm`, `license_or_reg_no`, `observed_count`, `verified_count`, `gap_codes`).
* **Escrow Semantics:** In the database (`banks.account_type`), Account Type `1` is strictly interpreted as the 70% statutory retention escrow, and `2` as the 100% collection account.

---

## Detailed Implementation Plan (Milestone 1)

### Step 1: Git Reconciliation & Worktree Pruning
* **Objective:** Cleanly fast-forward local `main` to `origin/main` (`e8da240`), eliminate the orphaned staging folder, and safely remove the secondary git worktree without merge conflicts.
* **Pre-Execution Check:**
  1. Inspect working tree: `git status --porcelain`.
  2. Discard uncommitted mutations to the tracked binary database:
     ```powershell
     git checkout HEAD -- real_estate_intelligence/data/intelligence.sqlite
     ```
* **Actions:**
  1. Remove the obsolete untracked staging directory:
     ```powershell
     Remove-Item -Recurse -Force "real_estate_intelligence/staging_from_pipeline"
     ```
  2. Fast-forward local `main` to remote:
     ```powershell
     git pull --ff-only origin main
     ```
  3. Discover and prune the secondary worktree:
     Run `git worktree list`. Identify the worktree linked to branch `cleanup_pipeline_files`.
     Execute:
     ```powershell
     git worktree remove --force "C:/Users/adars/.gemini/antigravity/worktrees/gujRERA/cleanup_pipeline_files"
     git worktree prune
     ```
  4. Delete the local tracking branch:
     ```powershell
     git branch -d cleanup_pipeline_files
     ```
* **Verification Gate:**
  * `git status` reports clean working tree on branch `main` (untracked review docs excepted).
  * `git log -1 --oneline` outputs `e8da240 docs: retire staging_from_pipeline references from root blueprint and README`.
  * Run test suite from repository root:
    ```powershell
    pushd real_estate_intelligence; $env:PYTHONPATH="."; python -m unittest discover -s tests -p "test_*.py"; popd
    ```
    (Reports `Ran 49 tests ... OK`).

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
     * Enforce privacy redaction: ensure `credential_coverage` returns only safe, whitelisted fields (`roles`, `gap_codes`) and zero PAN/Aadhaar identifiers.
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
       Update `loadProject(pid)` around line 1005 to parse `data.credential_coverage` and `data.escrow_runway`, updating badge text and Tailwind CSS color classes dynamically.
  3. **Regression Guard & Unit Testing:**
     * Extend `real_estate_intelligence/tests/test_ui_server.py`:
       Add `test_project_endpoint_credential_and_runway_keys()` asserting that querying `/api/project/13560` returns status 200 with dictionary keys `credential_coverage` and `escrow_runway` matching expected schema types.
* **Verification Gate:**
  * Run `python -m unittest real_estate_intelligence/tests/test_ui_server.py` (100% pass).
  * Run `python run_server.py eval` to confirm 100% baseline parity on AI/ML models.

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
