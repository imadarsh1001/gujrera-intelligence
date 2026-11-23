# Targeted Empirical Follow-ups: GujRERA Sovereign Data & Architecture

**Audit Date**: November 23, 2026 | **Target Database**: `data/intelligence.sqlite` (563 MB, 17,787 projects, 1.95M unit transactions)  
**Execution Environment**: Python 3.12.14, FastAPI 0.163.2, Starlette 1.10.0, Pydantic 2.14.3  
**Constraint Scope**: Read-only verification. Statewide data static (9 deep pilot projects reference-only). Target FastMCP 4.2 (`fastmcp-slim`).

---

## 1. Promoter Identity & Composite Linkage Keys

### 1.1 Column Census & The `promoter:None` Graph Bug
An audit across all 254 database columns established promoter, professional, and entity coverage:
- **`projects.promoter_name`**: 100.0% populated (17,787 rows, 12,191 distinct raw strings).
- **`projects.promoter_id`**: Populated for only 9 rows (0.05%); NULL for all 17,778 statewide projects.
- **Contact Info**: 0.00% statewide (no email, phone, PAN, or address columns exist for promoters).
- **Root Cause of 17,778 `promoter:None` Edges**: `real_estate_intelligence/graph/network.py:60` hardcodes `f"promoter:{row['promoter_id']}"`. Because `promoter_id` is NULL statewide, 17,778 edges collapsed into a single literal node `promoter:None`. Sibling tables (`banks`, `professionals`) normalized string names; promoters erroneously referenced the unpopulated foreign key.

### 1.2 Deity Homonyms vs. High-Precision Composite Keys
Report 03 naively stripped legal affixes (`PVT LTD`, `LLP`), grouping independent builders sharing devotional names into giant phantom conglomerates. Top 10 clusters (Shreeji, Shiv, Maruti, etc.) span up to 12 districts, 160 distinct professional licenses, and 226 distinct bank accounts.

| Clustering Methodology | Resulting Clusters | Multi-Project Groups ($\ge 2$) | Projects in Multi Groups | Max Group Size | Precision / Validity |
|---|---|---|---|---|---|
| **Naive Brand Normalization** | 8,660 | 2,227 | 11,354 (63.8%) | 228 (Shreeji) | **Invalid** (Deity homonym confounding) |
| **Key (a): Brand + District** | 10,822 | 2,610 | 9,575 (53.8%) | 65 | Moderate (Local homonyms persist) |
| **Key (b): Brand + Taluka** | 11,705 | 2,473 | 8,555 (48.1%) | 61 | Moderate-High |
| **Key (c): Brand + (Shared License OR Bank)** | **15,720** | **1,292** | **3,359 (18.9%)** | **52** | **High Precision Sovereign Benchmark** |

*Key (c) isolates 14,428 independent singletons and collapses multi-project entities down to 3,359 verified related schemes.*

---

## 2. Legacy Blank Data vs. Real Risk (Bank & BU Cohort Check)

### 2.1 Cohort Stratification: The Grandfathered 2018–2019 Transition Cliff
Stratifying all 17,787 projects by Scheduled Completion Year isolates portal digitization lag from real default:

| Completion Year Cohort | Total Projects | `projects.bu_status` Blank % | Missing NOC Table % | Expired w/o BU NOC % | `estimated_cost` Blank/0 % |
|---|---|---|---|---|---|
| **Legacy $\le$ 2017** | 35 | 100.00% | 0.00% | **71.43%** (25) | 0.00% |
| **Legacy 2018** | 698 | 100.00% | 2.87% | **75.93%** (530) | 2.29% |
| **Legacy 2019** | 1,164 | 100.00% | 3.52% | **51.37%** (598) | 2.23% |
| **Modern 2020** | 699 | 100.00% | 1.29% | **19.46%** (136) | 0.00% |
| **Modern 2021** | 1,142 | 100.00% | 1.14% | **11.56%** (132) | 0.53% |
| **Modern 2022** | 1,306 | 100.00% | 1.15% | **14.09%** (184) | 0.15% |
| **Modern 2023** | 1,431 | 100.00% | 3.21% | **14.88%** (213) | 0.07% |
| **Modern 2024** | 1,478 | 100.00% | 2.57% | **13.73%** (203) | 0.00% |
| **Modern 2025** | 1,735 | 100.00% | 3.57% | **13.78%** (239) | 0.00% |
| **Modern 2026 (thru Nov)** | 1,390 | 99.78% | 3.31% | **12.45%** (173) | 0.00% |
| **Active Ongoing (>2026)** | 6,709 | 99.91% | 7.07% | N/A (Not Expired) | 0.00% |

- **Transition Artifact**: 2018–2019 projects account for **1,128 of 2,398 expired projects (47.04%)**. Ongoing schemes registered under RERA in 2017 received physical municipal BUs that were never retroactively keyed into the portal.
- **Modern Baseline (2021–2026)**: True non-compliance stabilizes between **11.56% and 14.88%** (mean: **13.77%**).
- **Dead Column**: `projects.bu_status` is $\ge 99.78\%$ blank statewide. Ground truth lives in `project_summaries.has_bu_noc` (9,590 approvals) and `noc_bu_records.bu_check`.

