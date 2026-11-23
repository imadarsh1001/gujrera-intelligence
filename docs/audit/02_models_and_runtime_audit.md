# Empirical Audit Report: ML Models, Discrepancy Engine & MCP Runtime
**Audit Date**: November 23, 2026 | **Target Database**: `data/intelligence.sqlite` (17,787 projects, 1.95M units)  
**Verification Harness**: Read-only Python 3.12.14 empirical benchmarking against production code and database.

---

## 1. Quantitative Machine Learning Model Evaluation

Evaluated `analytics/ml_pricing.py` (`HedonicPricingModel`) and `analytics/survival.py` (`CompletionDelaySurvivalModel`) on full statewide data and an 80/20 holdout split.

### 1.1 Completion Delay Survival Analysis (`CompletionDelaySurvivalModel`)
- **Architecture**: Semi-parametric Cox Proportional Hazards with Breslow baseline cumulative hazard (`analytics/survival.py:14-131`).
- **Feature Vector**: 4 covariates: `velocity_ratio`, `incurred_cost_ratio`, `complaints_count`, `default_quarters_count`.
- **Dataset Size**: 17,787 projects total; 17,787 with parseable `start_date` (`projects.start_date`).

| Metric / Dimension | Full Database Run | 80/20 Holdout Split (Train / Test) | File & Line Reference |
| :--- | :--- | :--- | :--- |
| **Sample Size ($N$)** | 17,787 projects | Train: 14,229 \| Test: 3,558 | `analytics/survival.py:280-323` |
| **Observed Events ($E=1$)** | **4 projects (0.02%)** | Train: 3 \| Test: 1 | `analytics/survival.py:303-305` |
| **Right-Censored ($E=0$)** | **17,783 projects (99.98%)** | Train: 14,226 \| Test: 3,557 | `analytics/survival.py:304` |
| **Wall-Clock Training Time** | 91.24s (100 iterations) | 51.40s (100 iterations) | `analytics/survival.py:68-106` |
| **Peak Memory Allocation** | 10.98 MB | 1.50 MB | `analytics/survival.py:55-59` |
| **Fitted Coefficients ($\beta$)** | `[6.122, 3.583, -0.057, 2.569]` | `[4.958, 2.243, -0.001, 3.185]` | `analytics/survival.py:107` |
| **Harrell's C-Index** | **1.0000** (artifact of $E=4$) | **1.0000** (admissible=1,938, concordant=1,938) | `analytics/survival.py:247-274` |
| **Serialized JSON Footprint** | **2,001 bytes (1.95 KB)** | $\beta$ vector + 119 baseline steps | `analytics/survival.py:110-129` |

#### The 4 Completed Projects in Entire Database
Only 4 projects in `projects` satisfy the event completion criteria `is_completed = progress >= 99.0 or 'Approved' in bu_status` (`survival.py:303`):
1. `project_id = 13560` (Skydeck Serene): Form 1 progress = 100.0%, BU Approved (Blocks A, B).
2. `project_id = 13705` (The Gate by Dev Aashish): Form 1 progress = 100.0%, BU Approved (Blocks A+B+C+D).
3. `project_id = 16104` (Vrundavan Elysia): Form 1 progress = 94.0%, BU Approved (Block A).
4. `project_id = 17255` (Atmos by Solaire): Form 1 progress = 100.0%, BU Approved (Blocks A, B).

#### Root Cause of 99.98% Censorship & Dead Features
1. **Event Definition**: `is_completed = (r[4] or 0.0) >= 99.0 or ("Approved" in str(r[10] or ""))` (`survival.py:303`). Across 17,787 projects, `latest_form_one_progress_pct` is populated for only **9 projects** (`projects.latest_form_one_progress_pct`, 3 $\ge$ 99%), and `bu_status` is populated for only **9 projects** (4 with "Approved"). The remaining 17,778 statewide rows are NULL.
2. **Covariate Sparsity**:
   - `velocity_ratio`: Non-null in 9 projects (99.95% dead, defaults to 0.0).
   - `incurred_cost_ratio`: Non-null in 9 projects (99.95% dead, defaults to 0.0).
   - `complaints_count`: Non-zero in 4 projects (99.98% dead, 0).
   - `default_quarters_count`: Non-zero in 3 projects (99.98% dead, 0).
