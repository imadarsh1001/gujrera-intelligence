# GujRERA Sovereign Real Estate Intelligence Platform
### Advanced Quantitative Analytics, Interpretable ML, Survival Modeling & Agentic Diligence Workstation

An institutional-grade due-diligence and analytics platform for real estate in Gujarat, powered by official Gujarat Real Estate Regulatory Authority (GujRERA) statutory filings, certified professional disclosures, and municipal approvals.

[![Architecture: Sovereign Local-First](https://img.shields.io/badge/Architecture-Sovereign%20Local--First-blue.svg)](SHOWCASE.md#two-tier-architecture)
[![Evaluation Benchmark: PASS](https://img.shields.io/badge/Eval%20Harness-100%25%20PASS-brightgreen.svg)](SHOWCASE.md#automated-evaluation-harness)
[![Database: SQLite WAL](https://img.shields.io/badge/Database-SQLite%20WAL-orange.svg)](SHOWCASE.md#append-only-relational-fact-storage)
[![Evidentiary Contract: Zero Hallucination](https://img.shields.io/badge/Agentic%20MCP-Evidentiary%20Contract-purple.svg)](SHOWCASE.md#agentic-ai--model-context-protocol-mcp)
[![Dual-Repo: Public Intelligence + Private Pipeline](https://img.shields.io/badge/Repository-Dual--Repo%20Decoupled-success.svg)](#dual-repository-architecture--sync-workflow)

---

## Dual-Repository Architecture & Sync Workflow

To guarantee institutional privacy while maintaining open-source transparency, the platform operates across two separate repositories connected by a typed architectural data seam:

| Repository | Scope & Access | Key Responsibilities |
|---|---|---|
| **`gujrera-intelligence`** | **Public** | Quantitative ML (Hedonic GBDT + TreeSHAP), Cox survival delivery forecasting (reference projects), 15-table relational SQLite fact base, Vis.js knowledge graph (working), FastAPI web dashboard with Chart.js analytics, Diligence Copilot, and 13-tool Model Context Protocol (MCP) server. |
| **`gujrera-pipeline`** | **Private (Sibling)** | High-throughput Scrapy crawler, Parquet lake partitioner, immutable SHA-256 run archives, dynamic Form ID discovery, and RunReader seam (ADR-0004). Lives in sibling repository `../gujrera_pipeline`. |

### Architectural Boundary (`RunReader` Seam)
The public intelligence tier never invokes raw scrapers directly. Instead, it reads through the self-contained `RunReader` protocol boundary (`real_estate_intelligence/db/reader.py` / ADR-0001). This guarantees that the public intelligence application runs 100% standalone without requiring the private pipeline or network access.

### Repository Workflow & Contributing
Each repository is completely sovereign and follows standard Git workflows. To commit and push changes:
```bash
git add <files>
git commit -m "feat/fix: descriptive message"
git push origin <branch>
```

---

## Repository Structure

```
gujRERA/ (Public Analysis & Intelligence Platform)
├── real_estate_intelligence/ # [ACTIVE] Consumer Tier: Relational SQLite DB, FTS, graph, analytics & UI
│   ├── analytics/            # Discrepancy audits, pricing benchmarks, survival model, hedonic ML, dossiers
│   ├── db/                   # Database connection, 15-table schema, FTS5 engine, RunReader loader
│   ├── documents/            # PDF classification, text extraction, FTS search
│   ├── graph/                # Cross-project professional & promoter network knowledge graph
│   ├── mcp/                  # Model Context Protocol (MCP) server for AI research agents
│   ├── ui/                   # Single static UI directory (FastAPI backend in api/index.py)
│   ├── cli.py                # Unified CLI interface
│   ├── scripts/              # Operational utilities & empirical geocoding benchmarks
│   └── tests/                # Platform test suite (64 passing tests) & evaluation harness
│
├── api/                      # Consolidated FastAPI ASGI application (index.py)
├── docs/                     # Architectural Decision Records (ADRs) & technical specs
│   ├── adr/                  # 0001-run-reader..., 0002-columnar-parquet..., 0003-fastapi-consolidation..., 0004-analyst-workbench...
│   └── SPEC.md               # End-to-end platform specification & 52 user stories
│
├── GLOSSARY.md               # Canonical domain vocabulary & regulatory definitions
├── SHOWCASE.md               # Comprehensive institutional showcase & technical report
├── EGM.md                    # Explicit Architecture Blueprint & Subdirectory Contracts
└── run_server.py             # FastAPI dashboard server launcher via uvicorn (127.0.0.1:8765)

../gujrera_pipeline/ (Sibling Private Ingestion Engine)
├── crawler/                  # Production Scrapy crawler (gujrera_spider.py) & Parquet partitioner
├── core/                     # Core RunStore (manifest.sqlite), models, catalog, and core.reader
├── legacy_collector/         # Isolated curl-based collector tools
├── scripts/                  # Unified inspect_filings.py CLI and archive tools
├── staging_from_intelligence/# Consolidated historical crawlers, EDA prototypes, raw CSVs & docs
└── tests/                    # Pipeline verification test suite
```

---

## Code Contracts & Review Audit Trail

Every code directory carries an `EGM.md` contract — a per-directory statement of its public interface, invariants, and side effects, generated from source and verified in a six-round audit (96 findings raised, 94 fixes applied, 2026-11-09). Start at the root [`EGM.md`](EGM.md) (workspace blueprint) or [`real_estate_intelligence/EGM.md`](real_estate_intelligence/EGM.md) (public-repo subtree root). The audit trail for the review is kept locally and not distributed in the repository. Contracts for the private `gujrera_pipeline` repository live in that repository; the gitignored `legacy/` archive's contracts are local-only.

---

## Core Capabilities

### 1. Forensic Capital & Escrow Auditing
* **Statutory Section 4(2)(l)(D) Over-Withdrawal Audit**: Automatically audits whether cumulative withdrawals from the designated 70% retention account exceed certified allowable spend based on physical progress:
  $$\text{Allowable Spend Limit} = \text{Estimated Total Cost} \times \left( \frac{\text{Physical Progress \%}}{100} \right)$$
* **Escrow Burn Rate & Cash Runway Equation**: Calculates monthly construction burn velocity and remaining months of solvency in the 70% Retention Escrow Account.
* **Construction Finance & Encumbrance Risk Audit**: Audits Sub-Registrar encumbrance certificates and Form B declarations against active institutional bank borrowings/charges (`loan_rows_count`).

### 2. Quantitative Data Science & Machine Learning
* **Interpretable Hedonic Pricing Engine (GBDT + Exact TreeSHAP)**: Predicts unit valuation rates (INR/sq.ft) across asset classes (`Residential`, `Commercial_Office`, `Commercial_Retail`, `Industrial_Warehouse`) with exact Shapley value decomposition:
  $$\mathbb{E}[Y] + \sum_{j=1}^K \phi_j(x) \equiv \hat{y}(x) \quad (\text{Additive Efficiency Guaranteed})$$
* **Completion Delay Survival Model (Cox Proportional Hazards)**: Estimates handover delivery probabilities $S(t) = P(\text{Complete} > t)$ and forecasts delay percentiles ($p_{50}$ median, $p_{75}$ conservative, $p_{90}$ high-confidence delivery dates; trained on reference projects only).
* **Longitudinal Price Realization Trajectory & Annualized CAGR**: Tracks chronological quarterly median rates and computes compound annual growth rates across multi-year registered sale agreements.
* **Geospatial (GIS) Micro-Market Clustering**: Computes Great-Circle Haversine distance, Town Planning (TP) scheme clusters, and localized competitive density.

### 3. Interactive Web Dashboard & AI Diligence Copilot
Launch with `python run_server.py` (single FastAPI ASGI server via uvicorn, served on port `8765`):
* **Executive 4-Quadrant Dossier**: Financial health, construction velocity, land identity, and legal compliance.
* **Unit Pricing Distribution**: Percentile pricing cards, block-by-block variance, and recent registered transactions.
* **Quantitative ML & Curves (Chart.js 4.4 UMD)**:
  - Completion Survival Hazard Curve with $p_{50}, p_{75}, p_{90}$, and registered RERA completion dates.
  - Hedonic Pricing SHAP Waterfall with interactive asset class and square footage filters.
  - Longitudinal Price Realization Trajectory with total appreciation % and CAGR badges.
* **Interactive Knowledge Graph (Vis.js)**: Working cross-project entity graph exploring shared professionals and contagion risk leads across 21,836 nodes and 51,069 edges (connecting 1,612 shared cross-project professionals).
* **Dual-Mode AI Diligence Copilot**:
  - **⚡ Agentic LLM Mode (Gemini 2.0 Flash / OpenAI)**: Open-ended multi-turn reasoning executing automated tool calls across 10 MCP forensic tools to retrieve factual ground truth and synthesize comprehensive buyer guidance.
  - **🛡️ Local Evidentiary Mode (Deterministic Fallback)**: Operates 100% offline with zero external API credentials, powered by local SQLite FTS5 BM25 search (available for reference projects with ingested statutory PDFs, pending PDF pipeline for statewide records), GBDT SHAP, and Cox survival models with zero hallucination.

### 4. Agentic AI & Model Context Protocol (MCP)
The platform exposes 13 read-only research tools via `RealEstateIntelligenceMCP`:
* `get_project_dossier`, `query_inventory_breakdown`, `predict_pricing_benchmark`, `forecast_completion_delay`, `calculate_escrow_runway`, `get_spatial_density`, `get_escrow_health`, `get_land_records`, `get_regulatory_radar`, `audit_discrepancies`, `search_document_evidence`, `trace_entity_network`, `compare_projects`.
* Bound by an **Evidentiary Citation Contract** requiring every factual claim to link to an immutable run ID, form ID, or PDF page SHA-256 hash.

### 5. Automated Evaluation Harness
Run via `python -m real_estate_intelligence.cli eval`:
* **Hedonic Pricing ML**: 5-fold cross-validation RMSE < Rs. 2,500/sqft, 100% SHAP additive efficiency.
* **Completion Delay Survival Analysis**: Harrell's Concordance Index ($C$-index) = 1.000 on the 9-project reference fixture (Target $\ge 0.75$; trained on reference projects only, not the 17,787-project statewide crawl).
* **Statutory Document Retrieval**: MRR@5 = 1.000, Recall@5 = 1.000 across BM25 queries on the 9-project reference document fixture (statewide PDF ingestion pending pipeline).
* **Agent Factuality & Evidentiary Rubric**: 100% ground-truth fidelity, 0 hallucinations.

---

## Quickstart & Commands

### 1. Installation & Environment Setup (Managed with `uv`)

This platform uses [uv](https://github.com/astral-sh/uv) as its sovereign, blazingly fast Python package and virtual environment manager.

```bash
# Clone the repository and navigate to root
git clone https://github.com/imadarsh1001/gujrera-intelligence.git
cd gujrera-intelligence

# 1. Create a sovereign virtual environment
uv venv

# 2. Activate the virtual environment
# Windows PowerShell / CMD:
.venv\Scripts\activate
# Linux / macOS:
source .venv/bin/activate

# 3. Install core dependencies in editable mode
uv pip install -r requirements.txt

# (Optional) For development & testing dependencies:
uv pip install -r requirements-dev.txt
```

#### Package Maintenance Workflows with `uv`:
* **Zero-Activation Direct Run**: Execute any CLI command or server directly through `uv` without manually activating the virtualenv:
  ```bash
  uv run python run_server.py
  uv run python -m real_estate_intelligence.cli eval
  ```
* **Add a New Dependency**:
  ```bash
  uv add <package-name>
  # Or via pip interface:
  uv pip install <package-name>
  ```
* **Upgrade Dependencies**:
  ```bash
  uv pip install --upgrade -r requirements.txt
  ```
* **Inspect Dependency Tree**:
  ```bash
  uv pip tree
  ```

### 2. Running Tests & Benchmarks

```bash
# Run complete platform unit & integration test suite (64 passing tests)
uv run pytest real_estate_intelligence/tests

# Run the 4-pillar AI/ML & Agent Evaluation Benchmark Harness (reference project fixtures)
uv run python -m real_estate_intelligence.cli eval
```

### 3. Data Regeneration
The ~235 MB curated statewide SQLite database (`intelligence.sqlite`) is intentionally excluded from Git. To regenerate it locally from the sibling Parquet data lake, execute:
```bash
python -c "from real_estate_intelligence.db.statewide_loader import ingest_statewide; ingest_statewide()"
```
Rebuild performance is benchmarked at 4.18 minutes with 100% exact row-count and entity fidelity (see [`docs/LEARNINGS.md`](docs/LEARNINGS.md) §5.1).

### 4. CLI Operations

```bash
cd real_estate_intelligence

# 1. Start interactive FastAPI web dashboard via uvicorn (Port 8765)
python run_server.py
# (Or via CLI: python -m real_estate_intelligence.cli serve --port 8765)

# 2. Run full statutory due-diligence dossier
python -m real_estate_intelligence.cli dossier --project-id 13560

# 3. Predict unit pricing with SHAP feature attributions
python -m real_estate_intelligence.cli ml-price --project-id 13560 --asset-class Commercial_Retail --carpet-area 850

# 4. Forecast project handover dates and completion delay percentiles
python -m real_estate_intelligence.cli survival --project-id 17830

# 5. Audit escrow cash burn rate and monthly liquidity runway
python -m real_estate_intelligence.cli runway --project-id 13560

# 6. Analyze micro-market spatial density and nearby competition
python -m real_estate_intelligence.cli spatial --project-id 13560 --radius 5.0

# 7. Run automated discrepancy audit (cost reversals, velocity lag, over-withdrawals)
python -m real_estate_intelligence.cli audit --project-id 17830

# 8. Check registered unit pricing benchmarks & longitudinal trajectory
python -m real_estate_intelligence.cli pricing --project-id 13705

# 9. Search certified documents with BM25 ranking (reference projects with ingested PDFs)
python -m real_estate_intelligence.cli search --query "encumbrance"
```

### 5. Interactive Web Dashboard & AI Diligence Copilot

Start the single FastAPI server via uvicorn:
```bash
python run_server.py
# Or: python -m real_estate_intelligence.cli serve --port 8765
```
Open [http://localhost:8765](http://localhost:8765) in your browser.
* **Explore Projects** (landing tab): searchable, filterable, sortable project table over the registered projects — district boundaries on an interactive map (click a district to zoom and filter), filing-freshness and completion-revision statuses with evidence links, and a shortlist with a side-by-side **Compare** view (saved in your browser).
* Optional interactive basemap: set `MAPTILER_API_KEY` in the workspace `.env` (gitignored). The key stays server-side — the dashboard proxies map tiles through this server — and without it an offline sketch map is used.
* Select projects from the header dropdown (e.g. `16562 — THE BALCONY`, `13705 — THE GATE BY DEV AASHISH`) for the full per-project dossier.
* Explore the **Quantitative ML & Curves** tab for TreeSHAP decompositions and Cox survival delay forecasting.
* Inspect the **Cross-Project Knowledge Graph** (Working): visualize contagion and shared professional links rendered via Vis.js over SQLite `graph_nodes` and `graph_edges`.
* Launch the **Diligence Copilot**: click the floating bot launcher or press the gear icon (`⚙️`) to input an optional Gemini or OpenAI API key for deep multi-turn tool-calling, or use the 100% offline local evidentiary engine with zero hallucination.

---

## Documentation & Engineering Learnings

- **Full Project Specification**: [`docs/SPEC.md`](file:///d:/Code%20Projects/Miscellaneous/Real%20Estate%20Data/gujRERA/docs/SPEC.md)
- **Engineering Learnings & Post-Mortem**: [`docs/LEARNINGS.md`](file:///d:/Code%20Projects/Miscellaneous/Real%20Estate%20Data/gujRERA/docs/LEARNINGS.md) (Git HTTP/1.1 chunked protocol, sub-25MB data lake partitioning, DuckDB zero-copy querying, and 10.79 GB verified disk reclamation)
- **ADR 0001**: [`docs/adr/0001-run-reader-decoupling.md`](file:///d:/Code%20Projects/Miscellaneous/Real%20Estate%20Data/gujRERA/docs/adr/0001-run-reader-decoupling.md) (RunReader Decoupling)
- **ADR 0002**: [`docs/adr/0002-columnar-parquet-data-lake-and-document-manifest.md`](file:///d:/Code%20Projects/Miscellaneous/Real%20Estate%20Data/gujRERA/docs/adr/0002-columnar-parquet-data-lake-and-document-manifest.md) (Columnar Parquet Data Lake & Evidentiary Manifest)
- **ADR 0003**: [`docs/adr/0003-fastapi-consolidation.md`](file:///d:/Code%20Projects/Miscellaneous/Real%20Estate%20Data/gujRERA/docs/adr/0003-fastapi-consolidation.md) (FastAPI Server Consolidation)
- **ADR 0004**: [`docs/adr/0004-analyst-workbench-astryx-and-agent-runtime.md`](file:///d:/Code%20Projects/Miscellaneous/Real%20Estate%20Data/gujRERA/docs/adr/0004-analyst-workbench-astryx-and-agent-runtime.md) (Analyst Workbench & Agent Runtime Architecture)
- **ADR 0005**: [`docs/adr/0005-hybrid-coordinator-specialist-graph.md`](file:///d:/Code%20Projects/Miscellaneous/Real%20Estate%20Data/gujRERA/docs/adr/0005-hybrid-coordinator-specialist-graph.md) (Hybrid Map-Reduce Coordinator, Specialist Subgraphs & A2UI 1.0)
- **Private Pipeline Architecture**: [`gujrera_pipeline/README.md`](file:///d:/Code%20Projects/Miscellaneous/Real%20Estate%20Data/gujRERA/gujrera_pipeline/README.md)
