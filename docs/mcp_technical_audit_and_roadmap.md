# GujRERA Model Context Protocol (MCP) Technical Audit, Capability Gap Analysis, and Multi-Agent Architectural Roadmap

**Document Status**: Official Architecture & Technical Audit  
**Author**: GujRERA Sovereign Intelligence Platform Architecture Team  
**Date**: November 22, 2026  
**System**: `real_estate_intelligence`  
**Database**: `data/intelligence.sqlite` (SQLite WAL / Turso libSQL, 563 MB)  
**Deliverable Scope**: Comprehensive Technical Audit (R1), Capability & Gap Analysis (R2), Deep Data Analytics Plan (R3), Multi-Agent Serving Architecture (R4), and Phased Roadmap  

---

## Table of Contents
1. [Executive Summary & System Context](#1-executive-summary--system-context)
2. [MCP Code Architecture & Framework Analysis (Zoom-Out to Zoom-In)](#2-mcp-code-architecture--framework-analysis-zoom-out-to-zoom-in)
   - [2.1 High-Level Architecture & Component Topology](#21-high-level-architecture--component-topology)
   - [2.2 Framework & Dependency Footprint Analysis](#22-framework--dependency-footprint-analysis)
   - [2.3 Server Lifecycle, Configuration & Startup Mechanics](#23-server-lifecycle-configuration--startup-mechanics)
   - [2.4 Transport Protocols & Execution Patterns](#24-transport-protocols--execution-patterns)
   - [2.5 Concurrency Model & Lazy Model Lifecycle](#25-concurrency-model--lazy-model-lifecycle)
   - [2.6 Tool Discovery, Registration & The 3-Tool Copilot Registration Gap](#26-tool-discovery-registration--the-3-tool-copilot-registration-gap)
   - [2.7 Exhaustive 13-Tool MCP Inventory Table](#27-exhaustive-13-tool-mcp-inventory-table)
3. [Capability & Gap Analysis with Agent/Skill Orchestration](#3-capability--gap-analysis-with-agentskill-orchestration)
   - [3.1 Relational & Analytical Asset Census](#31-relational--analytical-asset-census)
   - [3.2 Sovereign Pure-Python ML & Analytics Engine Inventory](#32-sovereign-pure-python-ml--analytics-engine-inventory)
   - [3.3 Statutory Forensic Audit Rules & Broker Claims Verification](#33-statutory-forensic-audit-rules--broker-claims-verification)
   - [3.4 Comprehensive Capability Gap Matrix](#34-comprehensive-capability-gap-matrix)
   - [3.5 Specialized Agent Skills Architecture](#35-specialized-agent-skills-architecture)
4. [Deep Data Analysis & Hidden Insights Execution Plan](#4-deep-data-analysis--hidden-insights-execution-plan)
   - [4.1 Forensic Risk Signals & Anomaly Detection Methodologies](#41-forensic-risk-signals--anomaly-detection-methodologies)
   - [4.2 Quantitative Valuation & Market Econometrics](#42-quantitative-valuation--market-econometrics)
   - [4.3 Delivery Forecasting & Survival Analytics](#43-delivery-forecasting--survival-analytics)
   - [4.4 Analytical Feature Pipelines & SQL Materialization](#44-analytical-feature-pipelines--sql-materialization)
5. [Internal & External Agent Serving Architecture](#5-internal--external-agent-serving-architecture)
   - [5.1 FastMCP Gateway & Dual-Transport Architecture (stdio & SSE)](#51-fastmcp-gateway--dual-transport-architecture-stdio--sse)
   - [5.2 MCP Resource URI Hierarchy (`rera://...`)](#52-mcp-resource-uri-hierarchy-rera)
   - [5.3 Multi-Agent Orchestration Topology & Subagent Routing](#53-multi-agent-orchestration-topology--subagent-routing)
   - [5.4 Zero-Hallucination Evidentiary Citation Contract](#54-zero-hallucination-evidentiary-citation-contract)
   - [5.5 Privacy, Banking Masking & PII Redaction Interceptors](#55-privacy-banking-masking--pii-redaction-interceptors)
6. [Actionable Implementation Roadmap & Milestone Schedule](#6-actionable-implementation-roadmap--milestone-schedule)
   - [6.1 Phased Execution Breakdown](#61-phased-execution-breakdown)
   - [6.2 Architectural Risk Register & Mitigation Strategy](#62-architectural-risk-register--mitigation-strategy)
   - [6.3 Conclusion & Sign-Off](#63-conclusion--sign-off)

---

## 1. Executive Summary & System Context

The GujRERA Sovereign Real Estate Intelligence Platform (`real_estate_intelligence`) represents a specialized analytical stack engineered to perform automated forensic due-diligence, econometric property valuation, delivery timeline forecasting, and knowledge graph contagion analysis over real estate projects registered under the Gujarat Real Estate Regulatory Authority (GujRERA). 

Historically developed as a local-first, zero-dependency data platform, the repository hosts an extraordinary volume of curated public statutory filings:
- **17,787 Total Registered Projects**: Comprehensive coverage across all 33 districts of Gujarat (led by Ahmedabad with 5,536 projects, Vadodara with 2,946, Surat with 2,681, and Rajkot with 1,970).
- **1,952,528 Certified Unit Transactions**: Official Form 3 deed-level transaction records covering both booked ($1,093,866$ units) and unbooked ($858,662$ units) residential and commercial stock, establishing a true ground-truth ledger of property absorption and pricing.
- **46,931 Municipal Building Use (BU) NOC Records**: Official municipal occupancy clearances, fire safety NOC certificates, and lift inspection records tracking statutory safety compliance.
- **17,739 Statutory Escrow Bank Accounts**: Granular tracking of Section 4(2)(l)(D) 70% retention escrow accounts and 100% collection accounts with IFSC codes, branch allocations, deposits, withdrawals, and closing balances.
- **15,565 Licensed Professionals**: Architects (Council of Architecture registered), structural engineers (municipal license holders), chartered accountants, and contractors signing sworn compliance certificates.
- **21,836 Graph Nodes & 51,069 Edges**: An interconnected heterogeneous knowledge graph linking projects, developers, promoters, technical professionals, sister schemes, and financial institutions.
- **789 Indexed Documents & Cryptographic Hashes**: Statutory Form 1, Form 2, Form 3 CA filings, title reports, encumbrance certificates, and alteration petitions preserved with SHA-256 provenance hashes.

While the data layer is among the most sophisticated regional real estate intelligence assets in existence, the **Model Context Protocol (MCP)** interface that exposes these assets to Large Language Model (LLM) agents exhibits significant structural drift. The current MCP implementation is an in-process Python class (`RealEstateIntelligenceMCP` in `real_estate_intelligence/mcp/server.py`) offering 13 research methods. However:
1. **Transport Isolation**: It lacks standard external MCP transports (`stdio` streams or Server-Sent Events `/sse`), preventing out-of-the-box integration with external agentic clients (such as Claude Desktop, Cursor, or IDE plugins).
2. **Copilot Registration Drift**: The conversational copilot (`agent/copilot.py`) only registers 10 of the 13 tools, entirely omitting `compare_projects`, `get_regulatory_radar`, and `get_spatial_density`.
3. **Severe Data Exposure Gaps**: The 13 tools require knowing a numeric `project_id` upfront. They do not allow an agent to search or filter projects, inspect unit transactions, fact-check broker marketing claims against registered deeds, examine longitudinal CAGR trends, audit Town Planning (TP) scheme absorption, or evaluate promoter portfolios.

This technical audit and architectural roadmap provides the comprehensive blueprint to transition the platform into an enterprise-grade, multi-agent serving ecosystem with dual transports, verified citation contracts, zero-hallucination guardrails, and deep econometric and forensic capabilities.

---

## 2. MCP Code Architecture & Framework Analysis (Zoom-Out to Zoom-In)

### 2.1 High-Level Architecture & Component Topology

The system operates across four primary tiers: the Storage & Ingestion Layer, the Analytical & Machine Learning Engine Layer, the In-Process MCP Interface Layer, and the Serving/API Gateway Tier.

```
═══════════════════════════════════════════════════════════════════════════════════════════════════
                                HIGH-LEVEL SYSTEM TOPOLOGY
═══════════════════════════════════════════════════════════════════════════════════════════════════

   [ External AI Consumers ]        [ Local IDE / CLI Agents ]        [ Web Dashboard / UI ]
  (Claude Desktop / Cursor)            (CLI, Copilot Scripts)              (Leaflet/Chart.js)
              │                                  │                                  │
              │ (Proposed stdio / SSE)           │ (Python In-Process)              │ (HTTP JSON API)
              ▼                                  ▼                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 SERVING & TRANSPORT GATEWAY                                     │
│  FastAPI ASGI Server (api/index.py)                    CLI Engine (cli.py)                     │
│  ├── POST /api/copilot (LLM Tool Calling Loop)        ├── serve (Uvicorn 127.0.0.1:8765)       │
│  ├── GET  /api/projects, /api/explore                 └── sync-turso (Remote DB Replication)   │
│  └── GET  /api/analytics/{survival, pricing_trend, ml_pricing, verify_claim}                   │
└───────────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                                │
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 IN-PROCESS MCP TOOL CONTRACT                                    │
│  Class: RealEstateIntelligenceMCP (real_estate_intelligence/mcp/server.py)                      │
│  ├── 13 Named Research Tools (get_project_dossier, get_escrow_health, audit_discrepancies...)   │
│  ├── Lazy Model Training under threading.Lock (_model_lock)                                     │
│  └── Direct Object Composition (SearchEngine, KnowledgeGraph, ProjectAuditor, SpatialAnalytics) │
└───────────────────────┬───────────────────────────────────────────────┬─────────────────────────┘
                        │                                               │
                        ▼                                               ▼
┌───────────────────────────────────────────────┐ ┌───────────────────────────────────────────────┐
│       ANALYTICS & QUANTITATIVE MODELS         │ │          DOCUMENT & KNOWLEDGE GRAPH           │
│  ├── ml_pricing.py: Hedonic GBDT + TreeSHAP   │ │  ├── network.py: KnowledgeGraph (21.8k nodes) │
│  ├── survival.py: Cox Proportional Hazards    │ │  ├── search.py: DocumentSearchEngine (FTS5)   │
│  ├── pricing.py: Realized Deed CAGR Trajectory│ │  ├── claims_checker.py: SalesClaimVerifier    │
│  └── spatial.py: Haversine Micro-Market GIS   │ │  └── investor_dossier.py: 4-Quadrant Dossier  │
└───────────────────────┬───────────────────────┘ └───────────────────────┬───────────────────────┘
                        │                                               │
                        └───────────────────────┬───────────────────────┘
                                                │
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 STORAGE & RELATIONAL DATA LAYER                                 │
│  Database Connection Router: real_estate_intelligence/db/database.py (get_connection)          │
│  ├── Local SQLite3 WAL Mode (PRAGMA journal_mode = WAL; busy_timeout = 30000)                   │
│  └── Remote Turso libSQL Client (LibsqlConnectionWrapper via TURSO_DATABASE_URL)                │
│                                                                                                 │
│  Core Relational Stores (data/intelligence.sqlite - 563 MB):                                    │
│  ├── projects (17,787)        ├── unit_transactions (1,952,528)  ├── banks (17,739)            │
│  ├── project_summaries (17.7k) ├── noc_bu_records (46,931)        ├── professionals (15,565)    │
│  ├── graph_nodes (21,836)     ├── graph_edges (51,069)           ├── documents_catalog (789)   │
│  └── finances (18)            ├── applications (82)              └── quarterly_timeline (94)   │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Packaging Dependency Clarification**:
While the current repository operates with zero external MCP SDK dependencies (implementing an in-process class-based tool contract), adding `mcp>=1.0.0` or `fastmcp>=0.1.0` to `pyproject.toml` dependencies is the recommended first step in Phase 1 implementation to establish standard external `stdio` and `SSE` protocol listeners.

### 2.2 Framework & Dependency Footprint Analysis

A forensic inspection of `pyproject.toml` and `requirements.txt` reveals the packaging configuration of the project:

```toml
# pyproject.toml (lines 1-22)
[project]
name = "real-estate-intelligence"
version = "0.1.0"
description = "Sovereign Real Estate Intelligence Platform"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn>=0.30.0",
    "libsql>=0.1.11",
    "pypdf>=5.0.0",
]
```

**Key Architectural Observations**:
1. **Absence of Official MCP SDK**: Neither the official Model Context Protocol SDK (`mcp>=1.0.0`) nor `fastmcp` is listed as a project dependency. While the current repo has no external MCP SDK dependency, adding `mcp>=1.0.0` or `fastmcp>=0.1.0` to `pyproject.toml` dependencies is the recommended first step in Phase 1 implementation.
2. **Contractual Definition of "MCP"**: As documented in `real_estate_intelligence/mcp/EGM.md` (lines 3–5):
   > "`RealEstateIntelligenceMCP` exposes the analytics stack as named, read-only research tools for AI agents (the `agent` package's copilot calls these methods directly via `getattr`). It composes `DocumentSearchEngine`, `KnowledgeGraph`, `ProjectAuditor`, and `SpatialAnalytics` eagerly, and lazily trains the `HedonicPricingModel` and `CompletionDelaySurvivalModel` on first use. There is no network listener here — 'MCP' refers to the tool-calling contract, not a running server process."
3. **Pure-Python Scientific Stack**: The project explicitly avoids dependencies on `numpy`, `scipy`, `pandas`, `scikit-learn`, `xgboost`, `shap`, `statsmodels`, or `lifelines`. All gradient boosted trees, Shapley value path traversals, Kaplan-Meier estimations, Breslow cumulative hazard calculations, and matrix operations are implemented from first principles using Python standard libraries (`math`, `datetime`, `json`, `sqlite3`).

### 2.3 Server Lifecycle, Configuration & Startup Mechanics

#### 2.3.1 Database Connection Factory (`db/database.py`)
Database connectivity is managed through `get_connection(db_path=None)` in `real_estate_intelligence/db/database.py` (lines 164–190). The lifecycle dynamically forks depending on environment variables:

```python
def get_connection(db_path: Optional[Union[str, Path, sqlite3.Connection]] = None) -> Union[sqlite3.Connection, LibsqlConnectionWrapper]:
    if isinstance(db_path, sqlite3.Connection) or isinstance(db_path, LibsqlConnectionWrapper):
        return db_path
    
    # Check for Turso remote configuration
    turso_url = os.environ.get("TURSO_DATABASE_URL")
    turso_token = os.environ.get("TURSO_AUTH_TOKEN")
    
    if turso_url:
        import libsql
        client = libsql.create_client(turso_url, auth_token=turso_token)
        return LibsqlConnectionWrapper(client)
        
    resolved_path = resolve_db_path(db_path)
    con = sqlite3.connect(str(resolved_path), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode = WAL;")
    con.execute("PRAGMA foreign_keys = ON;")
    con.execute("PRAGMA busy_timeout = 30000;")
    return con
```

#### 2.3.2 Server Execution Entry Points
1. **CLI Launcher**: `python -m real_estate_intelligence.cli serve --host 127.0.0.1 --port 8765` triggers `uvicorn.run("api.index:app", host=host, port=port)`.
2. **Direct Script**: `python run_server.py` performs immediate configuration resolution and starts the Uvicorn ASGI server.
3. **FastAPI Application Lifecycle**: In `api/index.py` (lines 66–94), `AppState.setup_backends(db_path)` eagerly initializes the connection and injects it into both `RealEstateIntelligenceMCP` and `AgenticCopilot`:
   ```python
   cls.con = get_connection(db_path)
   cls.auditor = ProjectAuditor(cls.con)
   cls.spatial = SpatialAnalytics(cls.con)
   cls.graph = KnowledgeGraph(cls.con)
   cls.mcp_server = RealEstateIntelligenceMCP(cls.con)
   cls.agentic_copilot = AgenticCopilot(cls.mcp_server)
   ```

#### 2.3.3 Environment Variables
| Variable Name | Purpose | Default / Fallback |
|---|---|---|
| `DEFAULT_DB_PATH` | Path to primary SQLite database file | `data/intelligence.sqlite` |
| `TURSO_DATABASE_URL` | Cloud libSQL endpoint URL for serverless deployment | `None` (uses local SQLite) |
| `TURSO_AUTH_TOKEN` | Bearer token for Turso authentication | `None` |
| `MAPTILER_API_KEY` | Secret key for vector map tiles proxy (`/api/maptiler/{path}`) | Loaded from `.env` or empty |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Enables Gemini 2.0 Flash tool-calling copilot | None (falls back to local rules) |
| `OPENAI_API_KEY` | Enables OpenAI function-calling copilot | None |
| `OPENAI_BASE_URL` | Custom endpoint for OpenAI-compatible LLM gateways | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | Model identifier for OpenAI calls | `gpt-4o-mini` |
| `GUJRERA_PIPELINE_DIR` | Path to sibling raw scraper pipeline | `../gujrera_pipeline` |

### 2.4 Transport Protocols & Execution Patterns

The system currently exhibits a dichotomy between its internal tool-dispatch mechanism and external network exposure:

#### 1. In-Process Python Reflection Dispatch
Inside `real_estate_intelligence/agent/copilot.py` (lines 178–210), `AgenticCopilot.dispatch_tool(self, name: str, args: Dict[str, Any])` executes tool calls by reflecting directly on the `RealEstateIntelligenceMCP` instance:
```python
func = getattr(self.mcp, name, None)
if not func:
    return {"error": f"Tool '{name}' not found on MCP server"}

sig = inspect.signature(func)
# Dynamic type coercion
filtered_args = {}
for param_name, param in sig.parameters.items():
    if param_name in args:
        val = args[param_name]
        if param.annotation is int or param_name == "project_id":
            val = int(val)
        elif param.annotation is float:
            val = float(val)
        filtered_args[param_name] = val

return func(**filtered_args)
```

#### 2. HTTP/JSON REST Transport
The only external interface is exposed via HTTP POST on the FastAPI endpoint `/api/copilot` (`api/index.py` lines 528–580). Clients supply a JSON payload `{"query": "...", "project_id": 16562, "session_id": "..."}`, and the server executes multi-turn tool calling against Gemini 2.0 Flash or OpenAI before returning a final Markdown response with tool call traces.

#### 3. Standard MCP Transports (`stdio` / `SSE`) — Currently Missing
The platform currently has **zero support** for:
- Standard `stdio` communication (the standard pipe used by Claude Desktop, Claude Code, and Cursor).
- Server-Sent Events (SSE) endpoints (the standard network transport defined in the official Model Context Protocol specification).

### 2.5 Concurrency Model & Lazy Model Lifecycle

Because `real_estate_intelligence` is designed to run in both long-lived local environments and serverless edge functions, heavy predictive models are not trained during server boot.

Inside `real_estate_intelligence/mcp/server.py` (lines 24–32), the constructor initializes model placeholders and a thread lock:
```python
self._pricing_model: Optional[HedonicPricingModel] = None
self._survival_model: Optional[CompletionDelaySurvivalModel] = None
self._model_lock = threading.Lock()
```

When an agent invokes `predict_pricing_benchmark` or `forecast_completion_delay`, the server employs **Double-Checked Locking** (`server.py` lines 238–243 and 277–282):
```python
if self._pricing_model is None:
    with self._model_lock:
        if self._pricing_model is None:
            model = HedonicPricingModel(n_estimators=25, max_depth=3)
            model.train_from_db(self.con)
            self._pricing_model = model
```
This guarantees that even under concurrent multi-threaded requests (e.g. Uvicorn worker threads), database scanning and tree training occur exactly once, caching the fitted estimators in memory for sub-10ms subsequent inferences.

### 2.6 Tool Discovery, Registration & The 3-Tool Copilot Registration Gap

Tool registration follows a declarative JSON schema pattern defined in `real_estate_intelligence/agent/copilot.py`:
- `GEMINI_TOOLS` (lines 17–132): Declares Gemini function call definitions with input properties and required constraints.
- `OPENAI_TOOLS` (lines 134–154): Programmatically converts `GEMINI_TOOLS` into OpenAI-compliant function call specifications.

#### The 3-Tool Copilot Registration Gap
A rigorous comparison between `RealEstateIntelligenceMCP` (`server.py`) and `GEMINI_TOOLS` (`copilot.py`) uncovers an immediate discrepancy:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             TOOL REGISTRATION AUDIT                              │
├─────────────────────────────────────────┬──────────────────┬─────────────────────┤
│ Tool Method in RealEstateIntelligenceMCP│ Defined in Class │ Registered in Agent │
├─────────────────────────────────────────┼──────────────────┼─────────────────────┤
│ 1. get_project_dossier                  │ YES (Line 33)    │ YES (GEMINI_TOOLS)  │
│ 2. query_inventory_breakdown            │ YES (Line 41)    │ YES (GEMINI_TOOLS)  │
│ 3. search_document_evidence             │ YES (Line 57)    │ YES (GEMINI_TOOLS)  │
│ 4. trace_entity_network                 │ YES (Line 70)    │ YES (GEMINI_TOOLS)  │
│ 5. audit_discrepancies                  │ YES (Line 80)    │ YES (GEMINI_TOOLS)  │
│ 6. get_escrow_health                    │ YES (Line 99)    │ YES (GEMINI_TOOLS)  │
│ 7. get_land_records                     │ YES (Line 142)   │ YES (GEMINI_TOOLS)  │
│ 8. get_regulatory_radar                 │ YES (Line 172)   │ ❌ MISSING          │
│ 9. compare_projects                     │ YES (Line 204)   │ ❌ MISSING          │
│ 10. predict_pricing_benchmark           │ YES (Line 227)   │ YES (GEMINI_TOOLS)  │
│ 11. forecast_completion_delay           │ YES (Line 270)   │ YES (GEMINI_TOOLS)  │
│ 12. calculate_escrow_runway             │ YES (Line 285)   │ YES (GEMINI_TOOLS)  │
│ 13. get_spatial_density                 │ YES (Line 293)   │ ❌ MISSING          │
└─────────────────────────────────────────┴──────────────────┴─────────────────────┘
```

**Architectural Impact**:
- When an end-user asks the copilot to "compare project 16562 and 13560", "check the regulatory radar for litigation or alterations", or "evaluate nearby micro-market density", the LLM agent **does not see these tools in its function declaration schema**. It is forced to either hallucinate answers or fall back to calling single project dossiers sequentially.

---

### 2.7 Exhaustive 13-Tool MCP Inventory Table

Below is the verified inventory of all 13 tools implemented in `real_estate_intelligence/real_estate_intelligence/mcp/server.py`:

| # | Tool Name | Source Code Lines | Input Arguments & Types | Return Schema / Type | Underlying Database Queries & Models |
|---|---|---|---|---|---|
| 1 | `get_project_dossier` | `server.py:33-39` | `project_id: int` | `str` (Markdown 4-Quadrant Due Diligence Report) | Calls `generate_investor_dossier(self.con, project_id)`. Executes deep queries across `projects`, `promoters`, `professionals`, `banks`, `inventory_blocks`, `quarterly_timeline`, `finances`, `form5_compliance`, `noc_bu_records`, and `documents_catalog`; runs `ProjectAuditor.audit_project` and `KnowledgeGraph.trace_contagion_risk`. |
| 2 | `query_inventory_breakdown` | `server.py:41-55` | `project_id: int` | `List[Dict[str, Any]]` | SQL query: `SELECT block_name, total_units, booked_units, unbooked_units, booking_rate_pct, residential_units, commercial_units FROM inventory_blocks WHERE project_id = ? ORDER BY block_name` |
| 3 | `search_document_evidence` | `server.py:57-68` | `query: str`<br>`project_id: Optional[int] = None`<br>`doc_type: Optional[str] = None`<br>`limit: int = 5` | `List[Dict[str, Any]]` (`doc_uid_hash`, `project_id`, `doc_type`, `file_name`, `page_number`, `snippet`, `rank`) | Calls `self.search_engine.search()`. Queries SQLite FTS5 virtual table `document_fts` with BM25 ranking (`snippet(document_fts, 5, '<b>', '</b>', '...', 25)`, `bm25(document_fts)`). |
| 4 | `trace_entity_network` | `server.py:70-78` | `project_id: int` | `Dict[str, Any]` (`project_id`, `shared_entities`, `contagion_risk_leads`) | Calls `self.graph.find_shared_entities(project_id)` and `self.graph.trace_contagion_risk(project_id)`. Traverses `graph_edges` and `graph_nodes` joined with `projects` and `applications`. |
| 5 | `audit_discrepancies` | `server.py:80-97` | `project_id: int` | `List[Dict[str, Any]]` (Serialized `DiscrepancyLead` dicts: `category`, `severity`, `title`, `detail`, `evidence_source`, `reconciliation_guidance`) | Calls `self.auditor.audit_project(project_id)`. Evaluates 10 forensic rules across `finances`, `projects`, `banks`, `applications`, and `form5_compliance`. |
| 6 | `get_escrow_health` | `server.py:99-140` | `project_id: int` | `Dict[str, Any]` (`project_id`, `escrow_70_percent_accounts`, `collection_100_percent_accounts`, `cash_flow_summary`, `low_liquidity_flag`) | Queries `banks` table (`account_type = 1` vs `2`), queries latest `finances` table row, computes `low_liquidity_flag = closing_bal < 50000`. |
| 7 | `get_land_records` | `server.py:142-170` | `project_id: int` | `Dict[str, Any]` (`project_id`, `name`, `district`, `taluka`, `tp_scheme`, `final_plot_no`, `survey_no`, `latitude`, `longitude`, `google_maps_url`, `bu_status`, `block_clearances`) | Queries `projects` table for TP/FP/survey coordinates; queries `noc_bu_records` for block BU status, fire NOC, and lift inspection document IDs. |
| 8 | `get_regulatory_radar` | `server.py:172-202` | `project_id: int` | `Dict[str, Any]` (`project_id`, `name`, `complaints_count`, `has_complaints`, `alterations_count`, `has_alterations`, `extensions_count`, `has_extensions`, `default_quarters_count`, `society_reg_date`, `form_four_status`, `bu_status`, `velocity_ratio`, `progress_status_label`, `form5_annual_audits`) | Queries `projects` for complaints, alterations, extensions, and quarterly default metrics; queries `form5_compliance` for annual CA audit history. |
| 9 | `compare_projects` | `server.py:204-225` | `project_ids: List[int]` | `List[Dict[str, Any]]` | SQL query: `SELECT project_id, name, promoter_name, district, project_type, total_units, booked_units, booking_rate_pct, latest_form_one_progress_pct, velocity_ratio, progress_status_label, estimated_cost_inr, incurred_cost_inr, complaints_count, alterations_count, default_quarters_count, bu_status FROM projects WHERE project_id IN (...) ORDER BY project_id` |
| 10 | `predict_pricing_benchmark` | `server.py:227-268` | `project_id: int`<br>`asset_class: str = "Residential"`<br>`carpet_area_sqft: float = 1200.0` | `Dict[str, Any]` (`predicted_rate_per_sqft`, `base_market_average_inr`, `net_spread_from_average`, `shap_values`, `top_positive_premiums`, `top_negative_discounts`, `efficiency_check_passed`) | Lazy-trains `HedonicPricingModel(n_estimators=25, max_depth=3)` via `model.train_from_db(self.con)` under `_model_lock`. Queries `projects` joined with `promoters`. Computes Tree SHAP explanations via `model.explain(feats)`. |
| 11 | `forecast_completion_delay` | `server.py:270-284` | `project_id: int` | `Dict[str, Any]` (`project_id`, `project_name`, `scheduled_start_date`, `registered_completion_date`, `scheduled_duration_months`, `delay_risk_label`, `forecasted_delay_months`, `hazard_ratio`, `confidence_assessment`, `forecasted_handover_dates` with p50/p75/p90, `survival_probabilities`, `completion_probabilities`) | Lazy-trains `CompletionDelaySurvivalModel()` via `model.train_from_db(self.con)` under `_model_lock`. Calls `model.forecast_project_by_id(self.con, project_id)`. |
| 12 | `calculate_escrow_runway` | `server.py:285-291` | `project_id: int` | `Dict[str, Any]` (`project_id`, `closing_escrow_balance_inr`, `monthly_construction_burn_inr`, `estimated_runway_months`, `remaining_construction_cost_inr`, `insolvency_risk`) | Calls `self.auditor.calculate_escrow_runway(project_id)`. Queries `projects` (`estimated_cost_inr`, `incurred_cost_inr`), `banks` (`closing_bal` where `account_type = 1`), and spend deltas from `finances`. |
| 13 | `get_spatial_density` | `server.py:293-300` | `project_id: int`<br>`radius_km: float = 3.0` | `Dict[str, Any]` (`origin_project_id`, `origin_name`, `origin_coords`, `radius_km`, `nearby_count`, `micro_market_avg_rate_sqft`, `delayed_projects_count`, `delayed_project_ratio`, `nearby_projects`) | Calls `self.spatial.get_nearby_projects(project_id, radius_km=radius_km)`. Queries `projects` GPS coordinates, computes pairwise Haversine distance, and queries `unit_transactions` for micro-market pricing. |

---

## 3. Capability & Gap Analysis with Agent/Skill Orchestration

### 3.1 Relational & Analytical Asset Census

A systematic PRAGMA scan of `data/intelligence.sqlite` establishes the complete inventory of 27 tables and 2 views:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               RELATIONAL DATA CENSUS (27 TABLES)                                │
├──────────────────────┬─────────────┬─────────┬──────────────┬───────────────────────────────────┤
│ Table Name           │ Category    │ Rows    │ Columns (PK) │ Domain Purpose / Entity           │
├──────────────────────┼─────────────┼─────────┼──────────────┼───────────────────────────────────┤
│ projects             │ Core Entity │  17,787 │ 47 (pid PK)  │ Master statutory project registry │
│ project_summaries    │ Performance │  17,787 │ 29 (pid PK)  │ Pre-computed search/map cache     │
│ unit_transactions    │ Deed Ledger │1,952,528│ 14 (id PK)   │ Registered sales & booked units   │
│ noc_bu_records       │ Compliance  │  46,931 │  7 (id PK)   │ Building Use, Fire & Lift NOCs    │
│ banks                │ Financial   │  17,739 │ 15 (id PK)   │ 70% escrow & 100% accounts        │
│ professionals        │ Signers     │  15,565 │  6 (id PK)   │ Architects, Engineers, CAs        │
│ graph_nodes          │ Network     │  21,836 │  4 (node_id) │ Knowledge graph entity vertices   │
│ graph_edges          │ Network     │  51,069 │  4 (src,rel) │ Inter-entity network edges        │
│ documents_catalog    │ Provenance  │     789 │  7 (uid_hash)│ PDF registry with SHA-256 hashes  │
│ document_jobs        │ Pipeline    │     789 │ 14 (id PK)   │ Async PDF extraction queue        │
│ quarterly_timeline   │ Milestones  │      94 │  9 (id PK)   │ Quarterly physical progress %     │
│ applications         │ Legal       │      82 │  7 (id PK)   │ Alterations, extensions, lawsuits │
│ form5_compliance     │ Statutory   │      39 │  6 (id PK)   │ Annual CA audit compliance        │
│ inventory_blocks     │ Physical    │      22 │  9 (id PK)   │ Towers, wings, and unit mixes     │
│ finances             │ Financial   │      18 │ 15 (id PK)   │ Form 3 costs and receivables      │
│ previous_projects    │ Track Record│      18 │  7 (id PK)   │ Promoter historical portfolio     │
│ promoters            │ Entity      │       9 │  7 (prom_id) │ Master developer records          │
│ market_listings      │ Unpopulated │       0 │ 18 (id PK)   │ External portal listings schema   │
│ copilot_embeddings   │ Unpopulated │       0 │  7 (id PK)   │ Vector embeddings schema          │
│ document_fts         │ FTS5 Virtual│       0 │  6 (virtual) │ Full-text search index            │
│ document_fts_* (5)   │ FTS5 Aux    │     var │    var       │ FTS5 internal data/index tables   │
│ sqlite_sequence / st │ SQLite Meta │     var │    var       │ Internal sequence & statistics    │
├──────────────────────┴─────────────┴─────────┴──────────────┴───────────────────────────────────┤
│ SQL Views: (1) v_current_projects (17,787 rows), (2) v_current_unit_transactions (1.95M rows)   │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Sovereign Pure-Python ML & Analytics Engine Inventory

The platform houses five pure-Python analytical engines engineered to run without heavy C-extensions or external frameworks:

1. **Interpretable Hedonic Pricing Engine (`ml_pricing.py`)**:
   - Implements a custom Gradient Boosted Decision Tree (GBDT) regressor with shrinkage ($\eta = 0.15, M = 25$).
   - Exact Lundberg-Lee Tree SHAP decomposition traversing tree paths in $O(TLD^2)$ time.
   - Enforces mathematical additive efficiency:
     $$\mathbb{E}[Y] + \sum_{j=1}^K \phi_j(x) \equiv \hat{y}(x)$$
2. **Completion Delay Survival Model (`survival.py`)**:
   - Semi-parametric Cox Proportional Hazards regression model fitted via gradient ascent with $L_2$ regularization.
   - Breslow cumulative baseline hazard estimator $H_0(t)$ resolving continuous completion probabilities:
     $$S(t | X) = \exp(-H_0(t) e^{\beta^T X})$$
   - Computes delivery dates at $p_{50}$ (median), $p_{75}$ (conservative), and $p_{90}$ (high-confidence) percentiles.
   - Evaluated via Harrell's Concordance Index (C-index).
3. **Price Realization & CAGR Trajectory Engine (`pricing.py`)**:
   - Chronological quarterly aggregation of deed-level consideration from Form 3 filings.
   - Calculates Compound Annual Growth Rate (CAGR) and net appreciation percentage $\Delta P\%$.
   - Measures commercial-to-residential premiums (`retail_to_residential_ratio`, `office_to_residential_ratio`).
4. **Geospatial Micro-Market Analytics (`spatial.py`)**:
   - Great-Circle Haversine pairwise distance clustering over project coordinates.
   - Town Planning (TP) scheme aggregation calculating micro-market absorption rates and benchmark prices.
5. **Knowledge Graph Contagion Engine (`network.py`)**:
   - Multi-hop graph traversal over 21.8k vertices and 51k edges.
   - Traces shared technical professionals (Architects, Engineers, CAs) and flags `PROFESSIONAL_LINKED_COMPLAINT` risks when sister projects incur consumer litigation under RERA Section 31.

---

### 3.3 Statutory Forensic Audit Rules & Broker Claims Verification

The system codifies 10 deterministic statutory rules in `real_estate_intelligence/analytics/audit.py` and sales claim verification in `claims_checker.py`:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              STATUTORY FORENSIC AUDIT RULES                                     │
├────┬─────────────────────────────┬─────────────────┬──────────────────────┬─────────────────────┤
│ #  │ Forensic Check Name         │ Statutory Clause│ Input Data Sources   │ Severity & Trigger  │
├────┼─────────────────────────────┼─────────────────┼──────────────────────┼─────────────────────┤
│ 1  │ Financial Expenditure Drop  │ RERA Sec 4(2)(l)│ Sequential Form 3    │ HIGH: Incurred Cost │
│    │ / Cost Reversal             │                 │ in finances table    │ decreases over time │
│ 2  │ Construction Velocity       │ GujRERA Progress│ projects.velocity_   │ HIGH (<0.75x) /     │
│    │ Deficit                     │ Monitoring Regs │ ratio (engg/elapsed) │ MEDIUM (<0.90x)     │
│ 3  │ Escrow Account Liquidity    │ RERA Sec 4(2)(l)│ banks (Account 1     │ HIGH: Closing bal < │
│    │ Depletion                   │ Proviso 1       │ closing_bal)         │ ₹50k & progress <90%│
│ 4  │ Statutory Section 4(2)(l)(D)│ RERA Sec 4(2)(l)│ banks.withdrawal vs  │ CRITICAL: Cumulative│
│    │ Escrow Over-Withdrawal      │ Proviso 2       │ Form 1 % * Est Cost  │ withdrawals > allow │
│ 5  │ Completion Expired Without  │ RERA Section 4 /│ projects.completion  │ HIGH: Handover date │
│    │ Architect Form 4 Clearance  │ Form 4 Filing   │ vs documents_catalog │ passed without Form4│
│ 6  │ Active Consumer Complaints  │ RERA Section 31 │ applications (type = │ HIGH (>=2 complaints│
│    │                             │                 │ 'Complaint')         │ MEDIUM (1 complaint)│
│ 7  │ Sanctioned Layout           │ RERA Section 14 │ applications (type = │ MEDIUM: Post-reg    │
│    │ Alterations                 │ (2/3 consent)   │ 'Alteration')        │ layout amendments   │
│ 8  │ Quarterly Progress Report   │ RERA Section 11 │ projects.default_    │ MEDIUM: Quarters    │
│    │ (QPR) Default Penalties     │                 │ quarters_count       │ marked in default   │
│ 9  │ Overdue Form 5 CA Annual    │ RERA Sec 4(2)(l)│ form5_compliance     │ MEDIUM: Mandatory   │
│    │ Audit Submissions           │                 │ (status = 'ACTIVE')  │ audit pending >6 mos│
│ 10 │ Institutional Project Loans │ Encumbrance /   │ finances.loan_rows_  │ INFO: Bank charges  │
│    │ & Land Mortgages Disclosed  │ Title Security  │ count (Form 3 loans) │ on project assets   │
├────┴─────────────────────────────┴─────────────────┴──────────────────────┴─────────────────────┤
│ Broker Claim Verification (claims_checker.py):                                                  │
│ - Price Exaggeration: Claimed rate vs registered median unit deed (>15% premium, <-10% disc)    │
│ - Artificial Scarcity: Broker claimed sold % vs statutory booking rate (>10% inflation)        │
│ - Aggressive Handover Promises: Promised possession date earlier than statutory RERA deadline   │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### 3.4 Comprehensive Capability Gap Matrix

The following matrix maps every database table, quantitative model, and analytical service in the repository against its current MCP exposure, identifying the exact tools needed to bridge each gap:

| Asset Domain | Underlying Table / File | Current Volume | Exposed in MCP? | Exposed in Copilot? | Proposed Tool Name & Specification |
|---|---|---|---|---|---|
| **Project Search & Discovery** | `projects`, `project_summaries` | 17,787 rows | ❌ No | ❌ No | `search_projects(district, taluka, promoter, min_progress, has_complaints, limit, offset)`: Enables exploratory project discovery without knowing `project_id`. |
| **Market Screening** | `project_summaries` | 17,787 rows | ❌ No | ❌ No | `screen_market_projects(min_rate, max_rate, min_absorption, has_bu)`: Allows filtering projects by financial absorption and rate criteria. |
| **Unit-Level Deed Inspection** | `unit_transactions` | 1,952,528 rows | ❌ No | ❌ No | `query_unit_transactions(project_id, block, asset_class, status, min_rate, limit)`: Exposes raw deed consideration and registered rates. |
| **Broker Claim Fact-Checking** | `claims_checker.py` | Statutory Rule Engine | ❌ No | ❌ No | `verify_sales_claim(project_id, claimed_rate, claimed_sold_pct, claimed_completion_date)`: Directly exposes `SalesClaimVerifier`. |
| **Longitudinal Price CAGR** | `pricing.py` | 1.95M Deeds / Quarters | ❌ No | ❌ No | `get_pricing_appreciation_trend(project_id)`: Exposes quarterly median appreciation trajectories and CAGR percentages. |
| **Signer Credential Coverage** | `audit.py:audit_credential_coverage` | 15,565 Signers | ❌ No | ❌ No | `audit_credential_coverage(project_id)`: Verifies Council of Architecture numbers, municipal structural licenses, and CA Form 3 existence. |
| **Town Planning (TP) Scheme** | `spatial.py:get_tp_scheme_summary` | Geographic GIS | ❌ No | ❌ No | `get_tp_scheme_summary(tp_scheme, district)`: Aggregates absorption and pricing across contiguous TP schemes. |
| **Professional Track Record** | `professionals`, `graph_edges` | 15,565 Signers | ❌ No | ❌ No | `query_professional_track_record(role, name, license_no)`: Lists all projects signed by a specific architect, engineer, or CA. |
| **Promoter Portfolio Intelligence**| `promoters`, `projects` | 9 Promoters / 17.7k Proj | ❌ No | ❌ No | `get_promoter_portfolio(promoter_id, promoter_name)`: Returns all sister projects, delivery records, and default counts for a developer. |
| **Escrow Banking Network Audit** | `banks` | 17,739 Accounts | ❌ No | ❌ No | `audit_bank_escrow_exposure(bank_name, branch_ifsc)`: Evaluates systemic escrow exposure and deposit volume across banking branches. |
| **Document Provenance Audit** | `documents_catalog` | 789 Files with SHA-256 | ❌ No | ❌ No | `verify_document_provenance(doc_uid_hash, sha256)`: Validates document integrity and filing provenance. |
| **Regulatory Radar** | `server.py:get_regulatory_radar` | 17,787 Projects | ✅ Yes (Tool 8) | ❌ Missing | Wire `get_regulatory_radar` into `GEMINI_TOOLS` and `OPENAI_TOOLS`. |
| **Comparative Project Analysis** | `server.py:compare_projects` | 17,787 Projects | ✅ Yes (Tool 9) | ❌ Missing | Wire `compare_projects` into `GEMINI_TOOLS` and `OPENAI_TOOLS`. |
| **Spatial Micro-Market Density** | `server.py:get_spatial_density` | GIS Distances | ✅ Yes (Tool 13)| ❌ Missing | Wire `get_spatial_density` into `GEMINI_TOOLS` and `OPENAI_TOOLS`. |
| **Full-Text Document Search** | `document_fts` (FTS5 Table) | 0 Rows (Unindexed) | ⚠️ Broken | ⚠️ Empty | Execute offline PDF batch indexing worker to populate `document_fts` with 789 cataloged statutory filings. |

---

### 3.5 Specialized Agent Skills Architecture

To transition from a monolithic copilot into an autonomous multi-agent intelligence ecosystem, the platform will define four specialized agent skills. Each skill encapsulates dedicated domain heuristics, tool bindings, and verification protocols:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               SPECIALIZED AGENT SKILLS TOPOLOGY                                 │
├───────────────────────────────┬─────────────────────────────────┬───────────────────────────────┤
│ Skill Name                    │ Bound MCP Tools                 │ Autonomous Reasoning Protocol │
├───────────────────────────────┼─────────────────────────────────┼───────────────────────────────┤
│ 1. forensic-auditor-skill     │ audit_discrepancies             │ 1. Inspect Bank 70% Escrow    │
│                               │ get_escrow_health               │ 2. Evaluate Form 3 Spend Drop │
│                               │ calculate_escrow_runway         │ 3. Check Section 4 Over-Draw  │
│                               │ audit_credential_coverage       │ 4. Compute Cash Burn Runway   │
│                               │ get_regulatory_radar            │ 5. Flag QPR / Form 5 Defaults │
├───────────────────────────────┼─────────────────────────────────┼───────────────────────────────┤
│ 2. real-estate-valuation-skill│ predict_pricing_benchmark       │ 1. Retrieve Deed Transactions │
│                               │ verify_sales_claim              │ 2. Fit Hedonic GBDT Model     │
│                               │ get_pricing_appreciation_trend  │ 3. Compute Exact Tree SHAP    │
│                               │ query_unit_transactions         │ 4. Cross-Check Broker Claims  │
│                               │ get_spatial_density             │ 5. Project CAGR Trajectory    │
├───────────────────────────────┼─────────────────────────────────┼───────────────────────────────┤
│ 3. delivery-forecaster-skill  │ forecast_completion_delay       │ 1. Compute Velocity Ratio Vr  │
│                               │ get_project_dossier             │ 2. Evaluate Incurred Cost %   │
│                               │ get_regulatory_radar            │ 3. Fit Cox Hazard Model       │
│                               │ compare_projects                │ 4. Project p50, p75, p90 Dates│
│                               │                                 │ 5. Quantify Delay Risk Label  │
├───────────────────────────────┼─────────────────────────────────┼───────────────────────────────┤
│ 4. rera-evidence-verifier-    │ search_document_evidence        │ 1. Verify Document SHA-256    │
│    skill                      │ verify_document_provenance      │ 2. Extract Exact Page Snippet │
│                               │ get_land_records                │ 3. Validate Citation Schema   │
│                               │ trace_entity_network            │ 4. Enforce Zero-Hallucination │
└───────────────────────────────┴─────────────────────────────────┴───────────────────────────────┘
```

#### Detailed Skill Specifications

##### 1. `forensic-auditor-skill`
- **Objective**: Conduct rigorous statutory audits across RERA Section 4(2)(l)(D) escrow retention, expenditure drops, QPR default streaks, Section 14 alterations, and professional credential coverage.
- **Workflow Protocol**:
  1. Fetch banking accounts and partition into Account Type 1 (70% retention) and Type 2 (collection).
  2. Query chronological Form 3 CA filings and check for cost reversals ($\Delta C_{\text{incurred}} < 0$).
  3. Compare cumulative withdrawals against allowable cost allocation ($C_{\text{est}} \times P_{\text{engg}} \times 1.05$).
  4. Compute monthly burn rate and project escrow cash runway in months.
  5. Audit professional credentials (CoA numbers, municipal licenses, Form 3 presence).
  6. Return structured findings with severity classifications (`CRITICAL`, `HIGH`, `MEDIUM`, `INFO`).

##### 2. `real-estate-valuation-skill`
- **Objective**: Establish econometric property valuations, benchmark unit rate per sq.ft, break down Tree SHAP drivers, and fact-check broker claims against certified deeds.
- **Workflow Protocol**:
  1. Retrieve registered unit transaction deeds for the project from `unit_transactions`.
  2. Execute hedonic GBDT regression inference to establish the fair-market baseline rate.
  3. Decompose marginal price premiums and discounts using exact Lundberg-Lee Tree SHAP.
  4. Query Great-Circle Haversine neighbors within a 3.0 km radius to establish micro-market bounds.
  5. If marketing claims are supplied, execute `verify_sales_claim` to detect price inflation, artificial scarcity, or unrealistic handover timelines.

##### 3. `delivery-forecaster-skill`
- **Objective**: Forecast realistic project completion timelines, calculate construction velocity ratios, and output p50, p75, and p90 delivery percentiles.
- **Workflow Protocol**:
  1. Compute the empirical construction velocity ratio $V_r = \frac{P_{\text{engg}}}{T_{\text{elapsed}}}$.
  2. Compute the financial expenditure ratio $C_{\text{ratio}} = \frac{C_{\text{incurred}}}{C_{\text{est}}}$.
  3. Query active consumer complaints under Section 31 and quarterly default penalty counts.
  4. Evaluate the Cox proportional hazards model and Breslow baseline cumulative hazard.
  5. Project discrete delivery dates for median ($p_{50}$), conservative ($p_{75}$), and high-confidence ($p_{90}$) percentiles.

##### 4. `rera-evidence-verifier-skill`
- **Objective**: Inspect document provenance, verify cryptographic SHA-256 hashes in `documents_catalog`, and ensure all reported claims carry grounded evidentiary citations.
- **Workflow Protocol**:
  1. Query `documents_catalog` for certified statutory filing references.
  2. Confirm file integrity by matching SHA-256 cryptographic hashes.
  3. Query FTS5 virtual tables to extract exact page text snippets and clause references.
  4. Intercept outbound agent statements to ensure every numeric metric is bound to a validated `EvidentiaryClaimCitation` payload.

---

## 4. Deep Data Analysis & Hidden Insights Execution Plan

### 4.1 Forensic Risk Signals & Anomaly Detection Methodologies

```
═══════════════════════════════════════════════════════════════════════════════════════════════════
                              FORENSIC RISK SIGNAL PIPELINE
═══════════════════════════════════════════════════════════════════════════════════════════════════

   [ Sworn Form 1Filings ]       [ Sworn Form 3 Filings ]       [ Escrow Bank Passbooks ]
   Physical Progress % (Pengg)   Cumulative Spend (Cincurred)   Withdrawals & Balances
              │                             │                             │
              ├─────────────────────────────┼─────────────────────────────┤
              ▼                             ▼                             ▼
┌───────────────────────────┐ ┌───────────────────────────┐ ┌───────────────────────────┐
│ Construction Velocity Vr  │ │ Cost Reversal Check       │ │ Escrow Over-Withdrawal    │
│ Vr = Pengg / Telapsed     │ │ ΔCincurred = Ct - Ct-1    │ │ Wexcess = Wwithdrawn -    │
│ Vr < 0.75x -> Critical    │ │ ΔCincurred < 0 -> Tamper  │ │           1.05*(Cest*Pengg) │
└─────────────┬─────────────┘ └─────────────┬─────────────┘ └─────────────┬─────────────┘
              │                             │                             │
              └─────────────────────────────┼─────────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                            BAYESIAN PROMOTER CONTAGION ENGINE                                   │
│  Prior Delivery Rate: θ ~ Beta(5, 2)                                                            │
│  Posterior Updating: θ|D ~ Beta(5 + s, 2 + f) across Developer Portfolio Schemes                │
│  Cross-Scheme Contagion: ContagionRisk(P) = Σ wk * [ I(Rk < 3) + I(Vr,k < 0.75) + 0.5*Complaints]│
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### 1. Construction Velocity Dynamics
The platform quantifies construction pace by benchmarking physical engineering progress against calendar time consumption:

$$\text{Time Elapsed Ratio } T_{\text{elapsed}} = \frac{t_{\text{current}} - t_{\text{start}}}{t_{\text{completion}} - t_{\text{start}}}$$

$$\text{Velocity Ratio } V_r = \frac{P_{\text{engg}}}{T_{\text{elapsed}} \times 100}$$

- **Threshold Classification**:
  - $V_r \ge 0.90\text{x}$: **ON TRACK** — Construction pace satisfies registered timeline.
  - $0.75\text{x} \le V_r < 0.90\text{x}$: **MODERATE DELAY** — Project pacing reflects a 3-to-6 month expected slippage.
  - $V_r < 0.75\text{x}$: **CRITICAL DELAY DEFICIT** — Severe structural deficit; mandatory intervention trigger.

- **Progress Stagnation Index**:
  $$\Delta P_q = P_q - P_{q-1}$$
  If $\Delta P_q < 1.0\%$ across $\ge 2$ consecutive quarters while $T_{\text{elapsed}} < 100\%$, the project is flagged for **Critical Site Paralysis**.

- **Calendar Overrun Slippage**:
  $$\text{Slippage (Months)} = \max\left(0, \frac{t_{\text{current}} - t_{\text{completion}}}{30.4375}\right)$$

#### 2. Statutory Escrow Siphoning & Section 4(2)(l)(D) Over-Withdrawal
Under RERA Section 4(2)(l)(D), 70% of all real estate receivables must be deposited into a designated bank account and withdrawn strictly in proportion to the percentage of completion:

$$\text{Allowable Withdrawal } W_{\text{allowable}} = C_{\text{estimated}} \times \left(\frac{P_{\text{engg}}}{100}\right)$$

$$\text{Excess Siphoning Delta } \Delta W_{\text{excess}} = \max\left(0, W_{\text{withdrawn}} - 1.05 \cdot W_{\text{allowable}}\right)$$

- When $\Delta W_{\text{excess}} > 0$, a statutory discrepancy of severity `CRITICAL` is generated.
- **Financial Expenditure Reversals**:
  $$\Delta C_{\text{incurred}} = C_{\text{incurred}, t} - C_{\text{incurred}, t-1}$$
  If $\Delta C_{\text{incurred}} < 0$, it indicates retroactive balance-sheet restatement or Form 3 certification tampering.

#### 3. Escrow Cash Runway & Monthly Construction Burn
The monthly cash consumption is evaluated across sequential Form 3 milestones:

$$\text{Monthly Burn Rate } B_{\text{monthly}} = \frac{C_{\text{incurred}, t} - C_{\text{incurred}, t-1}}{\Delta t_{\text{months}}} \quad \left(\text{or } \frac{C_{\text{incurred}}}{12.0} \text{ if single filing}\right)$$

$$\text{Remaining Liability } C_{\text{rem}} = \max(0.0, C_{\text{estimated}} - C_{\text{incurred}})$$

$$\text{Escrow Runway (Months)} = \frac{\text{Closing Balance in Account Type 1}}{B_{\text{monthly}}}$$

- **Insolvency Risk**:
  - `CRITICAL`: Runway $< 3.0$ months and physical progress $< 95\%$.
  - `MODERATE`: Runway $< 6.0$ months.
  - `LOW`: Runway $\ge 6.0$ months.

#### 4. Bayesian Promoter Track Record & Cross-Scheme Contagion Scoring
Developers operating multiple projects frequently siphon capital between active SPVs. To model developer track record uncertainty, we implement Bayesian Beta-Binomial updating:
- **Prior Distribution**:
  $$\theta \sim \text{Beta}(\alpha_0, \beta_0), \quad \alpha_0 = 5.0, \; \beta_0 = 2.0$$
- **Posterior Updating**:
  Given developer portfolio history $\mathcal{D} = \{s \text{ on-time completions}, f \text{ delayed/defaulted schemes}\}$:
  $$\theta | \mathcal{D} \sim \text{Beta}(\alpha_0 + s, \beta_0 + f)$$
  $$\text{Expected Promoter Reliability } \mathbb{E}[\theta | \mathcal{D}] = \frac{\alpha_0 + s}{\alpha_0 + \beta_0 + s + f}$$
- **Capital-Weighted Contagion Risk Score**:
  For developer portfolio $\mathcal{P} = \{p_1, \dots, p_K\}$:
  $$\text{ContagionRisk}(\mathcal{P}) = \sum_{k=1}^K w_k \cdot \left[ \mathbb{I}(\text{Runway}_k < 3) + \mathbb{I}(V_{r,k} < 0.75) + 0.5 \cdot \text{Complaints}_k \right]$$
  where the capital weighting $w_k$ incorporates an explicit zero-division guard:
  $$w_k = \begin{cases} \frac{\text{Cost}_k}{\sum_{i=1}^K \text{Cost}_i} & \text{if } \sum_{i=1}^K \text{Cost}_i > 0 \\ \frac{1}{K} & \text{otherwise} \end{cases}$$
  This piecewise formulation directly accommodates the empirical finding that exactly 51 projects in the GujRERA database have zero or unreported estimated costs ($\text{Cost}_k = 0$), defaulting to uniform portfolio weighting ($1/K$) when the developer portfolio's aggregate estimated cost is zero.

---

### 4.2 Quantitative Valuation & Market Econometrics

#### 1. Log-Linear Hedonic Pricing Model (Rosen, 1974)
To capture marginal implicit prices across structural and geographic attributes, the econometric baseline is specified as:

$$\ln(P_{ijt}) = \alpha + \beta_1 \ln(\text{Area}_{ijt}) + \sum_{k} \gamma_k \text{AssetClass}_{ijk} + \sum_{m} \delta_m X_{jm} + \sum_{d} \theta_d \text{District}_{jd} + \lambda_t + \epsilon_{ijt}$$

where:
- $P_{ijt}$: Registered deed transaction rate (INR/sq.ft) for unit $i$ in project $j$ at quarter $t$.
- $\text{Area}_{ijt}$: Carpet area in square feet.
- $\text{AssetClass}$: Indicator vector for Residential, Commercial Office, Commercial Retail, and Industrial Warehouse.
- $X_{jm}$: Project characteristics (velocity ratio $V_r$, physical progress %, developer scale, amenities).
- $\lambda_t$: Quarterly macroeconomic fixed effects.
- $\frac{\partial P}{\partial X_k} = \gamma_k \cdot P$: The marginal percentage price premium for attribute $k$.

#### 2. Gradient Boosted Trees with Exact Additive Tree SHAP Decomposition
While linear hedonic models provide baseline coefficients, non-linear interactions (e.g. prime corridor premiums attenuating for delayed developers) are modeled using Gradient Boosted Decision Trees (GBDT).

In `real_estate_intelligence/analytics/ml_pricing.py`, the ensemble predicts rate per square foot $\hat{y}(x)$. Feature contributions are decomposed using exact Lundberg-Lee Tree SHAP:

$$\hat{y}(x) = \phi_0 + \sum_{i=1}^D \phi_i(x)$$

where:
- $\phi_0 = \mathbb{E}[Y]$: The statewide base market expected price ($₹3,842/\text{sq.ft}$).
- $\phi_i(x)$: The exact additive marginal contribution of feature $i$.
- **Additive Efficiency Guarantee**:
  $$\left| \left( \phi_0 + \sum_{i=1}^D \phi_i(x) \right) - \hat{y}(x) \right| < 10^{-4}$$
This allows an agent to explain property valuation with exact monetary attribution (e.g. "Base rate ₹3,842 + Commercial Retail premium ₹850 - Construction velocity deficit ₹320 = Final valuation ₹4,372/sq.ft").

#### 3. Spatial Econometric Models (SAR / SEM)
Property values exhibit strong spatial auto-correlation. To model geographic spillover across Town Planning (TP) schemes:
- **Spatial Autoregressive (SAR) Model**:
  $$Y = \rho W Y + X \beta + \epsilon, \quad \epsilon \sim \mathcal{N}(0, \sigma^2 I)$$
  where $W$ is the standardized inverse-distance spatial weight matrix:
  $$w_{ij} = \begin{cases} \frac{1}{d_{ij}^2} & \text{if } d_{ij} \le 3.0\text{ km} \\ 0 & \text{otherwise} \end{cases}$$
  The parameter $\rho$ measures the direct price contagion of neighboring developments.
- **Spatial Error Model (SEM)**:
  $$Y = X \beta + u, \quad u = \lambda W u + \epsilon$$
  Captures spatially correlated unobserved amenities (e.g. proximity to Gandhinagar GIFT City or Ahmedabad Metro corridors).

#### 4. Inventory Velocity & Months of Inventory (MOI)
- **Project Absorption Rate**:
  $$A = \frac{\text{Booked Units}}{\text{Total Registered Units}} \times 100$$
- **Quarterly Sales Velocity**:
  $$V_{\text{sales}} = \frac{\Delta \text{Booked Units}}{\Delta t_{\text{quarter}}}$$
- **Months of Remaining Inventory (Inventory Overhang)**:
  $$\text{MOI} = \frac{\text{Unbooked Units}}{V_{\text{sales, monthly}}}$$
  - $\text{MOI} < 6$ months: High-demand seller's micro-market.
  - $6 \le \text{MOI} \le 18$ months: Balanced equilibrium market.
  - $\text{MOI} > 18$ months: High inventory overhang / buyer's market.

---

### 4.3 Delivery Forecasting & Survival Analytics

#### 1. Non-Parametric Baseline: Kaplan-Meier Estimator & Greenwood Variance
Prior to conditioning on project-specific covariates via proportional hazards, the empirical baseline completion trajectory across all registered projects is quantified using the non-parametric Kaplan-Meier product-limit estimator:

$$\hat{S}(t) = \prod_{t_i \le t} \left( 1 - \frac{d_i}{n_i} \right)$$

where $d_i$ represents the number of observed completions at event time $t_i$, and $n_i$ represents the number of active, uncompleted (at-risk) projects immediately prior to $t_i$.

To quantify estimator uncertainty and construct rigorous statistical confidence intervals around the survival curve, standard error and variance are derived using Greenwood's formula:

$$\widehat{\text{SE}}(\hat{S}(t)) = \hat{S}(t) \sqrt{ \sum_{t_i \le t} \frac{d_i}{n_i (n_i - d_i)} }$$

$$\widehat{\text{Var}}(\hat{S}(t)) = \hat{S}(t)^2 \sum_{t_i \le t} \frac{d_i}{n_i (n_i - d_i)}$$

The $(1 - \alpha)$ Wald confidence interval for project survival probability at milestone $t$ is then bounded by $\hat{S}(t) \pm z_{1-\alpha/2} \cdot \widehat{\text{SE}}(\hat{S}(t))$.

#### 2. Semi-Parametric Cox Proportional Hazards Model
Project delivery timelines are subject to right-censoring: projects currently under construction have not yet experienced the "completion event" ($E_i = 1$). Standard regression leads to severe survivor bias.

In `real_estate_intelligence/analytics/survival.py`, delivery hazard is modeled via Cox Proportional Hazards:

$$h(t | X) = h_0(t) \exp\left( \beta^T X \right)$$

where the covariate vector $X$ incorporates:
1. $X_1 = V_r$: Construction velocity ratio.
2. $X_2 = C_{\text{ratio}}$: Incurred cost ratio ($\min(1.5, C_{\text{incurred}} / C_{\text{est}})$).
3. $X_3 = \mathbb{I}(\text{Complaints} > 0)$: Binary consumer litigation indicator.
4. $X_4 = \text{DefaultQuarters}$: Count of penalized quarterly filing defaults.

#### 3. Parameter Estimation & Breslow Cumulative Hazard
- **Partial Log-Likelihood Optimization**:
  $$\ell(\beta) = \sum_{i: E_i = 1} \left[ \beta^T X_i - \ln\left( \sum_{j \in R(t_i)} \exp(\beta^T X_j) \right) \right] - \frac{\lambda}{2} \|\beta\|_2^2$$
  Solved via gradient ascent with $L_2$ regularization ($\lambda = 0.05$).
- **Breslow Baseline Cumulative Hazard Estimator**:
  At each discrete completion time $t$:
  $$d H_0(t) = \frac{d_t}{\sum_{j \in R(t)} \exp(\beta^T X_j)}$$
  $$H_0(t) = \sum_{t_i \le t} d H_0(t_i)$$
- **Survival Function**:
  $$S(t | X) = \exp\left( - H_0(t) \cdot \exp(\beta^T X) \right)$$
  The probability of completion by month $t$ is $F(t | X) = 1 - S(t | X)$.

#### 4. Forecasting Completion Percentiles
The model calculates exact future handover dates by inverting the survival function:
- **p50 (Median Expected Completion)**: Smallest $t$ where $F(t | X) \ge 0.50$.
- **p75 (Conservative Delivery Horizon)**: Smallest $t$ where $F(t | X) \ge 0.75$.
- **p90 (High-Confidence Horizon)**: Smallest $t$ where $F(t | X) \ge 0.90$.
- **Projected Delay Horizon**:
  $$\Delta T_{\text{delay}} = t_{p50} - \text{Registered Statutory Handover Date}$$

---

### 4.4 Analytical Feature Pipelines & SQL Materialization

To support real-time MCP tool execution and sub-50ms model inferences across 17,787 projects, the following analytical SQL view materializes all core forensic, financial, and econometric covariates.

*(Note on relational integrity: Escrow retention bank accounts are aggregated in a subquery grouped by `project_id` rather than a raw join to prevent Cartesian row multiplication for projects possessing multiple Section 4(2)(l)(D) accounts, preserving exact 17,787 project cardinality. Promoter name is resolved via `pr.name AS promoter_name`, and deed pricing statistics retain `min_rate_sqft_booked` and `avg_rate_sqft_booked` from `project_summaries`)*:

```sql
-- DDL: v_analytics_project_features
-- Materializes project-level forensic, financial, and econometric covariates
CREATE VIEW IF NOT EXISTS v_analytics_project_features AS
SELECT 
    p.project_id,
    p.name,
    p.district,
    p.taluka,
    p.promoter_id,
    pr.name AS promoter_name,
    pr.total_projects_claimed,
    p.latest_form_one_progress_pct AS progress_pct,
    p.velocity_ratio,
    p.time_elapsed_pct,
    p.complaints_count,
    p.alterations_count,
    p.extensions_count,
    p.default_quarters_count,
    p.estimated_cost_inr,
    p.incurred_cost_inr,
    CASE 
        WHEN p.estimated_cost_inr > 0 THEN ROUND(p.incurred_cost_inr / p.estimated_cost_inr, 4)
        ELSE 0.0 
    END AS cost_incurred_ratio,
    s.absorption_pct,
    s.min_rate_sqft_booked,
    s.avg_rate_sqft_booked,
    COALESCE(b.escrow_closing_balance, 0.0) AS escrow_closing_balance,
    COALESCE(b.escrow_withdrawal_amt, 0.0) AS escrow_withdrawal_amt,
    CASE 
        WHEN p.estimated_cost_inr > 0 AND p.latest_form_one_progress_pct > 0 THEN 
            ROUND(COALESCE(b.escrow_withdrawal_amt, 0.0) - (p.estimated_cost_inr * (p.latest_form_one_progress_pct / 100.0)), 2)
        ELSE 0.0
    END AS escrow_over_withdrawal_inr
FROM projects p
LEFT JOIN project_summaries s ON p.project_id = s.project_id
LEFT JOIN promoters pr ON p.promoter_id = pr.promoter_id
LEFT JOIN (
    SELECT 
        project_id, 
        SUM(closing_bal) AS escrow_closing_balance, 
        SUM(withdrawal_amt) AS escrow_withdrawal_amt
    FROM banks 
    WHERE account_type = 1 
    GROUP BY project_id
) b ON p.project_id = b.project_id;
```

---

## 5. Internal & External Agent Serving Architecture

### 5.1 FastMCP Gateway & Dual-Transport Architecture (stdio & SSE)

To make `real_estate_intelligence` directly accessible to external AI agents (e.g. Claude Desktop, Cursor, and enterprise LLM orchestrators), the platform will implement an official Model Context Protocol gateway using `FastMCP`.

```
═══════════════════════════════════════════════════════════════════════════════════════════════════
                              DUAL-TRANSPORT MCP SERVING TOPOLOGY
═══════════════════════════════════════════════════════════════════════════════════════════════════

   [ Local CLI / Desktop Agent ]                                 [ Remote Network Agent ]
      (Claude Desktop / Cursor)                                  (Multi-Agent Cloud Pods)
                 │                                                          │
                 │ stdio Stream (stdin/stdout)                              │ HTTP POST & SSE Stream
                 ▼                                                          ▼
┌───────────────────────────────────────────────┐          ┌────────────────────────────────────────┐
│             stdio Transport Runner            │          │        Server-Sent Events (SSE)        │
│   (real_estate_intelligence/mcp/stdio_server) │          │     FastAPI Endpoint: GET /sse         │
└───────────────────────┬───────────────────────┘          └───────────────────┬────────────────────┘
                        │                                                      │
                        └───────────────────────┬──────────────────────────────┘
                                                │
                                                ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       FASTMCP GATEWAY CORE                                        │
│  ├── Dynamic JSON Schema Validation                                                               │
│  ├── Privacy & PII Redaction Interceptor (Masks Bank Accounts, Allottee Tokenization)              │
│  ├── Zero-Hallucination Evidentiary Citation Verification Guardrail                               │
│  └── Dispatches to RealEstateIntelligenceMCP (server.py) and Analytical Engines                    │
└───────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Dual Transport Specifications
1. **Transport 1: Standard Input/Output (`stdio`)**:
   - Implemented in `real_estate_intelligence/mcp/stdio_server.py`.
   - Executable via: `python -m real_estate_intelligence.mcp.stdio_server`.
   - Provides instant, zero-latency tool execution for local desktop coding agents.
   - Claude Desktop Configuration snippet:
     ```json
     {
       "mcpServers": {
         "gujrera": {
           "command": "d:\\Code Projects\\Miscellaneous\\Real Estate Data\\gujRERA\\.venv\\Scripts\\python.exe",
           "args": ["-m", "real_estate_intelligence.mcp.stdio_server"],
           "env": {
             "DEFAULT_DB_PATH": "d:\\Code Projects\\Miscellaneous\\Real Estate Data\\gujRERA\\data\\intelligence.sqlite"
           }
         }
       }
     }
     ```
2. **Transport 2: Server-Sent Events (`SSE`)**:
   - Mounted onto the existing FastAPI server (`api/index.py`) at `/sse` and `/messages`.
   - Runs on host `127.0.0.1`, port `8765`.
   - Enables distributed subagents across local networks or VPCs to establish persistent event-stream connections.

---

### 5.2 MCP Resource URI Hierarchy (`rera://...`)

In accordance with the Model Context Protocol specification, standard data assets should be exposed as readable **MCP Resources** in addition to executable tools:

```
rera://
├── project/
│   └── {project_id}/
│       ├── dossier          -> Complete 4-quadrant diligence markdown text
│       ├── forensic         -> Structured discrepancy leads JSON
│       ├── escrow           -> Section 4(2)(l)(D) banking & cash runway metrics
│       ├── pricing          -> Unit deed distributions and hedonic ML predictions
│       └── survival         -> 120-month survival probabilities & handover percentiles
├── promoter/
│   └── {promoter_id}/
│       └── portfolio        -> Master portfolio schemes, delivery records, defaults
├── documents/
│   └── {doc_uid_hash}/
│       └── manifest         -> Certified filing metadata, page counts, SHA-256 hash
└── spatial/
    └── {district}/
        └── tp_schemes       -> Aggregated absorption & benchmark rates per TP scheme
```

---

### 5.3 Multi-Agent Orchestration Topology & Subagent Routing

For complex diligence tasks (e.g. "Conduct a comprehensive statutory and econometric risk audit for promoter XYZ in Gandhinagar"), a hierarchical multi-agent architecture will coordinate specialized subagents:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 ORCHESTRATOR / ROOT AGENT                                       │
│  Receives high-level user objective; decomposes inquiry into specialized analytical sub-tasks.   │
└───────────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                                │
                ┌───────────────────────────────┼───────────────────────────────┐
                │                               │                               │
                ▼                               ▼                               ▼
┌───────────────────────────────┐ ┌───────────────────────────────┐ ┌───────────────────────────────┐
│   Forensic Auditor Subagent   │ │   Valuation Engine Subagent   │ │   Delivery Forecaster Subagent│
│ - Audits Escrow Account 1     │ │ - Queries Unit Deed Ledger    │ │ - Calculates Velocity Vr    │
│ - Checks Section 4 Over-Draw  │ │ - Fits Hedonic GBDT & TreeSHAP│ │ - Evaluates Incurred Cost % │
│ - Verifies Credential Coverage│ │ - Fact-Checks Broker Claims   │ │ - Fits Cox Proportional Haz │
│ - Flags QPR / Form 5 Defaults │ │ - Projects CAGR Realization   │ │ - Estimates p50, p75, p90   │
└───────────────┬───────────────┘ └───────────────┬───────────────┘ └───────────────┬───────────────┘
                │                                 │                                 │
                └───────────────────────────────┬─┴─────────────────────────────────┘
                                                │
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             EVIDENTIARY CITATION & SYNTHESIS AGENT                              │
│  - Inspects document catalog for cryptographic SHA-256 provenance hashes.                       │
│  - Verifies that all assertions adhere to EvidentiaryClaimCitation JSON Schema.                 │
│  - Formats unified, executive-grade Markdown Due Diligence Dossier.                             │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### 5.4 Zero-Hallucination Evidentiary Citation Contract

To enforce statutory audit integrity, all subagent assertions and MCP tool outputs must be bound to verifiable legal citations. Unsubstantiated claims are rejected by the serving gateway.

#### Evidentiary Citation JSON Schema Specification
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "EvidentiaryClaimCitation",
  "description": "Statutory audit citation enforcing zero-hallucination factual grounding for GujRERA analytics.",
  "type": "object",
  "properties": {
    "claim_statement": {
      "type": "string",
      "description": "Verbatim analytical finding or factual assertion."
    },
    "metric_value": {
      "type": ["number", "string", "null"],
      "description": "Exact quantitative figure (e.g. INR rate, percentage, runway months)."
    },
    "evidence": {
      "type": "object",
      "properties": {
        "source_filing_form": {
          "type": "string",
          "enum": [
            "Form 1 Architect",
            "Form 2 Engineer",
            "Form 3 CA",
            "Form 4 Completion",
            "Form 5 Annual Audit",
            "Portal Master Registry",
            "Bank Passbook Schedule",
            "Municipal BU NOC"
          ]
        },
        "project_id": {
          "type": "integer",
          "description": "Target GujRERA project ID."
        },
        "table_name": {
          "type": "string",
          "description": "Relational table containing ground-truth record."
        },
        "record_id": {
          "type": ["integer", "string"],
          "description": "Primary key identifier of the evidence row."
        },
        "filing_date": {
          "type": ["string", "null"],
          "description": "ISO date of the certified statutory submission."
        },
        "document_sha256": {
          "type": ["string", "null"],
          "description": "SHA-256 cryptographic hash of the source PDF document."
        },
        "statutory_reference_clause": {
          "type": ["string", "null"],
          "description": "Specific clause (e.g. RERA Section 4(2)(l)(D), Section 14, Section 31)."
        },
        "confidence_score": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 1.0,
          "description": "Degree of verification certainty (1.0 = sworn certified deed)."
        }
      },
      "required": ["source_filing_form", "project_id", "table_name", "confidence_score"]
    }
  },
  "required": ["claim_statement", "evidence"]
}
```

---

### 5.5 Privacy, Banking Masking & PII Redaction Interceptors

Under Invariant 2.3 of the Sovereign Real Estate Intelligence platform specification, consumer privacy and sensitive financial credentials must be protected before data leaves the SQLite/Turso layer:

```python
class PIIRedactionInterceptor:
    """Intercepts relational records and applies strict PII redaction rules."""
    
    @staticmethod
    def redact_bank_account(account_number: Optional[str]) -> str:
        if not account_number:
            return "UNSPECIFIED"
        clean = re.sub(r"\s+", "", str(account_number))
        if len(clean) <= 4:
            return "****"
        return f"**** **** **** {clean[-4:]}"
        
    @staticmethod
    def tokenize_allottee(name: Optional[str]) -> str:
        if not name:
            return "Anonymous_Allottee"
        token = hashlib.sha256(name.strip().upper().encode("utf-8")).hexdigest()[:8]
        return f"Allottee_{token}"
        
    @staticmethod
    def filter_kyc_fields(record: Dict[str, Any]) -> Dict[str, Any]:
        """Strips Aadhaar, PAN, phone numbers, and personal KYC identifiers."""
        forbidden_keys = {"pan_number", "aadhaar_number", "mobile_number", "kyc_doc_id", "personal_email"}
        return {k: v for k, v in record.items() if k.lower() not in forbidden_keys}
```
*Note*: Sworn public certifiers (Council of Architecture registered Architects, Structural Engineers, and CAs) are explicitly **not** redacted, as their professional identity and registration numbers represent public regulatory certifications under GujRERA statutory mandates.

---

## 6. Actionable Implementation Roadmap & Milestone Schedule

### 6.1 Phased Execution Breakdown

The implementation roadmap is divided into three distinct, non-breaking phases designed to maintain 100% test suite pass rates throughout development. Note that while the current repository currently operates without an external MCP SDK dependency, adding `mcp>=1.0.0` or `fastmcp>=0.1.0` to `pyproject.toml` dependencies is the recommended first step in Phase 1 implementation to furnish standard `stdio` and `SSE` server transports.

```
═══════════════════════════════════════════════════════════════════════════════════════════════════
                              PHASED IMPLEMENTATION TIMELINE
═══════════════════════════════════════════════════════════════════════════════════════════════════

  Phase 1: Transport & Registry Alignment (Immediate / Priority 1)
  ├── Add mcp>=1.0.0 or fastmcp>=0.1.0 to pyproject.toml dependencies
  ├── Register missing tools (compare_projects, get_regulatory_radar, get_spatial_density)
  ├── Implement FastMCP stdio transport (real_estate_intelligence/mcp/stdio_server.py)
  └── Mount SSE endpoints on FastAPI server (GET /sse, POST /messages)
  
  Phase 2: Tool Expansion & Analytical Views (Priority 2)
  ├── Deploy v_analytics_project_features view in database.py / schema.py
  ├── Implement search_projects and screen_market_projects exploratory tools
  ├── Wire claims_checker.py (verify_sales_claim) and pricing.py (get_pricing_appreciation_trend)
  ├── Implement audit_credential_coverage, get_tp_scheme_summary, and get_promoter_portfolio
  └── Execute offline PDF FTS5 batch indexing worker to populate document_fts
  
  Phase 3: Multi-Agent Serving & Specialized Skills (Priority 3)
  ├── Author 4 specialized agent skills (forensic-auditor, valuation, forecaster, evidence)
  ├── Implement EvidentiaryClaimCitation JSON Schema validation guardrails
  └── Enforce PIIRedactionInterceptor on all outbound tool responses
```

#### Detailed Milestone Specifications

| Phase | Milestone Name | Concrete Deliverables | Validation Criteria |
|---|---|---|---|
| **Phase 1** | **MCP Core Transport & Copilot Alignment** | 1. Add `mcp>=1.0.0` or `fastmcp>=0.1.0` to `pyproject.toml` dependencies (recommended first step to provide the external MCP protocol SDK runtime).<br>2. Update `real_estate_intelligence/agent/copilot.py` to register `compare_projects`, `get_regulatory_radar`, and `get_spatial_density` in `GEMINI_TOOLS` and `OPENAI_TOOLS`.<br>3. Build `real_estate_intelligence/mcp/stdio_server.py` exposing stdio transport.<br>4. Add SSE transport endpoint in `api/index.py`. | - LLM copilot successfully dispatches all 13 tools.<br>- Claude Desktop / Cursor connects via stdio.<br>- Existing 64 pytest tests pass with zero regressions. |
| **Phase 2** | **Tool Suite Expansion & Materialized Views** | 1. Materialize `v_analytics_project_features` view in SQLite.<br>2. Implement 9 new MCP tools in `server.py` (`search_projects`, `screen_market_projects`, `query_unit_transactions`, `verify_sales_claim`, `get_pricing_appreciation_trend`, `audit_credential_coverage`, `get_tp_scheme_summary`, `get_promoter_portfolio`, `verify_document_provenance`).<br>3. Run offline document indexing to populate `document_fts`. | - `RealEstateIntelligenceMCP` exposes 22 comprehensive tools.<br>- Exploratory discovery queries execute in $< 50\text{ms}$.<br>- `search_document_evidence` returns verified text snippets. |
| **Phase 3** | **Multi-Agent Orchestration & Guardrails** | 1. Create skill definitions in `.gemini/config/skills/` for the 4 specialized skills.<br>2. Implement hierarchical orchestrator routing.<br>3. Deploy `PIIRedactionInterceptor` and `EvidentiaryClaimCitation` validation middleware. | - Subagents autonomously complete end-to-end statutory audits.<br>- Zero unmasked bank accounts or allottee PII emitted.<br>- 100% of analytical claims include verified citation tokens. |

---

### 6.2 Architectural Risk Register & Mitigation Strategy

| # | Identified Architectural Risk | Severity | Potential Impact | Technical Mitigation Strategy |
|---|---|---|---|---|
| 1 | **Windows WDAC Binary Restrictions** | High | Unsigned C-extensions or compiled binaries (e.g. DuckDB, PyArrow) blocked by OS security policy. | Maintain 100% pure-Python algorithm design; use standard library `math`, `sqlite3`, and approved `libsql` bindings. |
| 2 | **Large-Scale Relational Query Latency** | Medium | Scanning 1.95M unit transactions on exploratory queries degrades user response times. | Route exploratory queries through pre-aggregated `project_summaries` table; ensure composite indexes on `(project_id, asset_class)`. |
| 3 | **Concurrent Lazy Model Training Contention** | Medium | Multiple incoming agent requests could trigger redundant GBDT/Cox model training scans. | Guard training blocks with Double-Checked Locking under `_model_lock` (`threading.Lock`) in `server.py`. |
| 4 | **FTS5 Virtual Table Cold Start** | Low | `document_fts` currently contains 0 rows in production database. | Provide a decoupled batch background worker (`DocumentWorker`) that parses PDFs into text and populates FTS5 asynchronously without blocking queries. |
| 5 | **LLM Hallucination in Legal Forensics** | Critical | Agent invent non-existent regulatory penalties or corrupt financial figures. | Enforce `EvidentiaryClaimCitation` JSON Schema validator; reject any agent response lacking a verified primary key and statutory clause source. |

---

### 6.3 Conclusion & Sign-Off

The GujRERA Sovereign Real Estate Intelligence Platform possesses an extraordinary institutional-grade foundation: 17,787 registered projects, 1.95 million certified unit transactions, 46.9k Building Use records, and 17.7k statutory escrow bank accounts. Its sovereign, zero-dependency analytical algorithms (custom GBDT with exact Tree SHAP and Cox Proportional Hazards with Breslow baseline hazards) deliver unmatched mathematical rigor without third-party ML runtime bloat.

By executing this architectural roadmap:
1. The 3-tool copilot gap will be immediately reconciled.
2. Standard Model Context Protocol transports (`stdio` and `SSE`) will bridge the platform to external AI agents.
3. Nine new research tools will unlock exploratory searching, deed-level transaction querying, broker claim fact-checking, and promoter portfolio tracing.
4. A multi-agent ecosystem backed by strict zero-hallucination citation contracts will provide sovereign, automated real estate diligence for Gujarat.

**Architecture Sign-Off**:
- Technical Lead / Implementer: Teamwork Worker M1
- Scope Certified: Comprehensive Technical Audit (R1), Capability & Gap Analysis (R2), Deep Data Analytics Plan (R3), Multi-Agent Serving Architecture (R4)
- Verification Command: `pytest real_estate_intelligence/tests` (64/64 Passing)
