# mcp — Model Context Protocol Gateway & Tool Server

## Overview
The `mcp` package provides standard Model Context Protocol (MCP 2024-11-05 / FastMCP 4.2.4) capabilities for AI agents running locally or remotely (e.g., Google Antigravity, Claude Code, Cursor). It exposes 14 consolidated tools (11 statewide core + 3 pilot-gated with explicit `SKIPPED_UNINGESTED` provenance), 3 dynamic `rera://` resources, and a `SkillCatalogProvider` mounting domain skills (`buyer-due-diligence`, `market-screening-analyst`, `pilot-forensic-auditor`). All outputs are formatted in a standard structured envelope (`{data, data_coverage, provenance, pagination, token_estimate}`) and capped at 6,000 tokens with centralized in-memory PII scrubbing (`db/redaction.py`).

## Interface
- `mcp: FastMCP` — Main FastMCP application instance configured with `streamable_http` and `stdio` transports [fastmcp_app.py:mcp]
- `SkillCatalogProvider([Skill.from_directory(...)])` — Isolated domain skill provider mounting skills from `.agents/skills/` [fastmcp_app.py:SkillCatalogProvider]
- Standard Envelope Wrapper `_wrap_envelope(data, data_coverage, source, query_hint, total_items, limit, offset)` [fastmcp_app.py:_wrap_envelope]
- Public Tools on `FastMCP` (14 consolidated):
  - `search_projects(query, district=None, limit=20, offset=0)` — Statewide FTS and facet exploration [fastmcp_app.py:search_projects]
  - `get_project_dossier(project_id)` — 4-quadrant executive dossier with BU check and overdue badging [fastmcp_app.py:get_project_dossier]
  - `compare_projects(project_ids)` — Side-by-side metric comparison across up to 10 projects [fastmcp_app.py:compare_projects]
  - `query_unit_transactions(project_id, status="ALL", limit=100, offset=0)` — Individual unit deeds [fastmcp_app.py:query_unit_transactions]
  - `get_spatial_pricing_benchmark(project_id, radius_km=2.0)` — Spatial empirical pricing pricer [fastmcp_app.py:get_spatial_pricing_benchmark]
  - `get_pricing_appreciation_trend(project_id, asset_class="Residential")` — Trailing-4Q and quarterly CAGR trend [fastmcp_app.py:get_pricing_appreciation_trend]
  - `verify_sales_claim(project_id, claimed_rate_sqft, asset_class="Residential")` — Trailing-4Q empirical claim verification [fastmcp_app.py:verify_sales_claim]
  - `get_spatial_density(project_id, radius_km=3.0)` — Geographic micro-market cluster absorption [fastmcp_app.py:get_spatial_density]
  - `get_land_records(project_id)` — TP scheme, final plot, survey, GPS, and block clearances [fastmcp_app.py:get_land_records]
  - `trace_entity_network(project_id)` — Promoter, professional, and bank entity graph connections [fastmcp_app.py:trace_entity_network]
  - `get_promoter_portfolio(project_id=None, promoter_name=None)` — Composite Key (c) disjoint cluster resolution [fastmcp_app.py:get_promoter_portfolio]
  - `audit_discrepancies(project_id)` — Pilot-gated statutory cross-filing discrepancy detector [fastmcp_app.py:audit_discrepancies]
  - `get_escrow_and_finances(project_id)` — Pilot-gated 70% escrow segregation and cash-flow health [fastmcp_app.py:get_escrow_and_finances]
  - `get_regulatory_radar(project_id)` — Pilot-gated Form 1/3/5 audit radar and complaints [fastmcp_app.py:get_regulatory_radar]
- Dynamic Resources on `FastMCP`:
  - `rera://project/{project_id}/summary` — Core project overview [fastmcp_app.py:resource_project_summary]
  - `rera://project/{project_id}/pricing` — Longitudinal pricing summary [fastmcp_app.py:resource_project_pricing]
  - `rera://project/{project_id}/compliance` — BU status and statutory flags [fastmcp_app.py:resource_project_compliance]
- Backward-Compatible Python Adapter:
  - `RealEstateIntelligenceMCP(db_path=None)` — Direct in-process analytics wrapper [server.py:RealEstateIntelligenceMCP]

## Invariants
- Zero DB mutations: all tool calls and resource reads execute strictly read-only queries against `data/intelligence.sqlite` [fastmcp_app.py], [server.py]
- Centralized PII Redaction: every tool response payload passes through `redact_payload()` before returning to clients [fastmcp_app.py:_wrap_envelope]
- Response Budget Ceiling: all tool payloads enforce a strict 6,000 token upper bound (24,000 characters) to prevent agent context window explosion [fastmcp_app.py:_enforce_token_budget]
- Data Coverage Transparency: pilot-gated tools return `"data_coverage": "SKIPPED_UNINGESTED"` with a clear warning whenever queried on uningested non-pilot projects [fastmcp_app.py]
- Skill Catalog Isolation: FastMCP uses `SkillCatalogProvider([Skill.from_directory(...)])` to mount verified skills without scanning unformatted workspace directories [fastmcp_app.py]

## Side Effects
- Opens a read-only SQLite connection via `db.database.get_connection()` on startup [fastmcp_app.py]
- Zero stdout pollution on stdio transport: all logging routes strictly to stderr or file [fastmcp_app.py]
- FastMCP HTTP endpoint mounted at `/mcp` inside `api/index.py` via `combine_lifespans` [api/index.py:app]

## Verification
- Run test suites:
  - `python -m pytest real_estate_intelligence/tests/test_fastmcp_gateway.py`
  - `python -m pytest real_estate_intelligence/tests/test_phase1_mcp.py`
  - `python -m pytest real_estate_intelligence/tests/test_phase1_5_polish.py`

