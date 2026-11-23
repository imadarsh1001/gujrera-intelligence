# Hostile Specification Critique: GujRERA MCP Roadmap

**Critique Date**: November 23, 2026  
**Target Document**: `docs/mcp_technical_audit_and_roadmap.md` (93 KB, 1,078 lines)  
**Wave 1 Evidence**: Reports 01–03 in `docs/audit/`  
**Methodology**: Every claim below is grounded in empirical SQL/Python verification against `data/intelligence.sqlite` and application source code. Zero deference to roadmap assertions.

---

## 1. Kill / Defer List

Items from the 93 KB roadmap that must be killed, deferred, or redesigned. Each entry cites one-line empirical proof from Wave 1 reports or verified code.

### 1.1 KILL — Remove Entirely

| # | Roadmap Item | Type | One-Line Empirical Proof |
|---|---|---|---|
| K1 | `CompletionDelaySurvivalModel` (Cox PH) | ML Model | 4 events / 17,787 rows (99.98% censored); C-index 1.0 is artifact of E=4 (`02_models:L19–L24`) |
| K2 | `forecast_completion_delay` tool | MCP Tool | Wraps K1; all 4 events are from 9 pilot projects; model outputs for statewide projects are statistically meaningless (`server.py:270–283`) |
| K3 | `delivery-forecaster-skill` | Agent Skill | Binds `forecast_completion_delay` + `compare_projects`; both feed on 0.05% velocity/progress data (`roadmap §3.5`) |
| K4 | SAR / SEM Spatial Econometric Models | Proposed Model | `projects.tp_scheme` populated for 2 of 17,787 projects (0.01%); spatial weight matrix W cannot be constructed (`03_hidden:L131`) |
| K5 | `get_tp_scheme_summary` tool | Proposed Tool | Depends on K4; tp_scheme is 99.99% NULL (`scratch_audit.py` verified: 2 / 17,787) |
| K6 | Kaplan-Meier Estimator & Greenwood Variance | Proposed Model | Same 4-event dataset as K1; product-limit estimator with d=4 out of n=17,787 produces degenerate near-1.0 survival curve (`roadmap §4.3.1`) |
| K7 | `audit_credential_coverage` tool | Proposed Tool | `professionals` has 8 architects, 0 CAs, 0 contractors; `project_summaries.ca_name` is 100% NULL; tool checks credentials that don't exist (`01_data:L169–L172`) |
| K8 | `rera-evidence-verifier-skill` (FTS5-based) | Agent Skill | `document_fts` has 0 rows; 789/789 `document_jobs` are PENDING; skill cannot verify anything (`01_data:L190–L191`) |
| K9 | `verify_document_provenance` tool | Proposed Tool | Same as K8; SHA-256 hashes exist in catalog but no text is indexed; tool returns empty on every call |
| K10 | `query_inventory_breakdown` on statewide | MCP Tool | `inventory_blocks` has 22 rows across 9 projects (0.05%); returns `[]` for 17,778 projects (`01_data:L30`) |
| K11 | Bayesian Promoter Contagion Engine (Beta-Binomial) | Proposed Model | `promoters` table has 9 rows; `projects.promoter_id` non-null for 9 / 17,787; prior Beta(5,2) updates on s=0, f=0 for 99.95% of developers (`roadmap §4.1.4`) |
| K12 | `get_promoter_portfolio` tool | Proposed Tool | Depends on K11 data; `promoters` has 9 rows; returns empty for all statewide queries |
| K13 | Months of Inventory (MOI) calculation | Proposed Model | Requires quarterly sales velocity ΔBooked/Δt; `unit_transactions` has no quarter-over-quarter delta (single snapshot, no temporal sequence per project) (`roadmap §4.2.4`) |

### 1.2 DEFER — Blocked Until Statewide Pipeline Expansion

