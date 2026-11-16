# EGM Feature Critic Review Report: Next Steps Plan (Lines 1..41)

**Target Document:** `docs/PROPOSED_NEXT_STEPS_PLAN.md`  
**Review Scope:** `FeatureRange` (Lines 1..41: Title, System Overview, Problem Statement, Goals, Non-Goals, System Invariants & Constraints)  
**Reviewer:** EGM Feature Critic Reviewer (Goldfish subagent)  
**Baseline Contracts:** Root `EGM.md`, `real_estate_intelligence/EGM.md`  
**Verdict:** **REJECT WITH MAJOR REVISIONS (4 Blockers, 4 Majors, 2 Nits)**  
**Status:** Completed (Stage 7)

---

## Executive Summary

The proposed `FeatureRange` (Lines 1..41) conflates three completely unrelated engineering domains—**Git VCS Operations**, **Web UI Presentation**, and **Large-Scale Data Lake Ingestion (ETL)**—into a single monolithic specification. 

Beyond this lack of separation of concerns, the specification suffers from fundamental architectural contradictions: it attempts to ingest a ~1,500-project slice from an ungrounded Parquet path into an SQLite prototype that performs unpaginated N+1 query loops on `/api/explore`, while simultaneously declaring server-side pagination to be an out-of-scope Non-Goal. Furthermore, key system invariants (such as "read-only" UI connections) are contradicted by the actual codebase implementation (`get_connection` executes DDL schema initialization in read-write mode), and the evaluation harness baseline will be broken by unchecked schema/data ingestion.

---

## 1. Lens 1: Design Critique (`egm-design`)

### 1.1 Inaccurate Problem Framing vs. Codebase Reality (Lines 14–17)
* **Untracked Binary Mutation Omitted (Line 15):** Problem 1 frames repository drift as simply being 5 commits behind `origin/main` with an untracked staging directory. It fails to report that `real_estate_intelligence/data/intelligence.sqlite` is tracked in git and currently has uncommitted modifications (`modified: real_estate_intelligence/data/intelligence.sqlite`). Because commit `73c8639` on `origin/main` also modifies `intelligence.sqlite`, executing `git pull --ff-only` will fail immediately with a merge conflict.
* **Premature Capability Claim (Line 16):** Problem 2 asserts that `ProjectAuditor.audit_credential_coverage` "exists in the backend and passes all 49 unit tests." In the checked-out workspace (`main` at `91e2d52`), this method does not exist in `analytics/audit.py` (it was introduced in commit `73c8639` on `origin/main`). Claiming it exists while simultaneously stating git has not been updated is contradictory.
* **Mischaracterization of Escrow Runway Status (Line 16):** The document claims escrow runway metrics have "zero representation in the interactive web UI dashboard." In reality, `calculate_escrow_runway` is already integrated into the backend and exposed via the Copilot agentic chat endpoint (`ui/server.py:841`). The actual gap is strictly its absence in the structured `/api/project/{pid}` payload and the Project Detail DOM view.

### 1.2 Incoherent Conflation of Three Unrelated Concerns (Lines 14–28)
The plan bundles three orthogonal concerns into one specification:
1. **Developer Operations / VCS Hygiene:** Pulling 5 commits, pruning worktrees, deleting untracked folders (Lines 24, 44–55).
2. **Frontend & REST API Surfacing:** Adding response fields to `/api/project/{pid}` and DOM cards to `index.html` (Lines 25–26, 57–74).
3. **Data Lake ETL Migration:** Ingesting ~1,500 projects from Form 3 Parquet files, introducing third-party dependencies (`duckdb`/`pyarrow`), and re-indexing FTS5 (Lines 27, 75–90).

Coupling VCS operations and large-scale ETL to a frontend UI feature creates unmanageable blast radius: a schema parsing failure or latency spike during 1,500-project ingestion blocks releasing the UI credential cards, and Git reconciliation merge issues halt application feature development.

### 1.3 Architectural Violation: Ingestion Scale vs. Prototype Rendering (Lines 17, 27, 31)
* **The N+1 Query Bottleneck:** In `ui/server.py:476-550`, `_explore_rows()` iterates through every project in `projects` and executes three sequential child queries per project (`finances`, `applications`, `unit_transactions`). For the current 9-project seed, this executes 28 queries. For the proposed 1,500-project slice, `/api/explore` will execute **over 4,500 synchronous database queries** on every request.
* **Client DOM Bloat:** The dashboard `index.html` has no virtualized scrolling or pagination; it renders the entire JSON array directly into memory and DOM.
* **Self-Contradiction:** Non-Goal 2.2 (Line 31) explicitly refuses to build server-side pagination in this milestone. Ingesting ~1,500 projects before pagination and relational query optimization are implemented violates the prototype's architectural boundaries and will destroy the sub-50ms latency target (Line 17, Line 84).

