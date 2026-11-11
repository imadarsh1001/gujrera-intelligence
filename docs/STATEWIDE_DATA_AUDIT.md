# Statewide Data Audit — Download Gaps & Missing Details

* **Author:** Adarsh Patel
* **Date:** 2026-11-12
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
| `gujrera_pipeline/data/runs/party_profiles_…`, `related_projects_…`, `pilot_…` | Small supplementary captures | < 4 MB total |
| `real_estate_intelligence/data/intelligence.sqlite` | Curated DB — currently the 9 deep-captured projects only | 4.8 MB |

## 2. Index coverage (17,634 projects)

Populated for **100% of projects**: projectRegId, projectName, project_address, districtName, projectType, project_status, startDate, endDate (format `31-December-2019`), regNo, promoterName, approvedOn, costs (17,583/17,634). No duplicate IDs.

Partial / empty:
- **`extDate` (extension date): 2,733 projects (15%)** — direct input for the completion-revision story at scale.
- **`disposed_date`: 0%** — column exists but is entirely empty.
- **No latitude/longitude columns** — the Explore map's pins currently come from per-project deep captures only.
- **Promoter PII present in the index**: `prmtr_adhaar_no`, `prmtr_pan_no`, `pr_mobile_no`, `pmtr_email_id`, `prmtr_com_reg_no`. ⚠️ These are portal-published fields, but per SPEC user story 27 (PII redaction) they must **never** flow into the public UI, exports, or model inputs. Any statewide ingestion must carry an explicit redaction list.

Status semantics caveat: `project_status` = New 14,238 / Ongoing 3,354 / Completed 42 — portal registration status, not construction stage; Explore filters should prefer deep-captured progress fields once available.

## 3. Download gap — what is pending

| Layer | Status |
|---|---|
| Statewide registration index | ✅ Complete (17,634/17,634, refreshed 2026-10-11; 4 historical snapshots) |
| Per-project form-ID map | ✅ Complete — the "what to fetch" list is fully catalogued |
| **Deep per-project capture** | ❌ **9 of 17,634 (0.05%)** — **17,625 projects pending** |
| Documents (PDFs) | ❌ Phase-2 on-demand only (deliberate, per SPEC two-phase strategy) |

Form-ID availability for the pending 17,625:
- **17,580 projects (99.7%) have ALL of Form 1 + 2 + 3 IDs** — meaning prices (Form 3), progress (Form 1), and engineering (Form 2) are fetchable for essentially the whole state.
- 44 projects have no core form IDs at all; 54 are missing at least one core form (likely pre-2023 registrations with no quarterly filings).
- Extension certificates: 918 projects have an `extcertificateId` (vs 2,733 with `extDate` in the index — the two sources disagree; reconcile during ingestion).
- `failed_ids` (145) are stale: sampled projects now have full core-form IDs — retry them in the first batch.

## 4. Scale & effort estimate (Phase-1 tabular only)

- Per-project Phase-1 footprint ≈ 43 gz JSON files ≈ 113 KB (measured on the nine-project run; the 1.2 GB run total is dominated by Phase-2 PDFs/exports, which stay on-demand).
- **Statewide Phase-1 estimate: ~2 GB raw JSON + curated SQLite growth of a few GB.**
- Requests: ~43 endpoints × 17,625 ≈ **758k requests**; at the collector's portal-respecting rate limits this is a multi-day continuous run — schedule it in batches and keep the resumable collector semantics (idempotent re-runs are already a pipeline invariant).
- Recommended phasing: **(1) pilot batch of 100** (mix: Ahmedabad+Gandhinagar, one edge district, the 145 stale failures) to validate the pipeline at width; **(2) Ahmedabad + Gandhinagar (~7,150)** — the districts the Explore scenarios need, including all South Bopal/Shela projects; **(3) remaining districts by size** (Vadodara, Surat, Rajkot, …).

## 5. What the statewide index unlocks vs. what stays blocked

**Unlocked immediately after ingestion (no new collection needed):**
- Explore at real scale: district (33 districts), type, budget fit (costs 100%), completion window (endDate 100%), extension-flag filter (extDate 2,733).
- Acceptance scenario 2 goes **live**: South Bopal (83) and Shela (98) projects exist in the index with addresses and costs.
- Longitudinal index drift (5 snapshots) for registration-level trends.

**Still blocked until deep capture (per-project fetches):**
- **GPS pins for the map** — locations endpoint is per-project (the 9 captured have it). Options: capture `locations` endpoint statewide (small per project), or geocode addresses; decide before Phase 2.
- Form-3 transaction prices, escrow banks, quarterly progress, applications/case records, documents/FTS — all per-project.
- Extension **actioned dates** at scale (the `approvalDate` field this audit's companion loader change now persists).

**Missing details to reconcile during ingestion:**
- `extDate` (2,733) vs `extcertificateId` (918) mismatch.
- `disposed_date` always empty — drop or investigate.
- `project_status` semantics ("New" ≠ construction stage).
- PII redaction list enforcement at the loader/export boundary.

## 6. Recommendation

Proceed with phased Phase-1 ingestion (pilot 100 → Ahmedabad+Gandhinagar → rest), preceded by (a) the PII redaction check on the loader/export paths and (b) a decision on statewide GPS (capture `locations` per project vs geocoding). The form-ID catalogue being 100% complete means no discovery work remains — the gap is purely fetch+ingest throughput.