3. **Artifactual C-index**: The Harrell's C-index of 1.0000 is an empirical artifact: only 1 event exists in the test split, and its duration happened to be shorter than censored comparisons with lower hazard scores.

---

### 1.2 Hedonic GBDT Pricing Model (`HedonicPricingModel`)
- **Architecture**: Pure Python Gradient Boosted Decision Tree (GBDT) with 25 estimators, depth 3, and Tree SHAP decomposition (`analytics/ml_pricing.py:193-364`).
- **Population**: 1,079,899 booked unit transactions with `rate_per_sqft > 0` joined against `projects` and `promoters`.
- **Target Distribution**: Unit rate/sqft: p1=₹333.1, p5=₹1,077.8, p25=₹2,541.4, p50=₹3,649.3, p75=₹5,136.6, p95=₹8,981.6, p99=₹14,008.2, max=₹2,521,376.3/sqft.

#### Empirical Scaling & Performance Metrics

| Training Configuration | Train Time | Peak RAM | MAE | RMSE | MAPE | $R^2$ Variance Explained |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **$N = 1,000$ sample** | 4.94s | 0.35 MB | — | — | — | — |
| **$N = 2,000$ sample** | 16.61s | 0.82 MB | — | — | — | — |
| **$N = 5,000$ sample** | 59.36s | 1.73 MB | — | — | — | — |
| **$N = 10,000$ sample** | 131.26s | 3.31 MB | — | — | — | — |
| **80/20 Holdout ($N=10,000$)** | **57.90s** | **2.64 MB** | **₹1,360.16/sqft** | **₹1,997.87/sqft** | **63.63%** | **0.3654** |
| **Full DB ($N=1,079,899$)** | **~3.93 hours (extrap.)** | **~480 MB** | — | — | — | Blocked by runtime timeout |
| **Offline Serialized JSON** | **27,546 bytes (26.9 KB)** | 25 trees, depth 3, feature splits & expectations | `ml_pricing.py:273-324` |

#### Feature Sparsity & Encoding Defects (`ml_pricing.py:227-244`)
- **`asset_Retail`, `asset_Office`, `asset_Warehouse` (100.0% DEAD)**: Encoded via `"retail" in aclass.lower()`, `"office" in aclass.lower()`, etc. In `unit_transactions`, `asset_class` only contains `'Commercial'` (254,960 rows) and `'Residential'` (824,970 rows). Retail, office, and warehouse substrings never match, rendering these 3 binary features 0.0 across all 1.08M units.
- **`promoter_scale` (100.0% DEAD)**: Fetched from `promoters.total_projects_claimed`. Table `promoters` contains only 9 rows statewide; joins produce NULL for 1,079,890 units, defaulting to 1.0.
- **`progress_pct` (99.90% DEAD)**: Non-zero for only 1,037 units (0.10%).
- **`velocity_ratio` (99.91% DEAD)**: Non-zero for only 937 units (0.09%).
- **District Bias**: Only `district_Ahmedabad` (32.89%) and `district_Gandhinagar` (10.70%) are encoded. The remaining 609,230 booked units (**56.42%**) across 31 other districts are collapsed into $(0, 0)$.

---

## 2. Discrepancy Engine Audit (`ProjectAuditor.audit_project()`)

Audited **200 projects** empirically: all 9 projects present in `finances` (pilot cohort) + 191 random statewide projects (`analytics/audit.py:10-413`).

### 2.1 Rule Coverage, Trigger, and Silent-Skip Census

