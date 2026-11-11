# Statewide Data Audit — Download Gaps & Missing Details

* **Author:** Adarsh Patel
* **Date:** 2026-11-12 (rev. 2 — corrected the same day: the statewide Form 3 filings lake was initially overlooked; §3/§4/§6 re-baselined)
* **Scope:** The 17,634-project statewide collection vs. what the intelligence platform can actually use today. Read-only audit of `raw_data/`, `collected_data/`, `gujrera_pipeline/data/` (all gitignored); no PII values reproduced here.
* **Motivation:** Author decision of 2026-11-11 — statewide ingestion is deferred until "we check what's pending to download and some details are missing." This document is that check.

## 1. What exists

| Asset | Contents | Size |
|---|---|---|
| `raw_data/all_projects_111026.csv` | **Statewide registration index**: 17,634 unique projects × 30 columns (identity, name, address, district, type, status, dates, costs, promoter fields) | ~12 MB CSV |
| `raw_data/all_projects_*.csv` (5 more) | Earlier index snapshots (2023-12, 2024-06, 2024-10, 2025-03) — longitudinal drift available | ~2 MB each |
| `raw_data/failed_ids.csv` | 145 projects that failed an earlier download attempt | small |
| `collected_data/form_ids_2026-10-11_*.csv` (+ 1 older) | **Per-project form-ID map**: for every one of the 17,634 projects, the portal IDs needed to fetch Form 1/2/3, certificates, extension certificates | ~7 MB CSV |
| `gujrera_pipeline/data/indexes/*.parquet` | The same indexes as Parquet (11 files) incl. `failed_ids_2026-10-11` and `documents_manifest` | ~17 MB |
| `gujrera_pipeline/data/runs/nine_projects_2026_10_15` | **Deep capture of 9 projects**: ~43 endpoint files each (Forms 1/2/3 index+latest, banks, applications, locations, bookings, documents…) + documents + exports | 1.2 GB (incl. PDFs) |
| `gujrera_pipeline/data/filings/{snapshot}/part_*.parquet` | **Statewide Form 3 filings lake — the headline asset**: 16 partitions over 4 snapshots (2023-12-01, 2024-10-13, 2025-03-01, 2026-10-11); 58,741 rows covering **17,632 of 17,634 projects (99.99%)**; each row = one project × quarter × snapshot with the complete Form 3 payload in `raw_json` | 251 MB |
| `gujrera_pipeline/data/samples/{project}/` | Document bundles (PDFs) for the 9 deep-captured projects only | 1.4 GB |
| `gujrera_pipeline/data/runs/party_profiles_…`, `related_projects_…`, `pilot_…` | Small supplementary captures | < 4 MB total |
| `real_estate_intelligence/data/intelligence.sqlite` | Curated DB — currently the 9 deep-captured projects only | 4.8 MB |

### What the Form 3 filings lake already contains (per project × quarter × snapshot)

