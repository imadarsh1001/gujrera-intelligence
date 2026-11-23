# GujRERA Database Empirical Data Coverage Report

**Database**: `data/intelligence.sqlite` (SQLite 3)  
**Total Projects Universe**: 17,787 distinct `project_id`s in `projects`  
**Dual-Tier Architecture Definition**: `real_estate_intelligence/real_estate_intelligence/db/statewide_loader.py:8,34` (`DEEP_AUDIT_IDS = [13560, 13705, 16104, 16562, 17255, 17830, 17855, 20523, 24508]`)

---

## 1. Table & Project Coverage Census (All 27 Objects)

Evaluated empirically against `data/intelligence.sqlite` (excluding SQLite internal tables `sqlite_sequence` and `sqlite_stat1`).

| Object Name | Type | Row Count | Distinct `project_id` | % Projects (17,787) | Primary Date Range |
|---|---|---:|---:|---:|---|
| `projects` | table | 17,787 | 17,787 | 100.00% | `start_date`: 2005-04-01 to 2026-10-14; `completion_date`: 2017-09-30 to 2036-10-30 |
| `v_current_projects` | view | 17,787 | 17,787 | 100.00% | `start_date`: 2005-04-01 to 2026-10-14; `completion_date`: 2017-09-30 to 2036-10-30 |
| `project_summaries` | table | 17,787 | 17,787 | 100.00% | `completion_date`: 2017-09-30 to 2036-10-30 |
| `banks` | table | 17,739 | 17,721 | 99.63% | `opening_date`: 2024-05-31 to 2025-09-30; `closing_date`: 2024-08-31 to 2026-04-30 |
| `noc_bu_records` | table | 46,931 | 17,027 | 95.73% | `bu_date`: 0001-01-01 to 2026-10-29 (6 rows corrupt `00xx`) |
| `unit_transactions` | table | 1,952,528 | 16,472 | 92.61% | `agreement_date`: 0022-09-16 to 2026-11-12 (1 row corrupt `0022`) |
| `v_current_unit_transactions` | view | 1,952,528 | 16,472 | 92.61% | `agreement_date`: 0022-09-16 to 2026-11-12 |
| `professionals` | table | 15,565 | 15,472 | 86.98% | None (Metadata records only) |
| `graph_nodes` | table | 21,836 | 17,787 | 100.00% | None (17,787 Project, 3,873 Engineer, 151 Bank, 9 Promoter, 9 PriorProject, 7 Architect) |
| `graph_edges` | table | 51,069 | 17,787 | 100.00% | None (17,787 DEVELOPED_BY, 17,721 ESCROW_AT, 15,544 ENGINEERED_BY, 8 DESIGNED_BY, 9 PRIOR_PORTFOLIO) |
| `document_jobs` | table | 789 | 9 | 0.05% | `created_at_utc`: 2026-11-20 21:57:12; `completed_at_utc`: NULL (100% PENDING) |
| `documents_catalog` | table | 789 | 9 | 0.05% | None (Relative path catalog) |
| `quarterly_timeline` | table | 94 | 9 | 0.05% | `submission_date`: 100% NULL |
| `applications` | table | 82 | 9 | 0.05% | `apply_date`: 044989 to 2026-06-11; `approval_date`: 2022-02-15 to 2026-02-19 |
| `form5_compliance` | table | 39 | 9 | 0.05% | `financial_year`: 2021-22 to 2026-27 |
| `inventory_blocks` | table | 22 | 9 | 0.05% | None |
| `finances` | table | 18 | 9 | 0.05% | `filing_date`: 2025-07-03 to 2026-10-07 |
| `previous_projects` | table | 18 | 9 | 0.05% | `completion_year`: 100% NULL |
| `promoters` | table | 9 | 9 (promoters) | 0.05% | None |
| `document_fts` | table | 0 | 0 | 0.00% | None (FTS5 virtual table empty) |
| `document_fts_config` | table | 1 | N/A | N/A | FTS shadow configuration table |
| `document_fts_content` | table | 0 | N/A | N/A | FTS shadow content table |
| `document_fts_data` | table | 2 | N/A | N/A | FTS shadow data index table |
| `document_fts_docsize` | table | 0 | N/A | N/A | FTS shadow docsize table |
| `document_fts_idx` | table | 0 | N/A | N/A | FTS shadow segment index table |
| `copilot_embeddings` | table | 0 | 0 | 0.00% | None |
| `market_listings` | table | 0 | 0 | 0.00% | None |