| Audit Rule & Statutory Target | Triggered (%) | Clean (%) | Silently Skipped (%) | Root Cause of False Negatives / Failure Mode |
| :--- | :--- | :--- | :--- | :--- |
| **1. Cost Reversal Across Filings** | 2 (1.0%) | 7 (3.5%) | **191 (95.5%)** | Requires $\ge 2$ rows in `finances`. Only 9 projects have financial filings. |
| **2. Construction Velocity Deficit** | 2 (1.0%) | 6 (3.0%) | **192 (96.0%)** | Requires `velocity_ratio` and `time_elapsed_pct > 10%`. NULL in 17,778 rows. |
| **3. Escrow Liquidity Depletion** | 2 (1.0%) | 7 (3.5%) | **191 (95.5%)** | Requires `banks.closing_bal` and `engg_score_pct < 90%`. NULL statewide. |
| **3b. Sec 4(2)(l)(D) Over-Withdrawal** | 0 (0.0%) | 9 (4.5%) | **191 (95.5%)** | Requires `finances` row + `banks.withdrawal_amt > 0` + `progress_pct > 0`. |
| **4. Completion Expired w/o Form 4** | **123 (61.5%)** | 77 (38.5%) | 0 (0.0%) | 61.5% expired past 2026-10-15; Form 4 catalog has 0 statewide rows. |
| **5. Consumer Complaints Filed** | 4 (2.0%) | 196 (98.0%) | 0 (0.0%) | Evaluates `projects.complaints_count`. State column populated (4 non-zero). |
| **6. Layout Alterations (Sec 14)** | 2 (1.0%) | 198 (99.0%) | 0 (0.0%) | Evaluates `projects.alterations_count`. State column populated (2 non-zero). |
| **7. QPR Quarterly Defaults** | 3 (1.5%) | 197 (98.5%) | 0 (0.0%) | Evaluates `projects.default_quarters_count`. State column populated. |
| **8. Overdue Form 5 CA Audit** | 2 (1.0%) | 7 (3.5%) | **191 (95.5%)** | Table `form5_compliance` has only 39 rows across 9 projects. |
| **9. Institutional Loan Charge** | 0 (0.0%) | 9 (4.5%) | **191 (95.5%)** | Checked via `finances.loan_rows_count`. Missing in 17,778 projects. |
| **10a. Missing Signed Form 3 CA Doc**| 2 (1.0%) | 7 (3.5%) | **191 (95.5%)** | `has_financial_activity` requires non-zero `incurred_cost_inr` or `finances`. |
| **10b. Missing/Unverified Architect**| **200 (100.0%)**| 0 (0.0%) | 0 (0.0%) | `professionals` has only 8 architects statewide; 100% fail check. |
| **10c. Missing/Unverified Engineer** | 22 (11.0%) | 178 (89.0%) | 0 (0.0%) | Structural engineers are populated (15,557 rows); 89% clean pass. |

### 2.2 Statutory Section 4(2)(l)(D) Over-Withdrawal Formula Flaws (`audit.py:128-160`)
```python
# Production Code Formula:
allowed_withdrawal = est_cost * (progress_pct / 100.0)
if tot_withdrawn > allowed_withdrawal * 1.05:
    excess_cr = (tot_withdrawn - allowed_withdrawal) / 10_000_000.0
```
Empirical analysis against GujRERA statutory regulations reveals three fatal defects:
1. **Land Cost Conflation (False Positive Risk)**: Under RERA Section 4(2)(l)(D) and Form 3 guidelines, **Land Cost is 100% withdrawable upon expenditure**, irrespective of civil construction progress. On a ₹100 Cr project with ₹40 Cr land cost at 10% construction progress, legal allowable withdrawal is ₹40 Cr + 10% $\times$ ₹60 Cr = ₹46 Cr. The production formula allows only 10% $\times$ ₹100 Cr = ₹10 Cr, generating a **₹36 Cr false-positive statutory breach allegation**.
2. **Deposit Base Disregard**: Withdrawals from the separate account are capped by cumulative collections deposited (70% of receivables), not total estimated project cost.
3. **Multi-Account Non-Determinism**: `con.execute("... FROM banks WHERE project_id = ? AND account_type = 1").fetchone()`. In the 9 pilot projects, each project has **2 rows** with `account_type = 1` (one with withdrawal amount, one with `None`). Arbitrary `fetchone()` ordering leads to non-deterministic silent skips.

---

## 3. MCP Tool Payload Benchmarks (`mcp/server.py`)

Measured byte size and estimated token footprint (char_len / 4) across all 13 tools on Small Project 58 (Santorini Square, 1 unit), Large Township 7871 (Surat Diamond Bourse, 4,798 units), and Pilot Project 16562 (The Balcony, 252 units).

