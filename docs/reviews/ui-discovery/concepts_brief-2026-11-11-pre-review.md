# UI Revamp: Explore Projects, Shortlist & Compare, Ask Across Projects

* **Author:** Adarsh Patel (git identity unset in workspace; taken from commit history — confirm before RFC)
* **Date:** 2026-11-11
* **Status:** DRAFT — anchored working hypothesis, pre-Goldfish review
* **Input:** User brief of 2026-11-09; dashboard fix pass of 2026-11-09/10 (verified fixes recorded in `docs/UI_COMPONENT_PLAN.md` handoff, pending); data coverage verified against `real_estate_intelligence/data/intelligence.sqlite` on 2026-11-09.

## Overview

The dashboard today is a single-project dossier: you pick one of 9 projects from a header dropdown and read its filings, pricing, analytics, graph, and document search. A user cannot ask "which projects in Gandhinagar finish by 2028 and cost less than their neighbors," cannot compare projects side by side, and cannot question a set of projects at once. This concept adds a search-first **Explore** entry point, a **Shortlist & Compare** view, and **Ask Across Projects** scoping for the copilot, while keeping the existing per-project workbench as Project Detail. Every finding must trace to its source record.

## Working Hypothesis (anchored)

The first release ships on the current Python-served UI (stdlib server + embedded template, no frontend migration): a filterable, sortable Explore table over the curated intelligence database, two validated summaries (filing freshness, completion-revision status), the existing per-project tabs as Project Detail with "why this matched" context, and a localStorage shortlist. Value benchmarks, architect filters, related-case search, side-by-side comparison, and cross-project questions follow in later stages, gated on verified data coverage rather than declared intent. The current stack can carry this release because every planned element already has a working pattern in the template (tables, filter chips, summary badges, fetch-and-render panels).

## Verified Data Coverage (curated DB, 2026-11-09)

Facts below were queried directly from `intelligence.sqlite` (9 projects, run `default_run`, 8 Gandhinagar + 1 Ahmedabad/Sanand).

| Proposed filter/analytic | Status | Evidence |
|---|---|---|
| District, taluka | **supported** | `projects.district`/`taluka` 9/9 populated (2 districts) |
| Locality / micro-market | **unavailable** | No locality column; `tp_scheme` 2/9, `final_plot_no` 3/9, `survey_no` 4/9. Statewide index (17,634 rows in `collected_data/`) not ingested |
| Project type | **partial** | `projects.project_type` 9/9 but only 2 values (Mixed Development, Residential/Group Housing) |
| Unit configuration | **supported** | `unit_transactions.unit_type` (Residential 1,516 / Shop 143 / Office 14), `carpet_area_sqft` 1,673/1,673 |
| Carpet-area range | **supported** | Same column, full coverage |
| Total price | **supported** | `unit_transactions.unit_consideration` 1,673/1,673 (recorded transaction prices only) |
| Price per sq ft | **supported** | `rate_per_sqft` 1,673/1,673; range ₹2,755–₹17,904; agreement dates 2022-03 → 2026-10 |
| Price source & date | **supported** | Form 3 agreement date per transaction; source is the sworn filing |
| Asking price / asking vs recorded | **unavailable** | `market_listings` has 0 rows (seam designed, dormant) |
| Local price benchmark (median vs own locality) | **partial** | Computable today only at district+project_type level with 8-vs-1 project splits; "locality" grouping needs ≥2 comparable projects. Minimum-coverage rule proposed below |
| Declared completion window | **supported** | `projects.completion_date` 9/9 (2026-03-31 → 2030-04-30) |
| Reported construction stage | **supported** | `latest_form_one_progress_pct` and `engg_score_pct` 9/9 |
| Latest filing date (freshness) | **supported** | `finances.filing_date`, exactly 2 filings per project (index + latest), 100% coverage |
| Completion-date revision status | **partial** | No multi-run history in curated DB; revisions observable only via `applications` Extension rows (2 projects) and `projects.has_extensions` (2/9). Three-state design below |
| Promoter / registered promoter | **supported** | `promoters` 9 rows with name, type, linked-project counts; `projects.promoter_name` 9/9 |
| Architect filter | **partial** | `professionals` architect rows 8/9, **name only** — no license number (engineers have 8/8 licenses), no firm_name |
| Design features / architectural style | **unavailable** | No source field exists in any table |
| Case/order records for the project | **partial** | `applications` table (82 rows: 50 Annual Compliance, 9 Registration, 7 BCR, 4 Complaint, 2 Extension, 2 Alteration, 7 LEGAL_PCWF, 1 TP_PCWF); `application_status` is null on all rows; dates occasionally malformed ("190130") |
| Cases naming promoter/builder in another project | **partial** | Only via shared-entity graph (`graph_edges` 52 edges, `PROBABLE_SAME_AS`/verified license links); no litigation table. Complaint ≠ order distinction must be surfaced |
| Builder role separation | **supported** | GLOSSARY: "promoter" is the registered role; "builder" is colloquial. UI will use promoter/professional terms per GLOSSARY |