---

## 2. Root Cause Analysis: Tiny Tables (0.05% Coverage)

### Populated Project IDs
All tiny tables (`applications`, `documents_catalog`, `document_jobs`, `finances`, `form5_compliance`, `inventory_blocks`, `previous_projects`, `promoters`, `quarterly_timeline`) share the exact same 9 project IDs:
`[13560, 13705, 16104, 16562, 17255, 17830, 17855, 20523, 24508]`.

| `project_id` | Project Name | RERA Registration Number | District | `has_deep_filings` | `tier` |
|---:|---|---|---|:---:|---|
| 13560 | Skydeck Serene | PR/GJ/AHMEDABAD/SANAND/AUDA/RAA09818/EX1/030925/310326 | Ahmedabad | 1 | deep_audit |
| 13705 | THE GATE BY DEV AASHISH | PR/GJ/GANDHINAGAR/GANDHINAGAR/Others/MAA09811/A1M/020523 | Gandhinagar | 1 | deep_audit |
| 16104 | VRUNDAVAN ELYSIA | PR/GJ/GANDHINAGAR/GANDHINAGAR/GUDA/RN234AA10134/211022 | Gandhinagar | 1 | deep_audit |
| 16562 | THE BALCONY | PR/GJ/GANDHINAGAR/GANDHINAGAR/GMC/MN365AA10265/191023 | Gandhinagar | 1 | deep_audit |
| 17255 | ATMOS BY SOLAIRE | PR/GJ/GANDHINAGAR/GANDHINAGAR/Others/MAA10279/EX1/130825/250626 | Gandhinagar | 1 | deep_audit |
| 17830 | SANDALWOOD | PR/GJ/GANDHINAGAR/GANDHINAGAR/Others/RAA10740/A1R/050723 | Gandhinagar | 1 | deep_audit |
| 17855 | PROVINCE | PR/GJ/GANDHINAGAR/GANDHINAGAR/Others/MAA10775/141022 | Gandhinagar | 1 | deep_audit |
| 20523 | PRAMUKH PENTAGON | PR/GJ/GANDHINAGAR/GANDHINAGAR/GMC/MAA13104/070324/311228 | Gandhinagar | 1 | deep_audit |
| 24508 | REVANTA FORTUNE 3 | PR/GJ/GANDHINAGAR/GANDHINAGAR/GMC/MAA14344/281024/311229 | Gandhinagar | 1 | deep_audit |

### Empirical Cause & Data Seam
1. **Source Seeding (`loader.py:1-643`)**: During Step A (`statewide_loader.py:311-316`), `DiskRunReader` seeded only the 9 projects residing in `../gujrera_pipeline/data/runs/nine_projects_2026_10_15/raw/projects/`. These 9 had full document and quarterly JSON archives (`all_data.json.gz`, `all_applications.json.gz`, `annual_compliance.json.gz`, `banks.json.gz`).
2. **Statewide Lake Omission (`statewide_loader.py:320-730`)**: The statewide data lake at `../gujrera_pipeline/data/` comprises `indexes/` (master projects), `governance/` (bank accounts, BU NOCs, project details), `discovery/` (engineers), and `form3/` (unit transactions). The pipeline **never scraped or extracted** Form 1 (architect quarterly), Form 2 (engineer quarterly), Form 5 (annual audit), promoter profiles, or applications statewide.
3. **Field Distribution in `projects` vs. `project_summaries`**:
   - `projects.incurred_cost_inr`: Populated for only 9 projects (0.05%); 17,778 are NULL (`statewide_loader.py:396-415` excludes `incurred_cost_inr`).
   - `projects.total_units` / `booked_units`: Populated for only 9 projects (0.05%) in `projects`.
   - `project_summaries.total_units` / `booked_units` / `absorption_pct`: Populated for **16,468 projects (92.58%)** via dynamic aggregation from `unit_transactions` (`statewide_loader.py:768-771`).
   - `project_summaries.ca_name`: 100% NULL across all 17,787 projects (`statewide_loader.py:782` hardcodes `None`).
   - `project_summaries.architect_names`: Populated for only 8 projects (0.045%); 17,779 are NULL.
   - `project_summaries.engineer_names`: Populated for 15,469 projects (86.97%) from governance parquet.