| MCP Tool Function (`mcp/server.py`) | Small (58) Bytes | Small Tokens | Large (7871) Bytes | Large Tokens | Pilot (16562) Bytes | Pilot Tokens | Flag >8k Tokens |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `get_project_dossier` | 3,526 B | 881 | 3,532 B | 883 | 6,433 B | 1,608 | Clean |
| `query_inventory_breakdown` | 2 B | 0 | 2 B | 0 | 487 B | 121 | Clean |
| `search_document_evidence` | 2 B | 0 | 2 B | 0 | 2 B | 0 | Clean (0 FTS rows) |
| `trace_entity_network` | **33,395 B** | **8,348** | **401,697 B** | **100,424** | **59,616 B** | **14,904** | **CRITICAL BLOWUP** |
| `audit_discrepancies` | 1,024 B | 256 | 1,024 B | 256 | 1,517 B | 379 | Clean |
| `get_escrow_health` | 465 B | 116 | 454 B | 113 | 1,497 B | 374 | Clean |
| `get_land_records` | 370 B | 92 | 1,677 B | 419 | 991 B | 247 | Clean |
| `get_regulatory_radar` | 362 B | 90 | 368 B | 92 | 963 B | 240 | Clean |
| `compare_projects` | 457 B | 114 | 465 B | 116 | 515 B | 128 | Clean |
| `predict_pricing_benchmark` | 573 B | 143 | 573 B | 143 | 573 B | 143 | Clean |
| `forecast_completion_delay` | 3,229 B | 807 | 3,234 B | 808 | 3,223 B | 805 | Clean |
| `calculate_escrow_runway` | 198 B | 49 | 202 B | 50 | 209 B | 52 | Clean |
| `get_spatial_density` | **73,006 B** | **18,251** | 17,759 B | 4,439 | **71,821 B** | **17,955** | **EXCEEDS 8k** |

### Root Cause of Payload Overflows
1. **`trace_entity_network` (100,424 tokens on Project 7871)**: Caused by a Knowledge Graph data defect (`graph_edges.dst_id`). In `data/intelligence.sqlite`, **17,778 of 17,787 projects point `DEVELOPED_BY` edges to `promoter:None`**. When `find_shared_entities()` traverses through `promoter:None`, it returns thousands of unrelated projects across Gujarat, exhausting the agent context window.
2. **`get_spatial_density` (18,251 tokens on Project 58 & 16562)**: `radius_km = 3.0` defaults in high-density urban corridors (Bodakdev, Kudasan) retrieve hundreds of projects with unpaginated nested metadata.

---

## 4. Personally Identifiable Information (PII) Audit

Audited all 18 tables, FastAPI routes (`api/index.py:48-636`), and MCP tools (`mcp/server.py:33-300`).

### 4.1 Sensitive Data Category Scan

| PII Data Category | Storage Location | Scan Finding | Exposure in API / MCP Server | Severity |
| :--- | :--- | :--- | :--- | :--- |
| **Bank Account Numbers** | `banks.account_number_masked` | **0 unmasked accounts**; 17,711 are 8-char (`****6485`), 27 are 4-char. | Masked correctly in `get_escrow_health()` & `/api/project/{pid}`. | Clean |
| **Allottee / Buyer Names** | `unit_transactions`, `applications` | **0 buyer names** present in database schema. | No allottee names exist to leak. | Clean |
| **Promoter / Individual PAN** | `professionals.license_or_reg_no` | **5 unmasked PAN numbers** entered by professionals as license IDs. | Leaked unmasked via `/api/project/{pid}`, `/api/graph`, `trace_entity_network`. | **HIGH** |
| **Personal Email Addresses** | `professionals.license_or_reg_no`, `professionals.name` | **4 personal emails** entered as license numbers or appended to names. | Leaked unmasked via `/api/project/{pid}`, `/api/graph`, `trace_entity_network`. | **HIGH** |
| **Phone / Mobile Numbers** | All tables | **0 unmasked 10-digit mobile numbers** detected in regex audit. | None detected. | Clean |

### 4.2 Exact Leaked PII Records in Production Database