---

## 2. Lens 2: Structural Critique (`egm-structural`)

### 2.1 Contradictions Between Goals and Non-Goals
* **Goal 2.1 (Line 27) vs. Non-Goal 2.2 (Line 31):** Non-Goal 2.2 correctly identifies that pagination and spatial clustering are absent. Yet Goal 2.1 targets 1,500 projects—a 166x increase in volume that immediately triggers the need for the exact pagination excluded in Non-Goal 2.2.
* **Goal 2.1 (Line 27) vs. Non-Goal 2.2 (Line 33):** Non-Goal 2.2 asserts "No live scraping or modifications to the private `gujrera-pipeline` crawling layer." However, Form 3 Parquet files reside inside the private `gujrera_pipeline/data/` tree (as defined in root `EGM.md`). Proposing ingestion from the pipeline lake without defining an immutable export seam violates the dual-repository boundary.
* **Goal 2.1 (Line 28) vs. Evaluation Harness Design:** Goal 2.1 demands maintaining 100% pass rate on `run_server.py eval`. In `tests/eval_harness.py:90-125`, `evaluate_survival_model()` loops through all projects in the database. Ingesting 1,500 unvalidated projects directly into `intelligence.sqlite` will degrade benchmark execution time and fail hardcoded accuracy thresholds (e.g. Hedonic Pricing RMSE `< 2500.0`).

### 2.2 Unverifiable and Contradicted System Invariants (Section 2.3)
* **The "Read-Only UI" Contradiction (Line 36 vs. Codebase Reality):** 
  Invariant 2.3 asserts: *"Read/Write Boundary: Only ingestion scripts and worker queues mutate intelligence.sqlite. The UI server and MCP tools remain strictly read-only."* 
  Table 4 (Line 97) further claims: *"UI connections open with `mode=ro`."*
  **This is factually false.** In `real_estate_intelligence/ui/server.py:130` and `db/database.py:10-21`, `IntelligenceRequestHandler.setup_backends()` calls `get_connection()`, which connects in read-write mode and calls `init_schema(con)` (executing `CREATE TABLE IF NOT EXISTS` DDL). If SQLite URI `file:...mode=ro` were applied today, the server would crash with `sqlite3.OperationalError: attempt to write a readonly database`.
* **Ungrounded Privacy Redaction (Line 37):** Stating "No individual Aadhaar, PAN, or KYC personal identity records are exposed in UI payloads" is an ungrounded assertion. There are no automated assertions, regex guards, or integration tests in `test_ui_server.py` verifying that new payload structures do not leak PII.

### 2.3 Critical Missing Architectural Constraints in Section 2.3
1. **Dependency Footprint Invariant:** `real_estate_intelligence/pyproject.toml` strictly permits `pypdf>=5.0.0` as its runtime dependency. Step 3 (Line 79) introduces `DuckDB` and `PyArrow`. Section 2.3 fails to specify whether heavy analytical libraries are permitted in the public core package or quarantined to an optional ingestion extra.
2. **Database Isolation Invariant:** Section 2.3 lacks an invariant specifying that slice ingestions must not mutate the evaluation baseline database (`intelligence.sqlite` / `test_intelligence.sqlite`).
3. **Idempotency & Upsert Invariant:** No constraint governs transaction boundaries, duplicate resolution, or rollback mechanics for multi-table ingestion (`projects`, `quarterly_timeline`, `unit_transactions`, `document_fts`).

---

## 3. Lens 3: Style & Clarity Critique (`egm-style`)

### 3.1 Ungrounded Claims and Overstatements
* **Line 12: *"Harrell C-index = 1.0 survival delay model"***: Claiming a perfect 1.0 concordance index on an empirical statistical model is misleading. In `eval_harness.py`, this metric was evaluated on a 9-project seed dataset. Stating it as a baseline capability without disclosing sample size is an ungrounded boast.
* **Line 17: *"covering 17,632 projects (99.99% of Gujarat)"***: The 99.99% statistic lacks provenance or grounding against official GujRERA gazette filings.

### 3.2 Vague Metaphors and Buzzwords
* **Line 1: *"Sovereign Platform"***: Non-technical marketing fluff in an engineering specification.
* **Line 12: *"evidentiary agent on a 9-project deep sample"***: Euphemistic phrasing; "deep sample" obscures that the database contains only 9 records.
* **Line 17: *"controlled, segmented pathway to ingest this lake"***: Hand-waving buzzwords. An engineering specification must state exact mechanisms (e.g. "batch-chunked CLI ingestion script reading partitioned Parquet directories").
* **Line 17: *"without overwhelming the current single-page dashboard"***: Subjective and untestable. Needs operational criteria (e.g., initial payload `< 500 KB`, DOM render `< 100 ms`).
* **Lines 25, 26: *"Surface professional credential validation... Surface the Escrow Cash Burn Rate"***: The verb "surface" is used repeatedly without defining the contract. Specify REST response schema keys and UI component specifications.