## Explore Projects Design

**Layout.** Explore becomes the landing tab: search box, filter rail (grouped), results table, summary strip. Project Detail remains the current tab set. The header dropdown stays as a shortcut.

**Search.** Free-text across project name, promoter name, registration number (client-side over `/api/projects` at 9 rows; server-side FTS once statewide).

**Filter groups → the question each answers:**

| Group | Filters (status) | Question answered |
|---|---|---|
| Location & unit | District (supported), taluka (supported), project type (partial), unit type (supported), carpet-area min/max (supported) | *Where and what can I buy?* |
| Budget & price | Min/max total price (supported), min/max ₹/sq ft (supported), price-as-of window (supported), below-own-group-median toggle (partial — see benchmark rule) | *What does it cost, and is that cheap for here?* |
| Construction & filings | Completion on/before date (supported), min construction stage % (supported), filed-within-N-days toggle (supported), revision status (partial) | *When is it done, how current are the filings, and did dates move?* |
| People & firms | Promoter name/autocomplete (supported), architect name (partial — name-only) | *Who stands behind it?* |
| Cases & applications | Has complaints (supported: `complaints_count`), has extensions/alterations (supported), application-type presence (partial) | *What friction is on record?* |

**Counts & active filters.** The results header shows "N of 9 projects match" and each applied filter as a removable chip. Clicking a summary-category badge (e.g. "3 projects with extensions") applies that filter; clicking the chip removes it. Unknowns are visible: each filter shows how many matching projects have no value for it ("2 of 5 have no filed completion date"), and a "not stated" option is offered where missing values would silently exclude rows.

**State preservation.** Search text, active filters, sort column/direction, and page live in the URL hash (e.g. `#exploreq=...`) plus sessionStorage, so returning from Project Detail restores the exact result view. Back returns to the same results, not a reset.

**Summary 1 — Filing freshness.** Label = days since the project's latest `finances.filing_date`. The label carries its cutoff explicitly ("latest filing 2026-10-07; computed 2026-11-11"). Buckets: ≤35 days (current quarter), ≤95 days (one quarter behind), >95 days (stale), never filed (none exist today). Every quarter-close the bucket boundaries re-anchor to the current date; the computation date is printed next to the summary.

**Summary 2 — Completion-revision status.** Three states, per the brief: **revision observed** (an Extension application row exists, dated), **no revision observed in comparable filings** (2 filings on record, index and latest, and no extension row), **insufficient comparable history** (fewer than 2 filings on record — 0 projects today, state kept for honesty as coverage grows). The DB holds no before/after completion-date pairs across runs, so "revision" today means "extension application on record", and the UI says exactly that rather than implying a date diff it did not compute.

**Summary 3 (deferred) — Local price benchmark.** Shown per project only when its comparison group (same district + same project type; locality when data allows) has ≥3 projects with ≥5 transactions each within the last 24 months. Today that is only satisfiable in degraded form (8 Gandhinagar projects); the brief's own threshold rule ("show insufficient comparable data when unmet") applies until coverage lands.