- `formThreeAList`: **block-level unit bookings** — blockName, usage (Residential/Shop/Office), carpetArea, status (BOOKED/…), unitConsideration, receivedAmount, balanceAmount → the raw material for Explore's price columns at statewide scale.
- Inventory summaries (`formThreeASummayList`, totals): booked/unbooked units, consideration totals, residential/shop/office counts.
- **`physicalProgressStatus` + `physicalProgressReason`** — a progress signal without needing the Form 1 detail fetch.
- **CA professional identity** (caName, caId, caFrnNo, caMemberShipNumber) — a new professional role for the knowledge graph.
- Land valuation (`formThreeBId`), submission quarters/dates, Form 3 PDF references.
- Caveat: this is the CA-certified quarterly snapshot per filing — agreement dates in `formThreeAList` are largely null at block level (the 9-project run's dated transactions came from the deeper index_form_three payload), so per-transaction agreement dates may still require the deep captures for the price-date columns.

## 2. Index coverage (17,634 projects)

Populated for **100% of projects**: projectRegId, projectName, project_address, districtName, projectType, project_status, startDate, endDate (format `31-December-2019`), regNo, promoterName, approvedOn, costs (17,583/17,634). No duplicate IDs.

Partial / empty:
- **`extDate` (extension date): 2,733 projects (15%)** — direct input for the completion-revision story at scale.
- **`disposed_date`: 0%** — column exists but is entirely empty.
- **No latitude/longitude columns** — the Explore map's pins currently come from per-project deep captures only.
- **Promoter PII present in the index**: `prmtr_adhaar_no`, `prmtr_pan_no`, `pr_mobile_no`, `pmtr_email_id`, `prmtr_com_reg_no`. ⚠️ These are portal-published fields, but per SPEC user story 27 (PII redaction) they must **never** flow into the public UI, exports, or model inputs. Any statewide ingestion must carry an explicit redaction list.

Status semantics caveat: `project_status` = New 14,238 / Ongoing 3,354 / Completed 42 — portal registration status, not construction stage; Explore filters should prefer deep-captured progress fields once available.

## 3. Download gap — corrected picture

| Layer | Status |
|---|---|
| Statewide registration index | ✅ Complete (17,634/17,634, refreshed 2026-10-11; 4 historical snapshots) |
| Per-project form-ID map | ✅ Complete — the "what to fetch" list is fully catalogued |
| **Form 3 (prices, bookings, inventory, CA, progress-status)** | ✅ **Statewide already collected — 17,632/17,634 (99.99%) across 4 snapshots** (251 MB, local; no fetching needed, only ingestion) |
| Form 1 (architect) + Form 2 (engineer) details | ❌ Pending per-project (IDs catalogued for 17,590/17,586 projects) |
| Banks / escrow passbooks | ❌ Pending per-project (not part of the Form 3 payload) |
| Applications / case records | ❌ Pending per-project (82 rows exist for the 9 deep projects) |
| Locations / GPS | ❌ Pending per-project (9 captured) or geocoding decision |
| Documents (PDFs) | ❌ Phase-2 on-demand; 9 projects bundled so far |

Form-ID availability for the pending fetches:
- **17,580 projects (99.7%) have ALL of Form 1 + 2 + 3 IDs**; 44 have none; 54 missing at least one core form.
- Extension certificates: 918 projects have an `extcertificateId` (vs 2,733 with `extDate` in the index — reconcile during ingestion).
- `failed_ids` (145) are stale: sampled projects now have full core-form IDs — retry them in the first batch.

**Bottom line:** the most valuable dataset — sworn Form 3 prices and inventory — is already downloaded for the whole state. The remaining portal fetching is Form 1/2 details, banks, applications, and locations: ~4–6 endpoint families × 17,634 projects rather than the full ~43-endpoint capture, i.e. roughly a quarter of the originally-estimated request volume.

## 4. Ingestion plan (revised)

**Phase A — local ETL, no portal fetching (unlocks statewide Explore immediately):**
Ingest the filings lake into the curated database: expand `raw_json` into `unit_transactions` / inventory summaries / CA professionals / progress-status tables keyed by `snapshot_date` + `quarter`. This makes Explore statewide for price, budget, inventory, district, type, completion-window, and CA-professional dimensions — and populates the local-price benchmark groups the review gated. Engineering estimate: a new filings-lake ingestion path (the existing loader reads RunReader snapshots, not the lake schema) — local work, a few days.

**Phase B — targeted portal fetching (batched, resumable):**
- `locations` for all projects (small payloads; unlocks map pins statewide) **or** geocode addresses — decide first.
- Form 1 + Form 2 details (progress %, engineer data) — ~2 requests/project.
- `all_applications` (case/extension records) — 1 request/project.
- Banks (escrow) — where the run schema sourced them.
At ~4–6 requests × 17,634 ≈ 70–105k requests — days, not weeks, batched by district.

**Phase C — documents (unchanged):** Phase-2 on-demand PDFs stay selective.

## 5. What the statewide data unlocks vs. what stays blocked

**Unlocked right now by Phase A (filings-lake ingestion, no fetching):**
- Explore at real scale: district (33), type, budget fit (index costs + Form 3 considerations), completion window (endDate 100%), inventory/booking metrics, CA-professional dimension.
- Local price benchmarks per district+type+unit-type — the review-gated summary becomes computable with real groups (hundreds of comparable projects per district).
- Scenario 2 goes **live**: South Bopal (83) and Shela (98) projects exist with addresses; Form 3 gives their unit-level pricing.
- Longitudinal Form 3 drift across the 4 snapshots (booking absorption trends).

**Still blocked until Phase B fetches:**
- **GPS pins for the map** — locations endpoint or geocoding (decision pending).
- Construction-stage percentages from Form 1 (a coarse proxy exists in Form 3's `physicalProgressStatus`), engineer data from Form 2.
- Escrow/bank passbook analytics, applications/case records, documents/FTS.

**Missing details to reconcile during ingestion:**
- `extDate` (2,733) vs `extcertificateId` (918) mismatch.
- `disposed_date` always empty — drop or investigate.
- `project_status` semantics ("New" ≠ construction stage).
- PII redaction list enforcement at the loader/export boundary (Aadhaar/PAN/mobile/email are in the index).

## 6. Recommendation

Start with **Phase A now**: it is pure local ETL over a complete, already-downloaded dataset and turns Explore into a statewide product this week. Phase B's portal fetching (Form 1/2, banks, applications, locations) follows in district batches; decide the GPS strategy (locations endpoint vs geocoding) before starting it. The form-ID catalogue being 100% complete means no discovery work remains for any of it.