---

## 3. Deep-Dive: `banks` Table (17,739 Rows)

### Distribution & Double Counting Analysis
- **Row Count**: 17,739 rows across 17,721 distinct `project_id`s.
- **Rows per Project Distribution**:
  - `min`: 1
  - `p25`: 1.0
  - `p50` (median): 1.0
  - `p75`: 1.0
  - `p95`: 1.0
  - `max`: 3
  - **Count breakdown**: Exactly 17,712 projects have 1 row; exactly 9 projects have 3 rows.
- **Account Type Split**:
  - `account_type = 1` (Escrow / Designated): 17,730 rows (17,721 distinct projects).
  - `account_type = 2` (Collection): 9 rows (9 distinct projects, exactly the 9 `deep_audit` projects).
- **The 9 Multi-Row Projects**:
  For each of the 9 `deep_audit` projects, 3 rows exist:
  1. `loader.py:345`: `account_type = 1` with financial balances and passbook IDs.
  2. `loader.py:377`: `account_type = 2` collection account.
  3. `statewide_loader.py:476`: Governance lake upsert inserted a redundant 3rd row with `account_type = 1` and all balance columns NULL.
- **Double Counting Risk & Multi-Quarter History**:
  - `banks` does **NOT** store multi-quarter time series. All date intervals represent a single snapshot filing.
  - Across all 17,739 rows, there are only 18 distinct `passbook_id`s, 17 distinct `opening_date`s, and 11 distinct `closing_date`s.
  - Double counting is severe if querying `SUM(closing_bal)` without filtering: the 9 deep audit projects contain both account_type 1 and account_type 2 entries.

### Field Hygiene & Null Rates (17,739 Total Rows)
| Column | Non-Null Count | Non-Null % | Non-Zero Count | Non-Zero % | Zero Count | Zero % | Null Count | Null % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `bank_name` | 17,739 | 100.00% | 17,739 | 100.00% | 0 | 0.00% | 0 | 0.00% |
| `branch_name` | 17,738 | 99.99% | 17,738 | 99.99% | 0 | 0.00% | 1 | 0.01% |
| `ifsc_code` | 17,739 | 100.00% | 17,739 | 100.00% | 0 | 0.00% | 0 | 0.00% |
| `account_number_masked`| 17,739 | 100.00% | 17,739 | 100.00% | 0 | 0.00% | 0 | 0.00% |
| `account_type` | 17,739 | 100.00% | 17,739 | 100.00% | 0 | 0.00% | 0 | 0.00% |
| `closing_bal` | 12 | 0.07% | 8 | 0.05% | 4 | 0.02% | 17,727 | 99.93% |
| `deposit_amt` | 9 | 0.05% | 9 | 0.05% | 0 | 0.00% | 17,730 | 99.95% |
| `withdrawal_amt` | 9 | 0.05% | 9 | 0.05% | 0 | 0.00% | 17,730 | 99.95% |
| `opening_bal` | 9 | 0.05% | 6 | 0.03% | 3 | 0.02% | 17,730 | 99.95% |

---

## 4. Hygiene Audit: `unit_transactions` (1.95M Rows)

### Booked vs. Unbooked Distribution
- **Total Rows**: 1,952,528 across 16,472 distinct projects.
- **Booked Rows**: 1,093,866 (56.02%).
- **Unbooked Rows**: 858,662 (43.98%).
- **Asset Classes**:
  - `Residential`: 1,357,298 rows (835,502 booked, 521,796 unbooked).
  - `Commercial`: 595,230 rows (258,364 booked, 336,866 unbooked).
