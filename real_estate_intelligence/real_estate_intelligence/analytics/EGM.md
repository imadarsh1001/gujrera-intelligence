# analytics — Forensic, Pricing, ML & Survival Engines

## Overview
Read-only quantitative analysis and statutory compliance engines over the curated SQLite database (`data/intelligence.sqlite`). Eight core modules:
1. Deterministic statutory auditing (`audit.py`)
2. Broker-claim fact-checking with trailing-4Q empirical benchmarks (`claims_checker.py`)
3. Institutional 4-quadrant investor dossier generation with statutory BU verification (`investor_dossier.py`)
4. Micro-market spatial empirical pricing (`spatial_pricing.py`)
5. Dependency-free GBDT + exact Tree SHAP hedonic pricing model (`ml_pricing.py`)
6. Unit transaction pricing benchmarks and trailing-4Q quarterly trends (`pricing.py`)
7. Geospatial micro-market analysis (`spatial.py`)
8. Cox Proportional Hazards completion-delay forecasting (`survival.py`)

## Interface
- `ProjectAuditor(con)` with `audit_project(project_id) -> List[DiscrepancyLead]`, `calculate_escrow_runway(project_id) -> dict`, and `audit_credential_coverage(project_id) -> dict` [audit.py:ProjectAuditor]
- `SalesClaimVerifier(con)` with `verify_claim(project_id, claimed_rate_sqft, claimed_sold_pct=None, claimed_completion_date=None, asset_class="Residential") -> dict` [claims_checker.py:SalesClaimVerifier]
- `generate_investor_dossier(con, project_id) -> str` — Markdown 4-quadrant dossier with statutory BU verification [investor_dossier.py:generate_investor_dossier]
- `SpatialEmpiricalPricer(con)` with `benchmark_project(project_id, radius_km=2.0) -> dict` — 2km/5km/taluka spatial medians and spreads [spatial_pricing.py:SpatialEmpiricalPricer]
- `HedonicPricingModel` with `extract_features`, `fit`, `predict`, `explain`, `train_from_db`, `cross_validate` [ml_pricing.py:HedonicPricingModel]
- `PricingIntelligence(con_or_db=None)` with `get_project_pricing_summary(project_id, asset_class="Residential")` and `get_longitudinal_pricing_trend(project_id, asset_class="Residential")` [pricing.py:PricingIntelligence]
- `SpatialAnalytics(con_or_path=None)` with `get_nearby_projects(project_id, radius_km=3.0)` and `get_tp_scheme_summary(tp_scheme, district=None)` [spatial.py:SpatialAnalytics]
- `CompletionDelaySurvivalModel` with `fit`, `predict_hazard_ratio`, `predict_survival_probability`, `forecast_project_timeline`, `calculate_concordance_index`, `train_from_db`, `forecast_project_by_id` [survival.py:CompletionDelaySurvivalModel]

## Invariants
- Ground Truth BU Verification: `projects.bu_status` is discontinued; BU status is determined strictly via `project_summaries.has_bu_noc` and `noc_bu_records.bu_check == 'YES'` [investor_dossier.py:generate_investor_dossier]
- Cohort-Aware Delivery Default Badging: modern schemes (completion date >= 2020) past due without BU are explicitly badged `🔴 EXPIRED_WITHOUT_BU (+X months overdue)` with statutory delivery default alerts; pre-2020 schemes are flagged `Legacy Pre-2020 Grandfathered`; public authority schemes are labeled `Govt Authority Scheme` [investor_dossier.py:generate_investor_dossier]
- Trailing-4Q Pricing Benchmarks: `verify_claim` and `get_pricing_appreciation_trend` default to `asset_class="Residential"` (matching `"Commercial"` or `"Residential"` case-insensitively, and treating `"All"`/`None` as un-filtered). Claims are evaluated against trailing-4Q booked deed medians if >= 3 deeds exist, falling back to lifetime medians with `stale_deed_warning: true` if transactions are older than 18 months [claims_checker.py:verify_claim], [pricing.py:get_project_pricing_summary]
- Spatial Pricing Hierarchy: `SpatialEmpiricalPricer` evaluates concentric radii (2km -> 5km -> taluka) to achieve <100ms pricing benchmarks backed by empirical registered deeds [spatial_pricing.py:SpatialEmpiricalPricer]
- Deterministic Audit Invariants: escrow velocity ratio (<0.75 HIGH / <0.90 MEDIUM), Section 4(2)(l)(D) 70% retention over-withdrawal check, and Form 3/5 CA coverage [audit.py:audit_project]

## Side Effects
- Strictly read-only operations across all analytics modules; no modifications made to `data/intelligence.sqlite` [audit.py], [claims_checker.py], [investor_dossier.py], [pricing.py]
- In-memory model caching: `HedonicPricingModel` and `CompletionDelaySurvivalModel` cache fitted weights in memory during server lifespan [ml_pricing.py], [survival.py]

## Verification
- Run test suites:
  - `python -m pytest real_estate_intelligence/tests/test_phase1_5_polish.py`
  - `python -m pytest real_estate_intelligence/tests/test_spatial_pricing_and_audit.py`
  - `python -m pytest real_estate_intelligence/tests/test_claims_and_pricing.py`