| # | Roadmap Item | Type | Blocker & Empirical Proof |
|---|---|---|---|
| D1 | 7 of 10 forensic audit rules (Rules 1–3b, 8–9, 10a) | Audit Rules | 95.5% silent skip rate on statewide projects; require `finances`, `form5_compliance`, `banks.closing_bal` populated beyond 9 pilots (`02_models:L79–L89`) |
| D2 | `calculate_escrow_runway` tool | MCP Tool | Requires `banks.closing_bal` (non-null for 8 / 17,739 rows, 0.045%) and `finances` (9 projects); returns zeroed metrics statewide (`01_data:L109–L111`) |
| D3 | `get_escrow_health` tool (financial portion) | MCP Tool | `banks.deposit_amt` / `withdrawal_amt` / `closing_bal` are 99.93–99.95% NULL; "cash_flow_summary" from `finances` returns `{}` for 99.95% of projects (`01_data:L109–L112`) |
| D4 | `search_document_evidence` tool | MCP Tool | `document_fts` has 0 rows; tool is registered but returns empty results for all queries; defer until offline PDF indexing worker runs (`01_data:L191`) |
| D5 | `v_analytics_project_features` materialized view | Proposed View | Joins `promoters` (9 rows), `banks` aggregations (99.93% NULL balances); `escrow_over_withdrawal_inr` computation is hollow for 99.95% of projects (`roadmap §4.4, L733–L779`) |
| D6 | `screen_market_projects` tool | Proposed Tool | Filters by `min_rate`, `has_bu` etc. — rates live in `project_summaries` (viable), but `has_bu` derived from `noc_bu_records` needs hygiene pass (6 corrupt date entries) |

### 1.3 REDESIGN — Fundamentally Flawed, Salvageable with Fixes

| # | Roadmap Item | Flaw | Required Fix |
|---|---|---|---|
| R1 | `HedonicPricingModel` (GBDT) | R²=0.3654, MAPE=63.63%, 4 dead features, ~3.9h lazy train on full DB (`02_models:L58–L67`) | Pre-train offline on sampled N≤50k; drop `asset_Retail/Office/Warehouse`, `promoter_scale`; add district one-hot for all 33 districts; serialize to JSON (26.9 KB) |
| R2 | `predict_pricing_benchmark` tool | Wraps R1; lazy `_model_lock` training crashes Vercel (10s/60s timeout) (`02_models:L192`) | Load pre-serialized JSON weights; eliminate lazy training entirely |
| R3 | `trace_entity_network` tool | 100,424 tokens on Project 7871 due to 17,778 `promoter:None` supernode (`02_models:L116,L128`) | Filter `promoter:None` edges; add pagination/`max_results` param; cap response at 4,000 tokens |
| R4 | `get_spatial_density` tool | 18,251 tokens on Project 58 at radius_km=3.0 (`02_models:L125,L129`) | Add pagination; reduce default `radius_km` to 1.5; return top-20 nearest only |
| R5 | Section 4(2)(l)(D) Over-Withdrawal formula | Conflates land cost with civil progress; non-deterministic `fetchone()` on multi-row bank accounts (`02_models:L100–L103`) | Exclude land cost from withdrawal cap; use `SUM()` aggregation across account_type=1 rows |
| R6 | Rule 10b (Missing Architect) | Triggers on 100% of projects because `professionals` has 8 architects statewide (`02_models:L90`) | Gate rule: skip when `professionals` architect count < threshold per district |
| R7 | Copilot registration gap | Roadmap says "3-tool gap"; empirically 4 tools missing (`get_project_dossier` is registered but `compare_projects`, `get_regulatory_radar`, `get_spatial_density` are not); copilot `handle_copilot_query()` hard-codes 15+ keyword branches duplicating MCP dispatch (`copilot.py:464–833`) | Register all 13 tools; delete hard-coded keyword routing; let LLM select tools |

---

## 2. Consolidated MCP Tool Surface

The roadmap proposes expanding to 22 tools. After applying the Kill/Defer list above, the viable surface is **14 tools** organized by data-tier viability.

### 2.1 Recommended 14-Tool Surface