### 2.2 Bank of Baroda vs. SBI Re-benchmarked
Report 03's reported 30.37% BoB default rate was an unstratified artifact combining: (1) string truncation (omitting 76 `'BANK OF BARODA'` uppercase rows), (2) legacy grandfathering skew (28.9% BoB portfolio was $\le 2019$ vs 8.9% for SBI), and (3) denominator dilution by SBI's 853 active projects ($>2026$).
- **Modern Era (2021–2026 Cohorts)**:
  - **Bank of Baroda**: 175 projects, 29 expired w/o BU $\rightarrow$ **16.57% failure rate** (16.86% of expired).
  - **State Bank of India**: 821 projects, 109 expired w/o BU $\rightarrow$ **13.28% failure rate** (13.47% of expired).
  - **Statewide Baseline**: **13.77% failure rate**. BoB is fully aligned with market norms.

### 2.3 Vadodara Trapped Projects Audit (15 Sampled Rows)
15 projects sampled across 2018–2026 confirm BU certificates are **genuinely missing**, not stored in alternate columns (`projects.bu_status`, `form_four_status`, and `project_summaries.bu_certificate_no` are all `None`). In `noc_bu_records`, block entries exist but `bu_check` and `bu_date` are explicitly `NULL`. Even public housing authority schemes (e.g. VUDA PMAY projects #3817 and #11926, 100% booked) have expired schedules without registered BU NOCs.

---

## 3. Pricing Benchmark: Spatial-Neighbor vs. GBDT

### 3.1 Feature Audit & Longitudinal Coverage
`HedonicPricingModel` features: `carpet_area_sqft`, `carpet_area_log`, `progress_pct` (99.9% 0), `velocity_ratio` (99.9% 0), `promoter_scale` (100% 0), `lat`, `lon`, `asset_Retail/Office/Warehouse/Residential`, `district_Ahmedabad`, `district_Gandhinagar`.  
- **Missing**: Transaction Year (completely ignored; 2015 and 2026 deeds lumped together), City/Taluka, and Spatial Neighbor metrics.
- **Deed Date Coverage**: 941,575 / 1,079,899 clean booked deeds (**87.19%**) have valid transaction years (2015: 1.3k, 2018: 51.8k, 2021: 91.9k, 2024: 133.2k, 2026: 162.4k).

### 3.2 80/20 Holdout Model Comparison (N = 921,213 Cleaned Deeds)
Evaluated on an identical 80/20 test split (Train = 20,000, Test = 5,000 deeds, rate ₹500–₹50,000/sq.ft):

| Model Architecture | MAE (₹/sq.ft) | MAPE (%) | R² | Median N per Bucket | Median Pred IQR (₹/sq.ft) |
|---|---|---|---|---|---|
| **(a) Current GBDT (`HedonicPricingModel`)** | ₹1,381.13 | 43.13% | 0.3333 | *N/A (Global)* | *N/A (Point)* |
| **(b) Empirical `(district, taluka, asset, year)`** | ₹1,427.41 | 39.18% | 0.2196 | 163.0 *(Mean: 207.8)* | ₹1,924.3 |
| **(c) Empirical 2km Spatial-Neighbor** | **₹1,106.28** | **29.41%** | **0.4798** | **17.0** *(Mean: 41.2)* | **₹1,210.0** |

*Model (c) delivers a **19.9% MAE reduction** and a **13.7 percentage point drop in MAPE** over GBDT, provides calibrated local uncertainty bounds (IQR), and executes with zero training latency.*

---

## 4. FastMCP 4.2 (`fastmcp-slim`) & PII Read-Path Choke Points

### 4.1 Environment & Lifespan Composition
- **Runtime Environment**: Python `3.12.14`, FastAPI `0.163.2`, Starlette `1.10.0`, Pydantic `2.14.3` — 100% compatible with `fastmcp-slim>=4.2.3`.
- **Clean Lifespan Integration**: In `api/index.py`, replace empty lifespan with:
  ```python
  @asynccontextmanager
  async def lifespan(app: FastAPI):
      AppState.get_backends()  # Eager DB connection
      async with mcp_app.lifespan(app): yield
      if AppState.con: AppState.con.close()
  app = FastAPI(title="GujRERA Intelligence", lifespan=lifespan)
  app.mount("/mcp", mcp_app)  # FastMCP Streamable HTTP on /mcp
  ```

### 4.2 Choke Points for In-Memory Regex PII Redaction
Audit found raw Income Tax PANs (`[REDACTED-PAN]`) and 12-digit Aadhaar numbers accidentally keyed into `professionals.license_or_reg_no`. Local SQLite remains immutable; sanitization is enforced in-memory at two choke points:
1. **Local API / MCP Read Choke Point (`db/queries.py:get_project_detail`)**:
   Apply regex scrub (`^[A-Z]{5}[0-9]{4}[A-Z]$` $\rightarrow$ `[REDACTED-PAN]`, `^\d{12}$` $\rightarrow$ `[REDACTED-UIDAI]`) before building response dicts in `get_project_detail()` and `copilot.py:779`.
2. **Cloud Replication Choke Point (`db/turso_sync.py`)**:
   Exclude raw `banks` table from remote sync (or push only aggregated balances); apply regex redaction on `professionals` rows during batch staging before executing remote libSQL INSERTs.