### 3.3 Passive Constructions and Commit Inaccuracies
* **Line 14:** Attributes audit logic migration to commit `e8da240`. In git history, `e8da240` was merely a documentation commit; the code was integrated in `73c8639`.

---

## 4. Prioritized Findings Matrix

| Finding ID | Severity | Citations | Description | Required Recommendation |
|---|---|---|---|---|
| **CRIT-01** | **Blocker** | Lines 14–28, 44–90 | **Omnibus Anti-Pattern:** Conflation of Git ops, UI enhancements, and Parquet ETL into one plan. | Split into three separate plans: (1) Ops Runbook for Git Sync, (2) UI Credential Surfacing Spec, (3) Lake Ingestion & Pagination RFC. |
| **CRIT-02** | **Blocker** | Lines 27, 31, 476–550 (`ui/server.py`) | **Architectural Breakdown:** Ingesting 1,500 projects triggers an unpaginated 4,500+ query N+1 cascade in `/api/explore`. | Prerequisite server-side pagination (`LIMIT`/`OFFSET`) and SQL query rewriting before any multi-project slice ingestion. |
| **CRIT-03** | **Blocker** | Lines 28, 89, `tests/eval_harness.py` | **Evaluation Baseline Invalidation:** Ingesting 1,500 projects into `intelligence.sqlite` breaks test harness assumptions. | Enforce database isolation: slice ingestion must write to a separate target (e.g. `data/ahmedabad_slice.sqlite`), leaving baseline intact. |
| **CRIT-04** | **Blocker** | Lines 36, 97, `db/database.py:10-21` | **Unenforced / False Invariant:** UI server claims `mode=ro`, but codebase connects read-write and runs DDL schema migrations. | Decouple DDL `init_schema()` from `get_connection()` and enforce URI `mode=ro` in `IntelligenceRequestHandler`. |
| **CRIT-05** | **Major** | Lines 15, 47 | **Incomplete Git Status:** Plan ignores uncommitted modification to tracked binary `intelligence.sqlite`. | Document modified `intelligence.sqlite` in Problem 1 and add resolution (`git checkout` / restore) to Step 1. |
| **CRIT-06** | **Major** | Section 2.3, Line 79 | **Missing Dependency Invariant:** Step 3 adds `DuckDB`/`PyArrow`, violating lightweight runtime dependency invariant. | Add dependency constraint to Section 2.3 restricting external C-extensions or defining optional ETL extras. |
| **CRIT-07** | **Major** | Line 17, Line 79 | **Ungrounded / Invalid Parquet Path:** Plan references `data/filings/*/*.parquet`, which does not exist in the repo. | Ground file paths against the cross-repo contract (`gujrera_pipeline/data/form3` per ADR-0002). |
| **CRIT-08** | **Major** | Lines 12, 17, 25–26 | **Imprecise Style & Vague Metrics:** "Surface", "controlled segmented pathway", and ungrounded "C-index = 1.0". | Enforce Plain-English Standard: specify exact REST keys, UI elements, and sample size qualifications. |
| **CRIT-09** | **Nit** | Line 14 | **Commit Misattribution:** `e8da240` cited for logic migration instead of `73c8639`. | Correct commit citation in Section 1. |
| **CRIT-10** | **Nit** | Lines 1, 12 | **Grandiose Vocabulary:** "Sovereign Platform" and "deep sample". | Replace with objective technical terms: "Intelligence Platform" and "9-project seed dataset". |

---

## 5. Specific Restructuring Recommendations

1. **Purge Step 1 (Git Reconciliation) from Feature Specification:**  
   VCS synchronization is a developer workflow hygiene item, not a product feature. Execute the git fast-forward and worktree cleanup via standard operations before authoring feature plans.
2. **Scope the Immediate Feature Spec to Milestone 1: UI Statutory Surfacing:**  
   Focus solely on exposing `audit_credential_coverage` and `calculate_escrow_runway` in `/api/project/{pid}` and adding the corresponding governance cards in `ui/static/index.html`.
3. **Draft an Architectural RFC for Milestone 2: Lake Ingestion & Server Pagination:**  
   Address district ingestion separately. Design the batch ETL script, define PyArrow/DuckDB placement as an ETL-only dependency, rewrite `_explore_rows` into a single paginated SQL JOIN query, and specify database isolation for benchmark stability.
