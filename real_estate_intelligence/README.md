# Real Estate Intelligence Platform (GujRERA)

An institutional-grade, evidence-backed real estate intelligence terminal and data science platform for **analytical buyers, institutional lenders, private equity analysts, and legal due-diligence advisors**.

Rather than acting as another broker lead-generation portal with unverified marketing claims, this platform serves as an **independent forensic workstation** anchored in official, sworn GujRERA filings, audited financial certificates, signed architect reports, registered sale deeds, and municipal approvals.

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        Real Estate Intelligence Architecture                           │
└────────────────────────────────────────────────────────────────────────────────────────┘

  [Raw GujRERA Archive / RunReader Seam] (406 JSON Responses, 789 Docs, 1.56 GB)
                                    │
                                    ▼
 ┌──────────────────────────────────────────────────────────────────────────────────────┐
 │                      Ingestion & Fact Curation Engine                                │
 ├──────────────────────────────┬───────────────────────────────┬───────────────────────┤
 │     Relational Facts         │       Knowledge Graph         │      FTS5 RAG         │
 │ (Projects, Blocks, Finances, │ (Promoters, Architects,       │ (Page text of 2,006   │
 │  Professionals, Banks)       │  Engineers, CAs, Sister Proj) │  extracted PDF pages) │
 └──────────────┬───────────────┴───────────────┬───────────────┴───────┬───────────────┘
                │                               │                       │
                ▼                               ▼                       ▼
 ┌──────────────────────────────────────────────────────────────────────────────────────┐
 │                   Quantitative Data Science & Forensic Analytics                     │
 ├──────────────────────────────────────────────────────────────────────────────────────┤
 │  • Hedonic Pricing Engine (GBDT + Exact TreeSHAP additive feature attributions)      │
 │  • Completion Delay Survival Model (Cox Proportional Hazards + Breslow estimator)    │
 │  • Section 4(2)(l)(D) Escrow Over-Withdrawal Audit (allowable physical spend cap)   │
 │  • Escrow Cash Burn Rate & Monthly Runway Equation (insolvency early warning)        │
 │  • Longitudinal Price Trajectory & Quarterly CAGR (chronological registered deeds)   │
 │  • Construction Finance & Encumbrance Risk Audit (active land charges/mortgages)     │
 │  • Cross-Project Professional Contagion Tracing (multi-hop graph risk propagation)   │
 │  • Spatial Micro-Market & Haversine Density Analysis (GIS TP Scheme clusters)        │
 └──────────────────────────────────────┬───────────────────────────────────────────────┘
                                        │
                 ┌──────────────────────┴──────────────────────┐
                 ▼                                             ▼
 ┌──────────────────────────────┐              ┌──────────────────────────────┐
 │ Terminal Web Dashboard & UI  │              │ Model Context Protocol (MCP) │
 │  • Executive 4-Quadrant Card │              │ (13 Tools for AI Agents with │
 │  • Chart.js ML Visual Curves │              │  strict Evidentiary Citation │
 │  • Vis.js Knowledge Graph    │              │  Contract & zero hallucina-  │
 │  • Live Diligence Copilot    │              │  tion guarantee)             │
 └──────────────────────────────┘              └──────────────────────────────┘