- **Parking Units**: Exactly 0 rows contain "park" in `unit_type` or `asset_class`. Parking is uninventoried.

### Booked Units Hygiene Breakdown (1,093,866 Rows)
- **Carpet Area (sqft & sqm)**: 1,093,866 rows (100.00%) have valid non-zero carpet area. 0 nulls, 0 zeros.
- **Unit Consideration**: 1,082,119 rows (98.93%) have non-zero consideration; 11,747 rows (1.07%) are zero or NULL.
- **Rate per Sqft**: 1,079,930 rows (98.73%) have non-zero rate/sqft; 13,936 rows (1.27%) are zero or NULL.
- **Agreement Date**:
  - Valid date (`YYYY-MM-DD`): 954,954 rows (87.30%).
  - Null or empty: 138,911 rows (12.70%).
  - Corrupt century prefix (`0022-09-16`): 1 row (0.00009%).

### Sq.mt vs. Sq.ft Unit Mixing Verification
- **Area Ratio (`carpet_area_sqft / carpet_area_sqm`)**:
  - Evaluated on all 1,952,528 rows.
  - Min ratio: `10.760000`, Max ratio: `10.765957`.
  - Exactly 1,952,528 rows (100.00%) match the metric conversion factor ($\approx 10.76391$) within 0.1 tolerance.
  - Direct 1:1 mixing (where sqft was copied into sqm): **0 rows**.
- **Rate Ratio (`rate_per_sqm / rate_per_sqft`)**:
  - Evaluated on 1,938,371 rows where both rates exist.
  - 1,938,191 rows (99.99%) have exact metric conversion; 0 rows have direct 1:1 mixing.

### Percentile Distribution: Booked Units
Computed on booked transactions with non-zero values (`real_estate_intelligence/real_estate_intelligence/analytics/pricing.py:45-120`):

| Metric | Min | p1 | p5 | p25 | p50 (Median) | p75 | p95 | p99 | Max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Carpet Area (sqft)** | 10.76 | 144.34 | 215.60 | 419.15 | 627.86 | 868.86 | 1,700.70 | 3,137.68 | 7,723,098.25 |
| **Rate / Sqft (INR)** | 0.01 | 333.13 | 1,077.77 | 2,541.38 | 3,649.26 | 5,136.59 | 8,981.65 | 14,008.16 | 2,521,376.27 |
| **Consideration (INR)** | 1.00 | 259,400 | 447,600 | 1,236,000 | 2,205,000 | 3,800,000 | 9,030,000 | 20,000,000 | 2,062,637,072 |

*Outlier Census*: Booked area < 50 sqft: 128 rows (0.012%); area > 10,000 sqft: 1,207 rows (0.11%). Rate < 100 INR/sqft: 3,017 rows (0.28%); rate > 100,000 INR/sqft: 51 rows (0.005%).

---

## 5. Governance & Network Coverage

### `noc_bu_records` (46,931 Rows, 17,027 Projects, 95.73% Coverage)
- `block_name`: 46,931 non-null (100.00%).
- `bu_check`: 26,293 non-null (56.02%); 20,638 null (43.98%).
- `bu_date`: 26,096 non-null (55.61%); 20,835 null (44.39%); 6 corrupt values (`0001-01-01` to `0020-03-24`).
- `fire_doc_id`: 12,448 non-null (26.52%); 34,483 null (73.48%).
- `lift_doc_id`: 11,228 non-null (23.92%); 35,703 null (76.08%).

### `professionals` (15,565 Rows, 15,472 Projects, 86.98% Coverage)
- `role`: 15,557 `engineer` (99.95%), 8 `architect` (0.05%, deep audit only). Zero CA or contractor records.
- `name`: 15,565 non-null (100.00%).
- `firm_name`: 15,565 NULL (100.00% null rate across entire table).
- `license_or_reg_no`: 15,530 non-null (99.78%); 35 null (0.22%).