| Table & Row ID | Project ID & Entity Name | Role | Leaked PII Value | Column Location | Exposed Endpoint / Tool |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `professionals:6483` | PR/GJ/.../0420: Dipaliben M. Desai | Engineer | **`[REDACTED-PAN]` (PAN Card)** | `license_or_reg_no` | `/api/project/420`, `trace_entity_network` |
| `professionals:597` | PR/GJ/.../3017: Setu Infrastructure | Engineer | **`[REDACTED-GSTIN]` (GSTIN/PAN)**| `license_or_reg_no` | `/api/project/3017`, `trace_entity_network` |
| `professionals:371` | PR/GJ/.../1467: Caes Consultants | Engineer | **`[REDACTED-REG]` (License/Reg)**| `license_or_reg_no` | `/api/project/1467`, `trace_entity_network` |
| `professionals:3889` | PR/GJ/.../23903: Sanjaykumar N Patel| Engineer | **`[REDACTED-EMAIL]`** | `license_or_reg_no` | `/api/project/23903`, `graph_nodes` |
| `professionals:4734` | PR/GJ/.../30775: Sanjaykumar N Patel| Engineer | **`[REDACTED-EMAIL]`** | `license_or_reg_no` | `/api/project/30775`, `graph_nodes` |
| `professionals:10841`| PR/GJ/.../3104: Jayesh A Dalal | Engineer | **`[REDACTED-EMAIL]`** | `license_or_reg_no` | `/api/project/3104`, `trace_entity_network` |
| `professionals:1002` | PR/GJ/.../5147: Paresh M Chavada | Engineer | **`[REDACTED-EMAIL]`** | `name` (concatenated) | `/api/project/5147`, `/api/graph` |
| `graph_nodes:21825` | `professional:engineer:dipaliben_m_desai`| Engineer | **`[REDACTED-PAN]` (PAN Card)** | `properties_json` | `/api/graph`, `trace_entity_network` |
| `graph_nodes:21826` | `professional:engineer:sanjaykumar...` | Engineer | **`[REDACTED-EMAIL]`** | `properties_json` | `/api/graph`, `trace_entity_network` |

---

## 5. Architecture, Turso/Vercel Bottlenecks & MCP Compliance

### 5.1 Turso & Vercel Serverless Bottlenecks (`db/database.py`)
1. **Schema Re-execution on Every Connection (`database.py:91, 102`)**:
   `get_connection()` calls `init_schema(con)` unconditionally. On Turso remote libSQL connections, every cold start executes `executescript()` creating 18+ tables and indexes across remote HTTP round-trips before answering a request.
2. **$N+1$ Sequential Query Waterfall in `get_project_detail()` (`db/queries.py:260-350`)**:
   Fetching a single project detail page issues **25 to 30 sequential SQL round-trips** (`projects`, `project_summaries`, `inventory_blocks`, `unit_transactions`, `quarterly_timeline`, `finances`, `professionals`, `banks`, `previous_projects`, `form5_compliance`, `noc_bu_records`, `applications`, and 10+ sub-queries in `auditor`). While in-process SQLite WAL executes this in ~1.5ms, on Turso over WAN (80-120ms RTT), this creates a **2.5 to 3.5 second latency waterfall**.

   *The 25-query waterfall executed sequentially on a single project page load*:
   1. SELECT * FROM projects WHERE project_id = ? (queries.py:260)
   2. SELECT * FROM project_summaries WHERE project_id = ? (queries.py:266)
   3. SELECT * FROM inventory_blocks WHERE project_id = ? (queries.py:280)
   4. SELECT block_name, count(*)... FROM unit_transactions GROUP BY block_name (fallback, queries.py:282)
   5. SELECT block_name, carpet_area_sqft... FROM unit_transactions LIMIT 500 (queries.py:299)
   6. SELECT * FROM quarterly_timeline WHERE project_id = ? (queries.py:305)
   7. SELECT * FROM finances WHERE project_id = ? (queries.py:306)
   8. SELECT role, name, firm_name... FROM professionals WHERE project_id = ? (queries.py:307)
   9. SELECT * FROM banks WHERE project_id = ? ORDER BY account_type (queries.py:308)
   10. SELECT linked_project_name... FROM previous_projects (queries.py:309)
   11. SELECT * FROM form5_compliance WHERE project_id = ? (queries.py:313)
   12. SELECT * FROM noc_bu_records WHERE project_id = ? (queries.py:314)
   13. SELECT apply_date, approval_date FROM applications (queries.py:343)
   14. SELECT COUNT(*) FROM finances WHERE filing_date IS NOT NULL (queries.py:347)
   15-24. In ProjectAuditor.audit_project(pid): 10 separate queries against inances, anks, documents_catalog, orm5_compliance, and professionals (udit.py:19-331).
   25. In KnowledgeGraph.trace_contagion_risk(pid): Recursive edge traversal (queries.py:339).