```

---

## Core Capabilities

### 1. Forensic Escrow & Financial Auditing
* **Section 4(2)(l)(D) Proviso 1 Over-Withdrawal Detector**: Verifies whether withdrawals from the 70% retention escrow account exceed certified allowable spend based on civil engineering progress:
  $$\text{Allowable Spend Limit} = \text{Estimated Total Cost} \times \left( \frac{\text{Physical Progress \%}}{100} \right)$$
* **Escrow Cash Runway**: Computes monthly construction spend velocity and models remaining months of solvency:
  $$\text{Escrow Runway (Months)} = \frac{\text{Closing Balance in 70\% Escrow Account}}{\text{Monthly Burn Rate}}$$
* **Encumbrance & Mortgage Verification**: Checks Sub-Registrar encumbrance certificates and Form B declarations against active institutional bank borrowings/charges (`loan_rows_count`).

### 2. Interpretable Hedonic Pricing (GBDT + Exact TreeSHAP)
* Models unit transaction prices ($\text{INR/sq.ft}$) using gradient boosted trees across segmented asset classes (`Residential`, `Commercial_Office`, `Commercial_Retail`, `Industrial_Warehouse`).
* Computes exact Shapley feature contributions $\phi_j(x)$ for location coordinates, layout scale, physical completion, and promoter scale, mathematically verifying the Additive Efficiency Property:
  $$\mathbb{E}[Y] + \sum_{j=1}^K \phi_j(x) \equiv \hat{y}(x)$$

### 3. Completion Delay Survival Analysis (Cox Proportional Hazards)
* Treats handover delivery as a time-to-event survival problem with right-censoring.
* Estimates hazard ratios $h(t \mid X) = h_0(t) \exp(\beta^T X)$ and forecasts delivery percentiles:
  - $p_{50}$ (Median expected handover date)
  - $p_{75}$ (Conservative handover estimate)
  - $p_{90}$ (High-confidence delivery horizon)

### 4. Longitudinal Price Trajectory & Quarterly CAGR
* Tracks registered unit agreement consideration over calendar quarters (2021 to 2026).
* Computes quarterly median rates, total price appreciation %, and annualized CAGR:
  $$\text{CAGR} = \left[ \left( \frac{\text{Latest Median Rate}}{\text{First Median Rate}} \right)^{\frac{1}{\Delta \text{Years}}} - 1 \right] \times 100$$

### 5. Interactive Terminal Web Dashboard & AI Diligence Copilot
Run locally via `python -m real_estate_intelligence.cli serve --port 8765` (or `python run_server.py` from root):
* **Executive 4-Quadrant Tab**: Financial inflows, construction velocity, land identity, and legal compliance.
* **Unit Pricing Tab**: 25th/median/75th percentiles, block-by-block variance, and recent registered transactions.
* **Quantitative ML & Curves Tab (Chart.js 4.4 UMD)**:
  - Survival Delay Hazard Curve $S(t) = P(\text{Complete} > t)$ with milestone markers.
  - Hedonic Pricing SHAP Waterfall with interactive asset class and carpet area selectors.
  - Longitudinal Price Realization Trajectory with total appreciation % and CAGR badges.
* **Knowledge Graph Tab (Vis.js)**: Interactive node-edge visualization of promoters, consultants, and banks.
* **Dual-Mode Diligence Copilot**:
  - **⚡ Agentic LLM Mode**: Deep reasoning using Gemini 2.0 Flash or OpenAI with automated tool calls across 10 MCP forensic tools. Configurable via the Copilot Settings (`⚙️`) drawer.
  - **🛡️ Local Evidentiary Mode**: 100% offline, zero-credential deterministic RAG using SQLite FTS5 BM25 search, GBDT TreeSHAP, and Cox survival modeling with guaranteed **0% hallucination**.

### 6. Model Context Protocol (MCP) Server
Exposes 13 research tools via `real_estate_intelligence.mcp.server.RealEstateIntelligenceMCP`:
* `get_project_dossier`, `query_inventory_breakdown`, `predict_pricing_benchmark`, `forecast_completion_delay`, `calculate_escrow_runway`, `get_spatial_density`, `get_escrow_health`, `get_land_records`, `get_regulatory_radar`, `audit_discrepancies`, `search_document_evidence`, `trace_entity_network`, `compare_projects`.

---

## Installation & Package Management with `uv`

The platform uses [uv](https://github.com/astral-sh/uv) for sovereign, lightning-fast virtual environment and dependency management:

```bash
# 1. Create a virtual environment
uv venv

# 2. Activate the virtual environment
# Windows:
.venv\Scripts\activate
# Linux / macOS:
source .venv/bin/activate

# 3. Install in editable mode
uv pip install -e .

# (Optional) Install development dependencies (pytest):
uv pip install -e ".[dev]"
```

Once installed in editable mode, the CLI is available both as a python module (`python -m real_estate_intelligence.cli`) and as an entrypoint executable:
```bash
uv run real-estate-intelligence --help
```

---

## Quickstart & CLI Commands

### 1. Start Web Terminal & Diligence Copilot

```bash
python -m real_estate_intelligence.cli serve --port 8765
```
Open `http://localhost:8765` in your browser.

### 2. Run Forensic Diligence & Analytics via CLI

```bash
# 1. Generate full 4-quadrant executive investor dossier
python -m real_estate_intelligence.cli dossier --project-id 13560

# 2. Predict unit pricing with SHAP feature attributions
python -m real_estate_intelligence.cli ml-price --project-id 13560 --asset-class Commercial_Retail --carpet-area 850

# 3. Forecast project handover dates and completion delay percentiles
python -m real_estate_intelligence.cli survival --project-id 17830

# 4. Audit escrow cash burn rate and monthly liquidity runway
python -m real_estate_intelligence.cli runway --project-id 13560

# 5. Analyze micro-market spatial density and nearby competition
python -m real_estate_intelligence.cli spatial --project-id 13560 --radius 5.0

# 6. Run automated discrepancy audit (cost reversals, over-withdrawals, velocity lag)
python -m real_estate_intelligence.cli audit --project-id 17830

# 7. Check registered unit pricing benchmarks & longitudinal trajectory
python -m real_estate_intelligence.cli pricing --project-id 13705

# 8. Search certified documents with BM25 ranking
python -m real_estate_intelligence.cli search --query "encumbrance"
```

### 3. Run Automated Tests & Evaluation Benchmark Harness

```bash
# Run all 32 unit tests
python -c "import sys, unittest; sys.path.insert(0, '.'); sys.path.insert(0, 'real_estate_intelligence'); unittest.main(module=None, argv=['unittest', 'discover', '-s', 'real_estate_intelligence/tests'])"

# Run the 4-pillar AI/ML & Agent Evaluation Benchmark Harness
python -m real_estate_intelligence.cli eval
```
