# mcp — Model Context Protocol Tool Server

## Overview
`RealEstateIntelligenceMCP` exposes the analytics stack as named, read-only research tools for AI agents (the `agent` package's copilot calls these methods directly via `getattr`). It composes `DocumentSearchEngine`, `KnowledgeGraph`, `ProjectAuditor`, and `SpatialAnalytics` eagerly, and lazily trains the `HedonicPricingModel` and `CompletionDelaySurvivalModel` on first use. There is no network listener here — "MCP" refers to the tool-calling contract, not a running server process.

## Interface
Public methods on `RealEstateIntelligenceMCP(db_path=None)` [server.py:RealEstateIntelligenceMCP]:
- `get_project_dossier(project_id) -> str` — full 4-quadrant Markdown dossier via `generate_investor_dossier` [server.py:get_project_dossier]
- `query_inventory_breakdown(project_id) -> List[Dict]` — block-level inventory rows from `inventory_blocks` [server.py:query_inventory_breakdown]
- `search_document_evidence(query, project_id=None, doc_type=None, limit=5) -> List[Dict]` — BM25 FTS search [server.py:search_document_evidence]
- `trace_entity_network(project_id) -> dict` — `{"project_id", "shared_entities", "contagion_risk_leads"}` [server.py:trace_entity_network]
- `audit_discrepancies(project_id) -> List[Dict]` — serialized `DiscrepancyLead` rows [server.py:audit_discrepancies]
- `get_escrow_health(project_id) -> dict` — splits `banks` into `escrow_70_percent_accounts` (type 1) and `collection_100_percent_accounts` (type 2), adds `cash_flow_summary` from the latest `finances` row and `low_liquidity_flag` (escrow closing balance < 50,000) [server.py:get_escrow_health]
- `get_land_records(project_id) -> dict` — TP scheme / final plot / survey / GPS plus `block_clearances` from `noc_bu_records` [server.py:get_land_records]
- `get_regulatory_radar(project_id) -> dict` — complaints/alterations/extension counters and `form5_annual_audits` [server.py:get_regulatory_radar]
- `compare_projects(project_ids) -> List[Dict]` — side-by-side comparison projection over `projects` [server.py:compare_projects]
- `predict_pricing_benchmark(project_id, asset_class="Residential", carpet_area_sqft=1200.0) -> dict` — SHAP-explained hedonic valuation [server.py:predict_pricing_benchmark]
- `forecast_completion_delay(project_id) -> dict` — Cox survival forecast via `forecast_project_by_id` [server.py:forecast_completion_delay]
- `calculate_escrow_runway(project_id) -> dict` — delegated to `ProjectAuditor.calculate_escrow_runway` [server.py:calculate_escrow_runway]
- `get_spatial_density(project_id, radius_km=3.0) -> dict` — delegated to `SpatialAnalytics.get_nearby_projects` [server.py:get_spatial_density]

## Invariants
- The class is documented and used as read-only: no method inserts or updates database rows [server.py:RealEstateIntelligenceMCP]
- `predict_pricing_benchmark` trains `HedonicPricingModel(n_estimators=25, max_depth=3)` once and caches it in `_pricing_model`; `forecast_completion_delay` likewise lazily caches `_survival_model` — first calls pay a full training scan, and both lazy initializations are double-checked under a shared `threading.Lock` (`_model_lock`) so concurrent first calls under the dashboard's threaded server train exactly once [server.py:predict_pricing_benchmark], [server.py:forecast_completion_delay]
- Constructor signature is `db_path`, but any `sqlite3.Connection` passed as `db_path` is returned unchanged by `db.database.get_connection`, so the UI can share its live connection [server.py:RealEstateIntelligenceMCP]
- `get_escrow_health` liquidity threshold is `< 50,000` INR closing balance on type-1 accounts [server.py:get_escrow_health]
- Unknown project IDs produce `{"error": f"Project {project_id} not found..."}` dicts (or a `ValueError` propagated from the dossier generator) rather than exceptions for most tools [server.py:get_land_records], [server.py:get_regulatory_radar]

## Side Effects
- Opens a SQLite connection via `db.database.get_connection(db_path)` at construction (default [../config.py:DEFAULT_DB_PATH]); the connection lives for the object's lifetime and is not closed by this class [server.py:RealEstateIntelligenceMCP]
- Indirect writes during construction: `get_connection` applies pragmas and `init_schema`, and `KnowledgeGraph.__init__` creates `graph_nodes`/`graph_edges` tables if absent [server.py:RealEstateIntelligenceMCP]
- Lazy training on first `predict_pricing_benchmark` / `forecast_completion_delay` call reads the full `unit_transactions` / `projects` tables (CPU-heavy, no writes); serialized by `_model_lock` across threads [server.py:predict_pricing_benchmark], [server.py:forecast_completion_delay]

## Verification
- Run: `python -m pytest real_estate_intelligence/tests`