| # | Tool Name | Data Tier | Status | Notes |
|---|---|---|---|---|
| 1 | `search_projects` | Tier 1 (new) | **BUILD** | Queries `projects` + `project_summaries`; viable on 17,787 rows |
| 2 | `get_project_detail` | Tier 1 (rename `get_project_dossier`) | **KEEP + REDESIGN** | Replace 25-query waterfall with 3 aggregated CTEs; cap output at 4k tokens |
| 3 | `query_unit_transactions` | Tier 1 (new) | **BUILD** | 1.95M rows; paginated, filterable by `project_id`, `asset_class`, `status` |
| 4 | `get_pricing_trend` | Tier 1 (new) | **BUILD** | Wraps `pricing.py`; 54% of projects have ≥4-quarter deed span (`03_hidden:L141`) |
| 5 | `verify_sales_claim` | Tier 1 (new) | **BUILD** | Wraps `claims_checker.py`; compares claimed vs. registered deed median |
| 6 | `predict_pricing_benchmark` | Tier 1 (redesigned) | **REDESIGN** | Pre-serialized offline weights; drop dead features; see R1–R2 |
| 7 | `get_land_records` | Tier 1 | **KEEP** | Queries `projects` + `noc_bu_records`; 95.73% coverage |
| 8 | `get_regulatory_radar` | Tier 1 | **KEEP + REGISTER** | Already implemented; register in GEMINI_TOOLS |
| 9 | `compare_projects` | Tier 1 | **KEEP + REGISTER** | Already implemented; register in GEMINI_TOOLS |
| 10 | `get_spatial_density` | Tier 1 (redesigned) | **REDESIGN** | Add pagination + max_results; register in GEMINI_TOOLS |
| 11 | `trace_entity_network` | Tier 1 (redesigned) | **REDESIGN** | Filter `promoter:None`; add token cap |
| 12 | `audit_discrepancies` | Mixed | **KEEP + FIX** | Fix Section 4(2)(l)(D) formula (R5); add `data_coverage` field showing which rules were skippable |
| 13 | `get_escrow_health` | Mixed | **KEEP** | Account identity is Tier 1; financial balances are Tier 3; return `data_coverage` indicators |
| 14 | `query_professional_track_record` | Tier 1 (new) | **BUILD** | Engineers only (15,557 rows, 86.98% coverage); name-normalized; explicitly exclude architect/CA claims |

### 2.2 Killed Tools (Do Not Build)

`forecast_completion_delay`, `calculate_escrow_runway`, `get_tp_scheme_summary`, `get_promoter_portfolio`, `audit_credential_coverage`, `verify_document_provenance`, `screen_market_projects` (merge into `search_projects`), `query_inventory_breakdown` (merge into `get_project_detail`).

### 2.3 Mandatory Response Envelope

Every tool response MUST conform to this envelope. The roadmap specifies no envelope; this is a critical omission.

```json
{
  "data": { ... },
  "data_coverage": {
    "tier": "tier_1 | tier_2 | tier_3",
    "populated_fields_pct": 0.95,
    "skipped_checks": ["rule_1_cost_reversal: finances table empty for this project"],
    "warning": "Escrow balances available for 9/17787 projects only"
  },
  "provenance": {
    "source_tables": ["projects", "unit_transactions"],
    "query_project_ids": [16562],
    "timestamp_utc": "2026-11-23T01:00:00Z"
  },
  "pagination": {
    "offset": 0,
    "limit": 50,
    "total": 4798,
    "truncated": true
  },
  "token_estimate": 1842
}
```

**Hard rule**: Any tool returning `token_estimate > 6000` MUST auto-truncate and set `pagination.truncated = true`. This prevents the 100k-token `trace_entity_network` blowup documented in `02_models:L116`.

---

## 3. Architecture Fixes

### 3.1 Transport: Kill SSE, Adopt stdio + Streamable HTTP

