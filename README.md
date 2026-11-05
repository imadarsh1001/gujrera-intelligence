# GujRERA Sovereign Real Estate Intelligence Platform
### Advanced Quantitative Analytics, Interpretable ML, Survival Modeling & Agentic Diligence Workstation

An institutional-grade due-diligence and analytics platform for real estate in Gujarat, powered by official Gujarat Real Estate Regulatory Authority (GujRERA) statutory filings, certified professional disclosures, and municipal approvals.

[![Architecture: Sovereign Local-First](https://img.shields.io/badge/Architecture-Sovereign%20Local--First-blue.svg)](SHOWCASE.md#two-tier-architecture)
[![Evaluation Benchmark: PASS](https://img.shields.io/badge/Eval%20Harness-100%25%20PASS-brightgreen.svg)](SHOWCASE.md#automated-evaluation-harness)
[![Database: SQLite WAL](https://img.shields.io/badge/Database-SQLite%20WAL-orange.svg)](SHOWCASE.md#append-only-relational-fact-storage)
[![Evidentiary Contract: Zero Hallucination](https://img.shields.io/badge/Agentic%20MCP-Evidentiary%20Contract-purple.svg)](SHOWCASE.md#agentic-ai--model-context-protocol-mcp)

---

## Repository Structure

```
gujRERA/
├── gujrera_pipeline/         # [ACTIVE] Producer Tier: Ingestion pipeline, curl transport, manifests & RunReader
│   ├── client.py             # Authenticated transport & rate-limiter
│   ├── collector.py          # Atomic, resumable endpoint harvester
│   ├── documents.py          # PDF document downloader & SHA-256 deduplicator
│   ├── reader.py             # RunReader & ProjectSnapshot abstraction (ADR-0001)
│   ├── catalog.py            # Complete GujRERA API endpoint schema catalog
│   ├── data/runs/            # Curated local runs (including nine_projects_2026_10_15)
│   └── tests/                # Automated pipeline test suite
│
├── real_estate_intelligence/ # [ACTIVE] Consumer Tier: Relational SQLite DB, FTS, graph, analytics & UI
│   ├── analytics/            # Discrepancy audits, pricing benchmarks, survival model, hedonic ML, dossiers
│   ├── db/                   # Database connection, 14-table schema, FTS5 engine, RunReader loader
│   ├── documents/            # PDF classification, text extraction, FTS search
│   ├── graph/                # Cross-project professional & promoter network knowledge graph
│   ├── mcp/                  # Model Context Protocol (MCP) server for AI research agents
│   ├── ui/                   # Web dashboard with Chart.js analytics & AI Diligence Copilot
│   ├── cli.py                # Unified CLI interface
│   └── tests/                # Platform test suite & automated evaluation benchmark harness
│
├── docs/                     # Architectural Decision Records (ADRs) & technical specs
│   ├── adr/
│   │   └── 0001-run-reader-ingestion-seam.md
│   └── SPEC.md               # End-to-end platform specification & 52 user stories
│
├── GLOSSARY.md               # Canonical domain vocabulary & regulatory definitions
├── SHOWCASE.md               # Comprehensive institutional showcase & technical report
│
├── collected_data/           # Master statewide index (17,634 projects) & reference datasets
└── legacy/                   # Archived historical systems & prototypes (Read-Only)
```

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
* **Completion Delay Survival Model (Cox Proportional Hazards)**: Estimates handover delivery probabilities $S(t) = P(\text{Complete} > t)$ and forecasts delay percentiles ($p_{50}$ median, $p_{75}$ conservative, $p_{90}$ high-confidence delivery dates).
* **Longitudinal Price Realization Trajectory & Annualized CAGR**: Tracks chronological quarterly median rates and computes compound annual growth rates across multi-year registered sale agreements.
* **Geospatial (GIS) Micro-Market Clustering**: Computes Great-Circle Haversine distance, Town Planning (TP) scheme clusters, and localized competitive density.

### 3. Interactive Web Dashboard & AI Diligence Copilot
Launch with `python run_server.py` (served on port `8765`):
* **Executive 4-Quadrant Dossier**: Financial health, construction velocity, land identity, and legal compliance.
* **Unit Pricing Distribution**: Percentile pricing cards, block-by-block variance, and recent registered transactions.
* **Quantitative ML & Curves (Chart.js 4.4 UMD)**:
  - Completion Survival Hazard Curve with $p_{50}, p_{75}, p_{90}$, and registered RERA completion dates.
  - Hedonic Pricing SHAP Waterfall with interactive asset class and square footage filters.
  - Longitudinal Price Realization Trajectory with total appreciation % and CAGR badges.
* **Interactive Knowledge Graph (Vis.js)**: Explores cross-project shared professionals and contagion risk leads.
* **Dual-Mode AI Diligence Copilot**:
  - **⚡ Agentic LLM Mode (Gemini 2.0 Flash / OpenAI)**: Open-ended multi-turn reasoning executing automated tool calls across 10 MCP forensic tools to retrieve factual ground truth and synthesize comprehensive buyer guidance.
  - **🛡️ Local Evidentiary Mode (Deterministic Fallback)**: Operates 100% offline with zero external API credentials, powered by local SQLite FTS5 BM25 search, GBDT SHAP, and Cox survival models with zero hallucination.

### 4. Agentic AI & Model Context Protocol (MCP)
The platform exposes 13 read-only research tools via `RealEstateIntelligenceMCP`:
* `get_project_dossier`, `query_inventory_breakdown`, `predict_pricing_benchmark`, `forecast_completion_delay`, `calculate_escrow_runway`, `get_spatial_density`, `get_escrow_health`, `get_land_records`, `get_regulatory_radar`, `audit_discrepancies`, `search_document_evidence`, `trace_entity_network`, `compare_projects`.
* Bound by an **Evidentiary Citation Contract** requiring every factual claim to link to an immutable run ID, form ID, or PDF page SHA-256 hash.

### 5. Automated Evaluation Harness
Run via `python -m real_estate_intelligence.cli eval`:
* **Hedonic Pricing ML**: 5-fold cross-validation RMSE < Rs. 2,500/sqft, 100% SHAP additive efficiency.
* **Completion Delay Survival Analysis**: Harrell's Concordance Index ($C$-index) = 1.000 (Target $\ge 0.75$).
* **Statutory Document Retrieval**: MRR@5 = 1.000, Recall@5 = 1.000 across BM25 queries.
* **Agent Factuality & Evidentiary Rubric**: 100% ground-truth fidelity, 0 hallucinations.

---

## Quickstart & Commands

### 1. Installation

```bash
# Clone the repository and navigate to root
cd "gujRERA"

# Install dependencies with uv (or standard pip)
uv pip install pypdf
```

### 2. Running Tests

```bash
# Run complete platform unit test suite (25 tests)
python -c "import sys, unittest; sys.path.insert(0, '.'); sys.path.insert(0, 'real_estate_intelligence'); unittest.main(module=None, argv=['unittest', 'discover', '-s', 'real_estate_intelligence/tests'])"

# Run the 4-pillar AI/ML & Agent Evaluation Benchmark Harness
python -m real_estate_intelligence.cli eval
```

### 3. CLI Operations

```bash
cd real_estate_intelligence

# 1. Start interactive terminal web dashboard with Chart.js analytics & AI Copilot
python run_server.py
# (Or with custom port: python run_server.py serve --port 8765)

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

# 9. Search certified documents with BM25 ranking
python -m real_estate_intelligence.cli search --query "encumbrance"
```

### 4. Interactive Web Dashboard

Start the server:
```bash
python -m real_estate_intelligence.cli serve --port 8000
```
Open [http://localhost:8000](http://localhost:8000) in your browser.
Select projects from the header dropdown (e.g. `16562 — THE BALCONY`, `13705 — THE GATE BY DEV AASHISH`), explore the **Quantitative ML & Curves** tab, inspect the **Cross-Project Knowledge Graph**, and chat with the **Diligence Copilot**.
