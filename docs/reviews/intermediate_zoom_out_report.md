# EGM Intermediate Zoom-Out Strategic Assessment Report

**Document Under Review:** `docs/PROPOSED_NEXT_STEPS_PLAN.md` (Lines 1–107)  
**Evaluator:** EGM Intermediate Zoom-Out Reviewer (Goldfish Subagent)  
**Contract Baselines:** Root `EGM.md`, `real_estate_intelligence/EGM.md`  
**Prior Stages Reviewed:** Stage 5 (Zoom-Out), Stage 6 (Comprehension), Stage 7 (Critic)  
**Status:** Completed (Stage 8)  
**Date:** 2026-11-17  

---

## 1. Executive Summary & Macro-Architectural Verdict

### Macro-Architectural Verdict: REJECT AS WRITTEN — MANDATORY DE-SCOPING & PARTITIONING

`docs/PROPOSED_NEXT_STEPS_PLAN.md` **cannot survive scrutiny as a single executable implementation plan.** 

The proposal suffers from an **Omnibus Anti-Pattern**: it braids three fundamentally disconnected engineering efforts—**Developer VCS Hygiene** (Step 1), **Frontend/REST Feature Surfacing** (Step 2), and **Data Lake Parquet Ingestion/ETL** (Step 3)—into an indivisible linear plan. 

The blast radii and failure modes of these steps are radically incompatible:
1. **Step 1 will fail at line 1**: The working copy has uncommitted modifications to a git-tracked binary file (`real_estate_intelligence/data/intelligence.sqlite`), which was also modified upstream in commit `73c8639`. A blind `git pull --ff-only` will immediately abort.
2. **Step 2 is structurally viable and high-value**, but is crippled in the document by invalid Python signatures (`calculate_escrow_runway(con, pid)` instead of `self.auditor.calculate_escrow_runway(pid)`) and a hallucinated DOM target ("Project Detail tab" does not exist in `index.html`).
3. **Step 3 is fundamentally unexecutable and architecturally destructive**:
   - Host Windows Defender Application Control (WDAC) blocks DuckDB and PyArrow C-extensions.
   - Form 3 filings lack mandatory master project metadata, causing immediate SQLite `NOT NULL` constraint crashes on `projects.registration_number`.
   - Ingesting ~1,500 projects triggers an $O(N)$ N+1 query loop in `ui/server.py:_explore_rows` (executing **4,501 sequential SQL queries** per HTTP request), dumps **10,000+ unclustered nodes** into Vis.js freezing the client browser, injects 1,500 options into an unsearchable HTML `<select>` element, and invalidates the AI/ML evaluation harness (`run_server.py eval`).

Coupling these three items guarantees systemic failure: Step 3's blockers will permanently stall shipping Step 2's high-value statutory features. The document must be formally partitioned into an **Immediate Implementation Plan (Milestone 1: Steps 1 & 2)** and a **Future Architectural RFC (Milestone 2: Step 3)**.

---

## 2. Assessment of Cross-Cutting Systemic Risks

### 2.1 The Binary SQLite Git-Tracking Antipattern & Collaboration Impact
- **Current State:** `real_estate_intelligence/data/intelligence.sqlite` (a 4.8 MB binary database) is tracked in Git. In the active workspace, `git status --porcelain` reveals ` M real_estate_intelligence/data/intelligence.sqlite`. Simultaneously, commit `73c8639` on `origin/main` modified this identical binary file.
- **Git Mechanics Failure:** Git cannot perform 3-way line merges on binary SQLite files. Executing `git pull --ff-only origin main` aborts immediately with:  
  `error: Your local changes to the following files would be overwritten by merge`.
- **Systemic Root Cause:** Any developer who launches `run_server.py`, runs the test suite, or executes schema initialization mutates SQLite page headers and WAL journal flags. Because `intelligence.sqlite` is tracked, routine local execution continuously dirties the git tree, breaking multi-developer collaboration, automated CI pulls, and branch switching.
- **Required Resolution:** 
  1. *Immediate Step 1 fix:* Discard local binary mutations prior to pulling:  
     `git checkout HEAD -- real_estate_intelligence/data/intelligence.sqlite` followed by `git pull --ff-only origin main`.
  2. *Architectural fix:* The project contracts (`EGM.md` and `real_estate_intelligence/EGM.md`) designate `data/` as generated artifacts. The database must either be untracked and seeded on-demand via `db.loader` from the immutable run archive (`gujrera_pipeline/data/runs/nine_projects_2026_10_15`), or protected by opening connections in immutable read-only mode (`mode=ro&immutable=1`) during non-ingest operations.