| Roadmap Proposal | Problem | Required Fix |
|---|---|---|
| "Dual Transport: stdio + SSE" (`roadmap §5.1, L786–839`) | SSE (`GET /sse`) is a **deprecated MCP transport** per MCP spec 2025-03-26; superseded by Streamable HTTP (`POST /mcp`). Roadmap proposes a transport that no major client will adopt. | Implement `stdio` for local clients (Claude Desktop, Cursor, Antigravity). Implement Streamable HTTP at `POST /mcp` with Bearer auth for remote clients. Delete all `/sse` and `/messages` endpoint references. |
| No auth on SSE | Roadmap mounts SSE on `127.0.0.1:8765` with no authentication; any local process can invoke tools. | Streamable HTTP `/mcp` endpoint: require `Authorization: Bearer <token>` header. stdio: inherits process-level auth (no additional auth needed). |
| `mcp` SDK not installed | `pyproject.toml` has no `mcp` or `fastmcp` dependency; `RealEstateIntelligenceMCP` is a plain Python class (`02_models:L195–L201`) | Add `mcp>=1.9.0` to `pyproject.toml`; wrap existing class with `FastMCP` decorator; expose via `mcp.run(transport="stdio")` and Starlette ASGI mount for `/mcp`. |

### 3.2 PII Redaction: Move to Shared Data-Access Layer

| Roadmap Proposal | Problem | Required Fix |
|---|---|---|
| `PIIRedactionInterceptor` as Phase 3 middleware (`roadmap §5.5, L979–1008`) | PII is already leaking NOW: 5 PANs + 4 emails in `professionals.license_or_reg_no` exposed via `/api/project/{pid}`, `/api/graph`, `trace_entity_network` (`02_models:L143–L159`) | Move PII scrubbing into `db/queries.py` at the data-access layer, not as an optional middleware. Apply regex scrub on `license_or_reg_no` and `name` columns: `re.sub(r'[A-Z]{5}\d{4}[A-Z]', '***PAN***', val)` and `re.sub(r'[\w.+-]+@[\w-]+\.[\w.]+', '***EMAIL***', val)`. |
| `PIIRedactionInterceptor.filter_kyc_fields()` checks column names | Column names like `license_or_reg_no` and `name` are NOT in the `forbidden_keys` set (`pan_number`, `aadhaar_number`, etc.); the interceptor misses actual PII locations (`roadmap L1004–L1007`) | Redact by content pattern (regex), not by column name. |
| FTS5 will index raw PDF text | When `document_fts` is populated, full-text snippets may contain buyer names, PAN, Aadhaar from Form 3 deed attachments. | Apply regex PII scrub in `fts.py:index_page_text()` before inserting into FTS5. |

### 3.3 Virtual Views → Persisted Summary Columns

| Current State | Problem | Required Fix |
|---|---|---|
| `v_current_projects` and `v_current_unit_transactions` are SQL VIEWs (`01_data:L16,L21`) | Views re-execute full table scans on every query; `v_current_unit_transactions` scans 1.95M rows per call | Drop views. Persist aggregated columns (`total_units`, `booked_units`, `absorption_pct`, `median_rate_sqft`) directly in `project_summaries` (already done for 16,468 projects). Remove redundant view layer. |
| Proposed `v_analytics_project_features` view (`roadmap §4.4, L736`) | Joins `promoters` (9 rows), aggregates `banks` (99.93% NULL balances); useful for 0.05% of projects | Kill as a view. If revived, persist as a materialized table rebuilt by an offline job after each data ingestion. |

### 3.4 Lazy Model Training → Offline Serialized JSON Weights

| Current State | Problem | Required Fix |
|---|---|---|
| `HedonicPricingModel.train_from_db()` under `_model_lock` on first call (`server.py:237–242`) | Full-DB training takes ~3.93 hours extrapolated; guaranteed Vercel timeout (`02_models:L59,L192`) | Train offline via CLI command `python -m real_estate_intelligence.cli train-models`. Serialize to `data/models/pricing_gbdt.json` (26.9 KB) and `data/models/survival_cox.json` (1.95 KB). Load at server startup. Delete `_model_lock` and lazy training code. |
| `CompletionDelaySurvivalModel.train_from_db()` under `_model_lock` (`server.py:276–281`) | 91.24s training time for a model with 4 events; model should be killed (K1), but if kept for pilot demo, serialize offline | Same as above; moot if K1/K2 are accepted. |

---

## 4. Citation Boundary: MCP Server vs. Copilot Verification

The roadmap conflates two distinct concerns under "Zero-Hallucination Evidentiary Citation Contract" (`roadmap §5.4, L903–975`):

### 4.1 MCP Server Guarantees (Per-Tool Structured Provenance)