### `graph_nodes` (21,836 Rows) & `graph_edges` (51,069 Rows)
- **Node Kinds**: Project: 17,787 (81.46%); Engineer: 3,873 (17.74%); Bank: 151 (0.69%); Promoter: 9 (0.04%); PriorProject: 9 (0.04%); Architect: 7 (0.03%).
- **Edge Relations**: DEVELOPED_BY: 17,787; ESCROW_AT: 17,721; ENGINEERED_BY: 15,544; DESIGNED_BY: 8; PRIOR_PORTFOLIO: 9.
- **Dangling Edges Defect (`network.py:59-61`)**:
  - Exactly **17,778 `DEVELOPED_BY` edges** point to `dst_id = 'promoter:None'`, because `promoters` table only contains 9 rows and master `projects` has null `promoter_id` for statewide projects.
  - 7 dangling edges reference 4 external projects (`project:17985`, `project:22915`, `project:24230`, `project:30122`) present in governance lake but absent from `projects`.

---

## 6. Document & FTS Infrastructure Audit

Empirical verification of document pipeline (`loader.py:576-640` and `fts.py:1-92`):

| Component | Database Metric | Physical Disk Metric | Status & Diagnosis |
|---|---:|---:|---|
| `documents_catalog` | 789 rows (9 projects) | 789 PDFs in pipeline run folder | `file_path` contains relative path `raw/documents/by-content/...`. Resolves to 0 on workspace root, but 100% (789/789) exist in `../gujrera_pipeline/data/runs/nine_projects_2026_10_15/raw/documents/by-content/`. |
| `document_jobs` | 789 rows (9 projects) | 0 jobs completed | 100% (789/789) in `status = 'PENDING'`. `index_documents=False` was passed during ingestion (`loader.py:604`). |
| `document_fts` | 0 rows (0 projects) | 0 index entries | FTS5 virtual table is completely empty. `index_page_text()` was never invoked. |
| `copilot_embeddings` | 0 rows (0 projects) | 0 vectors | Table schema initialized (`database.py:461`), but zero embeddings generated. |

---

## 7. Statewide Coverage Tier Classification

Every table and feature partitioned by statewide project coverage ($N = 17,787$):

| Tier | Coverage Level | Entities & Tables | Usable Analytical Capabilities |
|---|---|---|---|
| **Tier 1** | **High Coverage**<br>(>70% statewide) | • `projects` / `v_current_projects` (100.0%)<br>• `project_summaries` (100.0%)<br>• `banks` (metadata only: 99.63%)<br>• `noc_bu_records` (95.73%)<br>• `unit_transactions` (92.61%)<br>• `professionals` (Engineers: 86.98%)<br>• `graph_nodes` (Project, Bank, Engineer: 100.0%) | • Statewide project GIS & delivery velocity<br>• Price-per-sqft benchmarks (1.95M units)<br>• Absorption & inventory health by micromarket<br>• BU permission compliance checking<br>• Escrow bank concentration & engineer networks |
| **Tier 2** | **Partial Coverage**<br>(10% to 70%) | • `noc_bu_records.fire_doc_id` (26.52%)<br>• `noc_bu_records.lift_doc_id` (23.92%)<br>• `unit_transactions.agreement_date` (48.91% of all units, 87.30% of booked units) | • Fire safety compliance subset sampling<br>• Vertical transit (lift) NOC tracking<br>• Historical transaction velocity estimation |
| **Tier 3** | **Sample Only**<br>(<10%, 9 Seed Projects: 0.05%) | • `quarterly_timeline` (9 projects, 0.05%)<br>• `applications` (9 projects, 0.05%)<br>• `form5_compliance` (9 projects, 0.05%)<br>• `inventory_blocks` (9 projects, 0.05%)<br>• `finances` (9 projects, 0.05%)<br>• `previous_projects` (9 projects, 0.05%)<br>• `promoters` (9 promoters, 0.05%)<br>• `documents_catalog` / `document_jobs` (0.05%)<br>• `banks` financial balances (`closing_bal`: 0.07%)<br>• `projects.incurred_cost_inr` (0.05%)<br>• `document_fts` / `copilot_embeddings` (0.00%) | • Deep forensic audit demonstration for the 9 pilot projects only (`DEEP_AUDIT_IDS`).<br>• Cannot be used for statewide queries, cross-developer debt checks, or automated PDF search. |