### 2.2 Viability of Step 2 (UI Credential Surfacing) as an Independent Milestone
- **Viability Assessment:** **HIGHLY VIABLE, LOW RISK, IMMEDIATE VALUE.**
- **Isolation:** Step 2 touches exactly two files: `real_estate_intelligence/ui/server.py` and `real_estate_intelligence/ui/static/index.html`. It introduces zero new runtime dependencies, requires zero external data, and operates safely over the verified 9-project seed database.
- **Concrete Defects in Document That Must Be Corrected:**
  1. *Invalid Backend Function Call:* Step 2 calls `calculate_escrow_runway(con, pid)`. In `real_estate_intelligence/analytics/audit.py`, `calculate_escrow_runway` is an instance method of `ProjectAuditor` that accepts only `project_id`. The backend handler must invoke `self.auditor.calculate_escrow_runway(pid)`.
  2. *Hallucinated DOM Container:* `index.html` has no "Project Detail tab". Project views are structured across `content-dossier` ("Executive 4-Quadrant"), `content-discrepancies`, and `#projectBanner`. The "Statutory Credentials & Governance" card must be placed in `content-dossier` Quadrant 1 (Statutory Profile), and the Escrow Runway metric must be placed in `#projectBanner`'s KPI grid and Quadrant 4 (Financial Health).
  3. *PII Whitelisting:* Invariant 2.3 mandates privacy redaction (no PAN/Aadhaar/KYC). The `/api/project/{pid}` response must not blindly dump uncurated audit dictionaries into the JSON payload; it must whitelist safe credential fields (`architect_verified`, `engineer_verified`, `form3_ca_status`, `runway_months`).
  4. *Target Project Grounding:* Step 2 specifies testing project `13560`. Project 13560 is one of the 9 curated seed projects and serves as a valid fixture, but the test in `test_ui_server.py` should assert both verified and unverified statutory states.

### 2.3 Systemic Collapse of Step 3 (Parquet Lake Ingestion)
Attempting to execute Step 3 as specified triggers a four-point cascading failure:

1. **Host Windows Defender Application Control (WDAC) Execution Barrier:**
   - On the host Windows machine, WDAC policy actively blocks unapproved third-party C-extensions, specifically `pyarrow._fs` and `duckdb._duckdb`.
   - `real_estate_intelligence/pyproject.toml` strictly permits `pypdf>=5.0.0` as its runtime dependency.
   - Any script specifying `import duckdb` or `import pyarrow` fails on this runtime environment. A pure-Python parquet reader (or an external ETL build step that outputs a SQLite artifact) is required.

2. **$O(N)$ N+1 Query Cascade in `_explore_rows`:**
   - In `ui/server.py:476-550`, `_explore_rows()` iterates through every project in `projects` and executes three sequential SQL child queries (`finances`, `applications`, `unit_transactions`) per project.
   - For 9 projects: $1 + (9 \times 3) = 28$ queries.
   - For 1,500 projects: $1 + (1500 \times 3) = \mathbf{4,501\text{ synchronous SQL queries}}$ on every single `/api/explore` request.
   - Sub-50ms latency is physically impossible under this query cascade. Furthermore, Non-Goal 2.2 explicitly excludes server-side pagination, ensuring that the entire unpaginated JSON array will be serialized and transmitted to a non-virtualized frontend table.

3. **Vis.js Graph Saturation & Browser Freezing:**
   - In `ui/server.py:267-295`, `/api/graph` executes `SELECT * FROM graph_nodes` and `SELECT * FROM graph_edges`. It dumps every node and edge in the database directly into the browser.
   - Ingesting 1,500 projects expands the graph from ~80 nodes to **over 12,000 nodes and 25,000 edges**.
   - Vis.js running 25,000-edge spring-physics simulation on an HTML5 canvas will peg client CPU at 100% and completely freeze the browser tab. The platform lacks subgraph scoping, neighborhood filtering, or node clustering.
   - Simultaneously, `<select id="projectSelect">` in `index.html` dynamically loads all project IDs. A dropdown with 1,500 unsearchable options destroys UI usability.

4. **Schema Incompatibility & Constraint Violation:**
   - Form 3 filings are quarterly financial cost certificates issued by Chartered Accountants. They contain CA costs and unit totals; they do **not** contain master project registration fields (`registration_number`, `promoter_name`, `promoter_id`).
   - Attempting to upsert into `projects` directly from Form 3 Parquet files violates SQLite `NOT NULL` constraints (`NOT NULL constraint failed: projects.registration_number`).