Each tool response MUST include machine-readable provenance in the `provenance` field of the response envelope (§2.3 above):

| Guarantee | Scope | Implementation |
|---|---|---|
| `source_tables` | List of SQLite tables queried | Hardcoded per tool at registration time |
| `query_project_ids` | Project IDs used in WHERE clauses | Extracted from tool arguments |
| `data_coverage.tier` | Tier 1/2/3 classification per §7 of `01_data` | Computed from table row counts at startup |
| `data_coverage.skipped_checks` | Which audit rules had insufficient data | Returned by `audit_discrepancies` per rule |

This is the **MCP server's job**. It requires zero LLM involvement.

### 4.2 Copilot Verification (Agent-Side, NOT Server-Side)

The `EvidentiaryClaimCitation` JSON Schema (`roadmap L908–974`) is an **agent/copilot concern** that belongs in `agent/copilot.py`, NOT in MCP tool responses:

| Concern | Why It's Agent-Side |
|---|---|
| `claim_statement` | Generated by the LLM, not by the tool |
| `confidence_score` | Assigned by the agent based on tool output quality |
| `statutory_reference_clause` | Interpreted by the LLM from tool output context |
| `document_sha256` | Looked up by the agent via a separate tool call |

**Required separation**: The MCP server returns structured `provenance`; the copilot wraps LLM assertions in `EvidentiaryClaimCitation`. The roadmap must not place citation validation logic inside the MCP serving layer — doing so makes the server dependent on LLM output format and breaks the tool/agent boundary.

### 4.3 Delete the Hard-Coded Keyword Router

`agent/copilot.py:464–833` contains 370 lines of hard-coded keyword matching (`if any(w in q_lower for w in [...])`), duplicating what the LLM tool-calling loop already does. This is the antithesis of an MCP architecture:

- 15 keyword branches manually select which tools to call and format responses
- Bugs: branch 6 ("escrow") calls `mcp_server.get_escrow_health()` directly, bypassing `dispatch_tool()` logging
- When GEMINI_TOOLS grows, keyword branches will NOT auto-discover new tools

**Action**: Delete lines 464–833. Trust the LLM tool-calling loop (lines 234–409) to select tools. If a fallback is needed for no-API-key mode, return a "please provide an API key" message.

---

## 5. Top 5 Open Decisions

These decisions MUST be locked by the project owner before any Phase 1 implementation begins.

### Decision 1: Statewide Data Expansion Scope

> **Question**: Will the scraping pipeline (`../gujrera_pipeline`) be expanded to ingest Form 1 (architect quarterly), Form 5 (annual CA audit), promoter profiles, and applications statewide — or will the system permanently operate with 9-project deep data?

**Impact**: If NO expansion, then 7 of 10 audit rules, the survival model, the Bayesian contagion engine, and 6 proposed tools are permanently non-viable. The entire roadmap §4 (Deep Data Analysis) collapses. The honest answer may be: "This is a 9-project demo platform with statewide search only."

| If Expanded | If NOT Expanded |
|---|---|
| Kill list shrinks from 13 to ~4 items | Kill list stands; 22→14 tools becomes 22→10 |
| Phase 2 tools become viable | Phase 2 is mostly killed |
| Survival model may become viable with E>200 events | Survival model is permanently dead |

### Decision 2: Pricing Model Architecture

> **Question**: Should the hedonic pricing model remain a pure-Python GBDT (R²=0.3654, MAPE=63.63%), or should it be replaced with district-level median/percentile statistics from `unit_transactions` (zero ML, 100% interpretable)?

**Trade-off**: The pure-Python GBDT with 4 dead features explains 36.5% of variance. A simple `GROUP BY district, taluka` with `PERCENTILE_CONT` over 1.08M booked transactions provides median ± IQR with no training time, no serialization, and no dead features. ML adds complexity without adding predictive power at current feature sparsity.

### Decision 3: Knowledge Graph Remediation Strategy

> **Question**: Should `promoter:None` edges be (a) deleted, (b) replaced with `promoter_name` string-keyed nodes from `projects.promoter_name`, or (c) blocked until `promoter_id` is populated statewide?