3. **FTS5 Virtual Table Support (`db/fts.py` vs `db/database.py`)**:
   `init_schema()` in `database.py` never initializes `document_fts`. In `data/intelligence.sqlite`, `document_fts` has **0 rows** and all 789 `document_jobs` remain in `PENDING` status.
4. **Lazy Training Serverless Crash (`mcp/server.py:239-242`)**:
   Cold calls to `predict_pricing_benchmark()` invoke `HedonicPricingModel.train_from_db(self.con)`. Training on 1.08M units in pure Python takes **~3.9 hours**, immediately hitting Vercel's 10s (Hobby) or 60s (Pro) execution timeout.

### 5.2 MCP SDK & Protocol Compliance Audit
- **Official SDK Absence**: The official `mcp` SDK (`mcp>=1.0.0`) is **NOT installed** in `.venv` (`ImportError: No module named 'mcp'`).
- **Dependency Missing**: `pyproject.toml` contains only `fastapi`, `uvicorn`, `libsql`, `pypdf`. Neither `mcp` nor `fastmcp` is declared.
- **Protocol Non-Compliance**: `RealEstateIntelligenceMCP` in `mcp/server.py` is a standard Python utility class. It implements:
  - **No `FastMCP` server wrapper**.
  - **No `stdio` transport** for desktop AI clients (Claude Desktop, Antigravity, Cursor).
  - **No SSE / Streamable HTTP `/mcp` transport**.
  - **No JSON-RPC 2.0 message handling**.

---

## 6. Summary Audit Metrics Matrix

| Component / Subsystem | Primary Metric | Baseline / Observed Value | Target / Health Benchmark | Audit Status |
| :--- | :--- | :--- | :--- | :--- |
| **Pricing Model ($N=10k$)** | $R^2$ / RMSE | $R^2 = 0.3654$ \| RMSE = ₹1,997/sqft | $R^2 > 0.80$ \| RMSE < ₹1,000 | **DEFICIENT** |
| **Survival Model Data** | Censored Rate | **99.98% (4 events / 17,787 rows)** | Event rate > 20% | **DATA HOLLOW** |
| **Discrepancy Engine** | False Negative Rate | **95.5% silent skip** on 7 of 10 rules | < 5% unhandled skips | **HOLLOW LAKE** |
| **Discrepancy Formula** | Sec 4(2)(l)(D) False Pos. | Up to 100% of land cost misattributed | Land cost excluded from civil % | **FLAWED FORMULA** |
| **MCP Payload Scale** | `trace_entity_network` | **100,424 tokens** (Project 7871) | < 8,000 tokens | **CRITICAL OVERFLOW** |
| **MCP Payload Scale** | `get_spatial_density` | **18,251 tokens** (Project 58) | < 8,000 tokens | **OVERFLOW** |
| **PII Protection** | Bank Accounts | **100% masked** (`****XXXX`) | 100% masked | **PASSED** |
| **PII Protection** | Developer Licenses | **5 PANs + 4 Emails leaked unmasked** | 0 unmasked PII | **FAILED** |
| **Turso / Vercel** | Project Detail Queries | **25-30 sequential SQL round-trips** | < 3 aggregated queries | **LATENCY RISK** |
| **MCP Architecture** | Protocol Compliance | Plain Python class (0 stdio / 0 SSE) | FastMCP with stdio & HTTP `/mcp` | **NON-COMPLIANT** |