5. **AI/ML Evaluation Benchmark Degradation:**
   - `tests/eval_harness.py` evaluates survival forecasting and ML pricing across all records in `projects` (`SELECT project_id, name, bu_status FROM projects`).
   - The Form 3 lake lacks BU permission dates and complete transaction histories. Ingesting 1,500 partial projects will corrupt the survival models, drop Harrell's C-index below the required 0.75 threshold, and cause `run_server.py eval` to fail.

---

## 3. Authoritative Go / No-Go Strategic Decisions

| Step | Plan Step Description | Strategic Decision | Technical Justification & Mandatory Directives |
|---|---|---|---|
| **Step 1** | **Git Reconciliation & Worktree Pruning** | **CONDITIONAL GO** | **Recategorize as Operational Runbook.** Must NOT be gated as a product feature. Pre-condition fix mandatory: execute `git checkout HEAD -- real_estate_intelligence/data/intelligence.sqlite` before `git pull --ff-only origin main`. Remove hardcoded Windows user paths. |
| **Step 2** | **UI Exposure of Credential & Escrow Metrics** | **GO (Milestone 1)** | **Promote to Primary Feature Objective.** High institutional value, low blast radius. Fix method invocation to `self.auditor.calculate_escrow_runway(pid)`, place cards in `content-dossier` Quadrant 1 and `#projectBanner`/Quadrant 4, whitelist payload fields against PII leakage, and verify against `test_ui_server.py`. |
| **Step 3** | **District-Level Parquet Lake Ingestion** | **NO-GO (REJECT)** | **Sever from Document entirely.** Fails host WDAC security policy, violates SQLite `NOT NULL` constraints, triggers 4,501-query N+1 cascade, freezes Vis.js client canvas with 10,000+ nodes, and destroys the evaluation harness baseline. Must be deferred to a dedicated architectural RFC. |

---

## 4. Document Restructuring Roadmap (Prior to Stage 9)

To ensure **Implementation Readiness (Stage 9)**, the single monolithic plan must be split into two decoupled specifications:

### Document 1: `docs/MILESTONE_1_UI_CREDENTIALS.md` (Implementation Ready)
1. **Scope:** Restricted exclusively to VCS reconciliation and UI/REST credential surfacing on the 9-project seed database.
2. **Phase 1: Pre-Execution VCS Runbook:**
   - Discard tracked SQLite modifications: `git checkout HEAD -- real_estate_intelligence/data/intelligence.sqlite`.
   - Remove orphaned directory: `Remove-Item -Recurse -Force real_estate_intelligence/staging_from_pipeline`.
   - Fast-forward to `origin/main`: `git pull --ff-only origin main`.
   - Prune worktree: `git worktree remove --force <worktree_path>` and `git worktree prune`.
3. **Phase 2: Backend REST Enhancement:**
   - Extend `ui/server.py` `/api/project/{pid}` handler.
   - Invoke `self.auditor.audit_credential_coverage(pid)` and `self.auditor.calculate_escrow_runway(pid)`.
   - Sanitize and whitelist JSON output keys (prevent PII exposure).
4. **Phase 3: Frontend DOM Presentation:**
   - Insert "Statutory Credentials & Governance" card into `content-dossier` Quadrant 1.
   - Insert Escrow Runway metric into `#projectBanner` KPI grid and Quadrant 4.
5. **Phase 4: Verification Contract:**
   - Run unit test suite: `python -m unittest discover -s real_estate_intelligence/tests -t real_estate_intelligence -p "test_*.py"` (confirming all 49 tests pass).
   - Assert new keys in `test_ui_server.py`.
   - Run `python run_server.py eval` to confirm 100% baseline parity.

### Document 2: `docs/rfc/RFC_0001_LAKE_INGESTION_PAGINATION.md` (Architectural Track)
1. **Scope:** Big data lake ingestion, query engine optimization, and UI virtualization.
2. **Prerequisites to be designed before any lake ingestion:**
   - **WDAC Compatibility Strategy:** Pure-Python Parquet decoding or out-of-band SQLite database generation.
   - **Relational Ingestion Pipeline:** Multi-table relational joins connecting Form 3 filings with project registration catalogs.
   - **Database Isolation:** Ingesting slice datasets into an isolated database (`data/ahmedabad_benchmark.sqlite`) to protect the primary seed and evaluation baseline.
   - **Explore Query Rewriting:** Eliminating the N+1 loop in `_explore_rows` by rewriting it into a single SQL query with aggregations and indexed joins.
   - **Pagination Contract:** Implementing `LIMIT` and `OFFSET` parameters on `/api/explore`.
   - **Graph Subgraph Scoping:** Updating `/api/graph` to return project-scoped ego networks rather than full-database dumps.