## Value & Related-Cases Rules

**Price displays.** Lowest total price, lowest ₹/sq ft, and vs-comparable are three separate sortable columns, never blended into one "value score". ₹/sq ft is computed per transaction as consideration ÷ carpet sq ft (the loader already derives this); a project's "lowest" is its cheapest matching unit under the active unit-type/carpet filters. Asking prices never mix into these columns (no data today; when `market_listings` activates, asking rates render in a visually distinct column with source and date).

**Comparison group definition.** Same district + same project type (+ unit type when filtering residential). Reporting period enters as a filter (agreement-date window), construction stage as a disclosed caveat (median of a 95%-complete project vs a 20%-complete project is not apples-to-apples; the UI prints stage alongside the benchmark rather than adjusting for it).

**Value for money.** Explicit checklist, not a verdict: budget fit (user's max price), price vs own-group median (≥10% below / within ±10% / above), unit configuration availability, stage risk, filing freshness. Each result shows which criteria it meets; a low ₹/sq ft alone is labeled "lower-priced", not "better value".

**People.** Promoter, architect, engineer remain separate roles with separate chips. Architect filter is name-equality on the documented attribution (8/9 coverage) with a "source: professionals table (Form 1/2 filing)" link; no style/design-feature filters exist.

**Related cases.** Three tiers, always labeled: (1) records directly concerning the project (`applications` rows, complaint counts); (2) records naming the same promoter on another project (promoter_id join); (3) other-project records connected via a verified shared professional (license-number edge) — soft `PROBABLE_SAME_AS` links are shown with their confidence and never presented as verified. Each row shows named party, role, linked project, record type, status (or "status not disclosed" — the field is null across the board), date, and source table. A search returning nothing reports which sources were searched and their coverage ("searched: applications, complaints_count, professional graph; no order/litigation records exist in this database") — absence of records is not absence of cases.

## Connected Workflows

**Project Detail.** The existing 8 tabs (dossier, pricing, ML curves, claims, discrepancies, graph, vault, search) are kept as-is post-fix. Explore adds: a "why this matched" strip (which filters the project satisfies), deep links into the evidence behind any summary value (the filing pair behind freshness, the extension row behind revision status, the transaction rows behind a price stat), and the existing project-scoped copilot unchanged.

**Shortlist & Compare.** Add/remove from Explore rows and Project Detail header. Persistence: localStorage (`gujrera.shortlist.v1`, JSON array of project IDs + added-at), per browser — chosen as default (no server write path; revisitable decision). Compare renders the shortlist side by side using Explore's exact definitions and thresholds: total price and ₹/sq ft as separate rows with their dates, stage, freshness, revision status, and per-cell evidence links. Data gaps render as "not stated", never as zero. Shareable due-diligence brief is a follow-on, not in this concept's first release.

**Ask Across Projects.** The copilot gains a scope selector with three explicit states: **filtered results** (default when launched from Explore), **shortlist** (default from Compare), **all indexed projects** (9 today). The active scope is always printed above the answer. Queries run the same definitions as Explore/Compare (same comparison group, same thresholds), return the matching project list plus the evidence rows behind each claim, and offer "reopen these results in Explore" (restores the filter state). Coverage limits are stated in the answer ("benchmark unavailable: only 1 comparable project in group").

## Acceptance Scenarios

1. **Filing history.** Filter district=Gandhinagar, completion ≤ 2028-12-31 (5 of 9 projects qualify on today's data). Open revision summary; shortlist 3; ask "which of these revised their completion dates?" — expect per-project statuses with the extension-application evidence behind any "revision observed", "no revision observed in comparable filings" for the others, and the filing pair (index + latest) reachable in two clicks. Insufficient-history must appear as its own state, distinct from "no revision".
2. **Value, architect, promoter history.** 3 BHK in South Bopal/Shela: **cannot be demonstrated on current data** (no Ahmedabad-city projects, no locality column). The scenario runs fixture-backed: a sanitized fixture set (3-4 synthetic projects with South Bopal/Shela localities, documented as fixtures in the UI banner "demo data") exercises the locality benchmark, below-own-benchmark highlighting, and architect narrowing; the same interactions on live data show "insufficient comparable data" instead of fabricated numbers. Price basis, architect source, party relationship, case status, and underlying record must each be visible in the fixture run.

## First-Release Proposal

Ship: Explore table (search + the supported filters above + sort + counts + chips + state preservation), filing-freshness and revision-status summaries with their three states and cutoff dates, Project Detail with match-reason strip and evidence links, localStorage shortlist with a basic side-by-side (Explore-defined fields, no benchmark column), copilot scoped to one project (unchanged). Follow-ons in order: local price benchmark (when ≥3-project groups exist), architect filter hardening, related-case tier-2/3 views, full Compare with benchmark column, cross-project Ask. Each gate is a data-coverage check, not a date.

## Alternatives Weighed (draft)

- **Vue + Vite + shadcn-vue or React + Vite + shadcn/ui migration now** — deferred to the component-mapping step of the brief; the current stack already renders tables/chips/badges/drawers and the release adds no state complexity beyond URL-hash filters. Migration cost today buys no user-visible capability this release needs. (To be challenged in review with the code-we-would-own numbers.)
- **Server-side filter API from day one** — rejected for 9 rows (client-side filtering is instant and simpler); becomes necessary with statewide ingestion; the filter state design (URL hash) is chosen so the same state can later drive a server query unchanged.
- **Ingesting the statewide 17,634-project index before any UI work** — rejected for this release by the author (2026-11-11): the statewide collection itself is incomplete (pending downloads, missing details, unverified), so ingestion would front-load an unverified dataset into the UI. Staged follow-on: first a download-gap/coverage audit of the statewide index, then ingestion, then Explore's location/type filters upgrade from client-side to server-side using the same URL-hash filter state.
- **A blended "value score"** — rejected: the brief requires lowest-price, lowest-₹/sqft, and vs-benchmark as separate sorts; a composite would hide the trade-offs the checklist exists to show.

## Key Decisions & Staging

1. First release on the current Python-served UI; migration decision taken after the component comparison lands in `docs/UI_COMPONENT_PLAN.md`.
2. Shortlist persistence: localStorage (default chosen; server-side table offered as alternative).
3. Server switched to `ThreadingHTTPServer` (2026-11-11) with `ui/EGM.md` contract updated — a slow copilot call no longer freezes the dashboard; verified 3.7 ms response during an in-flight call.
4. Summary honesty rules: every freshness/revision/benchmark label prints its cutoff date and source; the three revision states are distinct and today's implementation labels extension applications as what they are.
5. Scenario 2 runs fixture-backed until Ahmedabad-city/locality data lands; fixtures are banner-labeled, sanitized, and never mixed into live result counts.

## Open Questions for the Author

1. Data scope: first release on the 9-project DB (assumed default) vs ingesting the statewide index first?
2. Shortlist persistence: localStorage (assumed default) vs server-side table vs both?
3. Author name for the RFC header (git identity is unset; "Adarsh Patel" taken from commit history).
4. Is the fixture-backed demonstration of scenario 2 acceptable for the review walkthrough, or should the review run on live data only?

**Resolved by the author (2026-11-11):** (1) 9-project DB only for this release — the statewide 17,634-project index stays out; a separate follow-on task will audit what remains to be downloaded and which details are missing before ingestion is considered. (2) localStorage. (3) Author is Adarsh Patel. (4) Fixture-backed demonstration approved ("do what works best") — the walkthrough will use banner-labeled sanitized fixtures, with live data showing "insufficient comparable data" alongside.

## Reviewer Challenges Requested (from the author's brief)

- Which filters and analytics actually help narrow a shortlist — and which are table dressing at 9 projects?
- Do available prices support meaningful local comparisons; which claims exceed the data?
- Could missing filings or uncertain entity matches mislead a user about a project, promoter, or professional?
- Can a user see the scope of a cross-project answer and verify its evidence?
- Can the first release stay on the current frontend at reasonable effort, or does migration materially reduce the code we would own?