**Impact**: 17,778 of 17,787 `DEVELOPED_BY` edges point to `promoter:None`. The graph is non-functional for developer contagion analysis until this is resolved. Option (b) enables the 350 split-risk developer clusters identified in `03_hidden:L74` using string-normalized promoter names (12,191 unique raw → 9,457 brand clusters).

### Decision 4: MCP SDK Version & Transport

> **Question**: Which MCP SDK and transport combination? Options: (a) `mcp>=1.9.0` with `stdio` + Streamable HTTP, (b) `fastmcp>=2.0` with same, (c) continue as plain Python class with no SDK.

**Impact**: Option (c) means no Claude Desktop / Cursor / Antigravity integration ever. Options (a) and (b) are functionally equivalent; `fastmcp` adds decorator sugar. Lock one and add it to `pyproject.toml` as the first commit.

### Decision 5: Copilot Architecture — LLM-First or Deterministic Fallback

> **Question**: Should `handle_copilot_query()` (370 lines of keyword routing in `copilot.py:464–833`) be (a) deleted entirely (LLM-only, requires API key), (b) kept as offline fallback, or (c) replaced with a minimal template-based fallback?

**Impact**: The keyword router is unmaintainable — it doesn't auto-discover new tools, manually formats responses, and duplicates MCP dispatch. If an offline mode is needed, option (c) with 5 simple templates (<50 lines) covering search, detail, pricing, audit, and "get API key" is sufficient.

---

## Appendix: Roadmap Factual Errors

| Roadmap Claim | Line | Empirical Reality |
|---|---|---|
| "3-Tool Copilot Registration Gap" | §2.6, L271 | 10 of 13 tools are registered (confirmed by GEMINI_TOOLS parse); 3 missing is a **lower bound** — but `handle_copilot_query()` hard-codes its own tool calls, making the registration count irrelevant for keyword-mode queries |
| "17,739 Statutory Escrow Bank Accounts" with "deposits, withdrawals, and closing balances" | §1, L54 | `closing_bal` non-null for 12 rows (0.07%), `deposit_amt` non-null for 9 rows (0.05%); 99.93% are identity-only records with zero financial data (`01_data:L109–L111`) |
| "15,565 Licensed Professionals" including "architects, engineers, CAs" | §1, L55 | 15,557 engineers, 8 architects, 0 CAs, 0 contractors (`01_data:L169`) |
| "sub-10ms subsequent inferences" for lazy-trained models | §2.5, L263 | First inference triggers 3.93-hour training; subsequent inferences are sub-10ms only if server stays alive (`02_models:L59`) |
| "21,836 Graph Nodes & 51,069 Edges" as functional knowledge graph | §1, L56 | 17,778 of 17,787 `DEVELOPED_BY` edges point to `promoter:None`; graph traversal returns entire state as "shared entities" (`01_data:L177–L179`) |
| "789 Indexed Documents" | §1, L57 | 789 PDFs cataloged but `document_fts` has 0 indexed rows; `document_jobs` are 100% PENDING (`01_data:L190–L191`) |
| `PIIRedactionInterceptor` protects against PII | §5.5, L979–1008 | Interceptor checks column names, not content; misses 5 PANs and 4 emails in `license_or_reg_no` and `name` fields (`02_models:L143–L157`) |
| "Zero-Hallucination" via EvidentiaryClaimCitation | §5.4, L903 | Schema validates agent claims, not tool outputs; a tool returning wrong data passes citation validation perfectly; the guarantee is illusory at the MCP layer |

---

## Summary Metrics

| Metric | Count |
|---|---|
| Items KILLED from roadmap | 13 |
| Items DEFERRED | 6 |
| Items requiring REDESIGN | 7 |
| Proposed tools trimmed (22 → 14) | 8 removed |
| Factual errors in roadmap | 8 documented |
| Open decisions requiring owner lock | 5 |
| Audit rules viable statewide (of 10) | 3 (Rules 4, 5, 6/7) |
| Audit rules blocked by data (of 10) | 7 |
| PII leaks requiring immediate fix | 9 records (5 PAN + 4 email) |
