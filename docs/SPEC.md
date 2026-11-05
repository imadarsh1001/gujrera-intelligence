# Project Specification: Gujarat Real Estate Regulatory Authority (GujRERA) Intelligence & Agentic Analytics Platform

## Problem Statement

Institutional real estate investors, homebuyers, lenders, and compliance officers face extreme information asymmetry when evaluating registered real estate developments in Gujarat. While the statutory Gujarat Real Estate Regulatory Authority (GujRERA) portal hosts mandatory disclosures, the underlying data is fragmented across obscure API endpoints, rate-limited query structures, and thousands of unstructured PDF certificates.

Consequently, critical investment, legal, and operational risks remain undetected:
- **Artificial Pricing & Marketing Hype**: Buyers lack empirical benchmarks to evaluate broker quotes against true registered sales consideration certified by Chartered Accountants in Form 3 filings.
- **Hidden Project Delays & Insolvency**: Promoters make aggressive handover commitments contradicted by civil engineering progress (Form 1) and depleted statutory Retention Escrow Accounts.
- **Expenditure Reversals & Compliance Defaults**: Promoters report unexplained drops in cumulative project expenditure between filings, delay mandatory quarterly filings (QPRs), or fail to submit annual audit certificates (Form 5).
- **Systemic Contagion Across Projects**: Structural engineers, architects, and chartered accountants associated with stalled or defaulting projects quietly certify new developments without transparency.
- **Opaque Legal Encumbrances**: Title clearance reports, municipal Town Planning (TP) approvals, and Building Use (BU) permissions span thousands of pages of unstructured legal documents that cannot be queried systematically.
- **Asset-Class Conflation**: Commercial properties (high-value retail shops and offices) are often lumped together with residential units, obscuring true commercial yields and vertical floor-level pricing gradients.

## Solution

The GujRERA Intelligence & Agentic Analytics Platform provides an institutional-grade, local-first analytics and due-diligence system. Built on sworn statutory disclosures and designed with resilient micro-architecture boundaries, the platform operates across five cohesive layers:

1. **Tamper-Evident Ingestion Engine (`gujrera_pipeline`)**: Collects immutable observations of statutory disclosures across all registered projects into isolated runs. Features a pluggable `Transport` interface, SHA-256 cryptographic provenance manifests, and a decoupled `RunReader` read-side seam (ADR-0001) that serves structured `ProjectSnapshot` objects. Implements a two-phase ingestion strategy (statewide tabular ingestion in Phase 1, on-demand PDF extraction in Phase 2).
2. **Append-Only Relational & Feature Store (`real_estate_intelligence.db`)**: Ingests project snapshots into a run-versioned SQLite database with a canonical `v_current_projects` view, preserving historical temporal drift across quarterly observation periods across 14 normalized relational and virtual tables.
3. **Decoupled Document Processing Micro-Architecture (`DocumentWorker`)**: Operates an asynchronous background worker reading from an isolated `document_jobs` SQLite queue, ensuring heavy PDF downloading, OCR, and dense vector embeddings never block or degrade fast tabular ingestion or the web dashboard.
4. **Quantitative Data Science & Interpretable ML**:
   - **Hedonic Pricing Model**: Uses gradient boosting (LightGBM) with SHAP (SHapley Additive exPlanations) across segmented asset classes (`Residential`, `Commercial_Office`, `Commercial_Retail`), modeling vertical floor-level pricing gradients.
   - **Completion Delay Survival Model**: Implements Cox Proportional Hazards and time-to-event survival modeling to forecast the probability distribution of handover delays.
   - **Capital Burn-Rate & Escrow Runway Analyzer**: Models quarterly construction cash burn against 70% Retention Escrow Account liquidity to project cash runway in months.
   - **Geospatial (GIS) Micro-Market Clustering**: Applies spatial autocorrelation and clustering (DBSCAN) over GPS coordinates and Town Planning schemes.
5. **NLP, Forensic Graph & Agentic AI**:
   - **Hybrid RAG Engine**: Combines SQLite FTS5 (BM25 keyword search for legal survey numbers and advocate names) with local dense vector embeddings (`sentence-transformers`) using Reciprocal Rank Fusion (RRF).
   - **Statutory Remarks Parser**: Reconciles promoter explanatory notes using regex dictionaries to classify anomalies as "Explained" vs "Unreconciled".
   - **Knowledge Graph**: Resolves professional entities anchored on statutory Council of Architecture (CoA) and ICAI licensing numbers, modeling two-tier edges (`CERTIFIED_BY` vs `PROBABLE_SAME_AS`) and multi-hop contagion risk.
   - **Autonomous Diligence Agent**: Exposes Model Context Protocol (MCP) tools via `stdio` transport, bound by an **Evidentiary Citation Contract** where every factual claim links to an immutable run ID, form ID, or PDF page SHA-256.
   - **Automated Evaluation Harness**: Benchmarks ML accuracy, RAG retrieval precision, and Agent zero-hallucination compliance against verified ground-truth test suites.

## User Stories

1. As an institutional investor, I want to view the median, minimum, maximum, and 25th-to-75th percentile registered rate per square foot for a project, so that I can benchmark fair market valuation against CA-certified Form 3 transaction records rather than marketing brochures.
2. As an institutional investor, I want block-by-block pricing variance across individual towers, so that I can identify premium pricing trends and absorption discrepancies within a single registered project.
3. As an institutional investor, I want to evaluate a project's statutory Retention Escrow Account balance against total customer deposits, so that I can detect liquidity diversion or under-funded construction reserves before deploying capital.
4. As an institutional investor, I want to compare certified physical progress from Form 1 against elapsed calendar time, so that I can calculate the velocity ratio and flag construction delay risk early.
5. As an institutional investor, I want an executive 4-quadrant due-diligence dossier generated for any project, so that investment committees can review financial, physical, regulatory, and legal standing in a standardized format.
6. As a homebuyer, I want to enter a broker's claimed sales velocity and handover date into a claims checker, so that I can immediately detect artificial scarcity or unrealistic possession commitments contradicted by statutory filings.
7. As a homebuyer, I want to see the exact Town Planning (TP) scheme, Final Plot (FP) number, and Revenue Survey number for a project, so that I can confirm municipal site legitimacy and land title boundaries.
8. As a homebuyer, I want to verify whether Building Use (BU) permissions or architectural completion certificates (Form 4) have been granted for my specific block, so that I do not take possession of an uncertified structure.
9. As a forensic auditor, I want an automated discrepancy audit across historical filings, so that I am alerted if cumulative incurred expenditure reported in Form 3 inexplicably drops between filing periods.
10. As a forensic auditor, I want to see a project's Form 5 annual audit compliance history, so that I can identify promoters who fail to submit statutory annual utilization certificates under Section 4(2)(l)(D).
11. As a forensic auditor, I want to inspect default quarters and registered consumer complaints, so that I can quantify regulatory friction and promoter non-compliance.
12. As a risk analyst, I want a knowledge graph mapping promoters, projects, architects, structural engineers, and chartered accountants, so that I can uncover shared entity networks across the state.
13. As a risk analyst, I want multi-hop contagion risk tracing, so that if a project defaults, I can instantly identify other ongoing projects relying on the same structural engineer or architect.
14. As a legal researcher, I want BM25 full-text search across all certified statutory PDF documents, so that I can pinpoint encumbrances, litigation clauses, or specific consultant names across thousands of filing pages.
15. As a pipeline data engineer, I want the ingestion engine to be completely decoupled from downstream analytics through a canonical `RunReader` seam, so that changes in storage formats or compression do not break intelligence applications.
16. As a quantitative researcher, I want statewide historical project registries and quarterly Form 3 filings stored as date-stamped, ZSTD-compressed Parquet datasets, so that I can perform zero-copy SQL analytics across years of disclosures in milliseconds using DuckDB.
17. As an investment analyst inspecting a specific project, I want statutory project documents packaged into individual, project-isolated zip archives indexed by a lightweight Parquet manifest, so that I can retrieve only the documents for my project of interest without downloading a monolithic multi-gigabyte document repository.
18. As a forensic auditor, I want every quarterly Form 3 filing preserved with explicit `snapshot_date` and `quarter` columns alongside the original raw JSON payload, so that longitudinal expenditure audits maintain 100% data fidelity without schema truncation.
16. As a pipeline data engineer, I want every API response stored with an immutable SHA-256 hash and atomic manifest entry, so that any stakeholder can cryptographically verify data provenance against the official regulator.
17. As a pipeline data engineer, I want the ingestion collector to support idempotent resumption, so that interrupted network runs resume seamlessly without re-fetching completed projects.
18. As a pipeline data engineer, I want a rate-limited transport layer that respects portal stability, so that automated ingestion runs smoothly without triggering denial-of-service protections.
19. As a pipeline data engineer, I want project identity mismatches detected immediately during ingestion, so that corrupt portal payloads do not pollute downstream project snapshots.
20. As an AI coding or research agent, I want access to GujRERA intelligence tools via a Model Context Protocol (MCP) server, so that I can answer natural-language due-diligence inquiries, query escrow health, and retrieve land records programmatically.
21. As an application developer, I want a fast, in-memory fake implementation of `RunReader`, so that I can write comprehensive end-to-end integration tests without requiring multi-gigabyte disk snapshots.
22. As an operations manager, I want a web dashboard displaying real-time project metrics, interactive network graphs, and document search, so that non-technical team members can conduct visual due diligence.
23. As an operations manager, I want CLI commands for ingestion, pricing benchmarks, discrepancy audits, document search, and dossiers, so that routine reporting can be scripted in continuous integration pipelines.
24. As an institutional lender, I want to monitor the ratio of booked vs unbooked units over quarterly filing periods, so that I can assess inventory overhang and debt servicing capacity.
25. As an institutional lender, I want visibility into bank branch names and masked account numbers for Collection Accounts and Retention Escrow Accounts, so that loan agreements mandate valid statutory escrow routing.
26. As a municipal analyst, I want to track geographic project clustering by district, latitude, and longitude, so that infrastructure demand and urban sprawl can be mapped against Town Planning schemes.
27. As a compliance officer, I want to ensure sensitive personal identifiable information (PII) such as individual allottee names and promoter PAN numbers are redacted from public exports, so that statutory compliance does not breach privacy standards.
28. As an auditor, I want a distinction maintained between index form IDs, current QPR form IDs, filing dates, and fetch times, so that temporal lineage is never obscured by a single generic date field.
29. As a data analyst, I want registered unit transaction prices broken down into carpet area in square meters and square feet, so that pricing conforms to standardized institutional metrics.
30. As a portfolio manager, I want to run comparative multi-project side-by-side analyses across key metrics (velocity, booking rate, escrow balance, complaint counts), so that I can rank relative project health across investment portfolios.
31. As an institutional investor, I want an interpretable ML hedonic pricing model with SHAP explanations, so that I can understand the exact price premium associated with specific micro-markets, plot locations, and promoter track records.
32. As an institutional investor, I want a survival analysis model predicting the probability distribution of completion delays, so that I can stress-test internal rate of return (IRR) models against empirical regulatory slippage.
33. As a commercial real estate buyer, I want pricing benchmarks strictly segmented by asset class (`Commercial_Office`, `Commercial_Retail`, `Residential`), so that ground-floor retail shop premiums do not distort office suite valuations.
34. As a commercial real estate buyer, I want a vertical floor-level pricing gradient model, so that I can evaluate whether upper-floor office premiums or discounts conform to historical building sales.
35. As an institutional investor, I want an Escrow Cash Runway model computing monthly construction burn rate vs available 70% Retention Escrow Account liquidity, so that I know exactly how many months of solvency remain.
36. As a data scientist, I want geospatial feature engineering (DBSCAN clusters, transit distance, and spatial lag pricing), so that micro-market spatial dependencies are captured in valuation models.
37. As a homebuyer, I want to ask questions to an interactive AI Diligence Copilot in natural language, so that I can receive simple, jargon-free explanations backed by official RERA citations.
38. As a homebuyer, I want to see recent registered transaction prices in the same building, so that I have hard evidence to negotiate discounts during sales discussions.
39. As a buyer or investor, I want external real estate listing asking prices compared against statutory Form 3 registered sale prices (when external market data is ingested), so that I can compute the Broker Markup Index and negotiation spread.
40. As a forensic auditor, I want statutory promoter remarks automatically parsed and reconciled against discrepancies, so that legitimate project restructuring is clearly differentiated from unexplained financial anomalies.
41. As a risk analyst, I want soft-link clustering (`PROBABLE_SAME_AS`) for professionals with similar names, so that consultant overlaps without licensing IDs are highlighted with confidence scores rather than missed entirely.
42. As a legal researcher, I want hybrid BM25 and dense vector semantic search across all certified statutory PDF documents, so that I can find exact plot numbers, encumbrances, litigation clauses, or specific advocate names across thousands of filing pages.
43. As a pipeline data engineer, I want a decoupled `DocumentWorker` service processing large PDF files via an asynchronous SQLite task queue, so that heavy OCR and embedding operations never block or crash core tabular pipelines.
44. As a pipeline data engineer, I want a two-phase collection strategy, so that statewide tabular data can be harvested quickly without triggering multi-terabyte disk exhaustion from binary PDFs.
45. As a pipeline data engineer, I want an optional post-extraction PDF pruning flag (`--prune-binaries`), so that raw PDFs can be deleted after text extraction and hashing while retaining full FTS searchability.
46. As a data scientist, I want an append-only relational schema tracking observation runs, so that I can extract clean longitudinal panel datasets for time-series and survival modeling without data leakage.
47. As an ML engineer, I want an automated evaluation harness computing RMSE, MAE, and $R^2$ for pricing models and C-index for survival models, so that model iterations are rigorously validated.
48. As an NLP engineer, I want an automated retrieval evaluation benchmark measuring Mean Reciprocal Rank (MRR@5) on statutory document queries, so that search ranking quality is continuously tracked.
49. As an AI agent engineer, I want an automated agent rubric eval harness, so that I can measure the agent's tool-selection accuracy and enforce a 0% hallucination rate on statutory facts.
50. As an AI agent engineer, I want the agent bound by an Evidentiary Citation Contract, so that every claim in generated reports must cite a verified database field or PDF page SHA-256 hash.
51. As an application developer, I want the Model Context Protocol (MCP) server to operate via `stdio` transport, so that local AI tools (Antigravity, Cursor, Claude Code) connect directly to the embedded database without daemon overhead.
52. As an operations manager, I want an interactive web dashboard showcasing analytics charts, network graphs, and an agent copilot trace, so that technical and non-technical stakeholders can conduct visual due diligence.

## Implementation Decisions

### 1. Two-Tier Modular Architecture
The repository is split into two distinct tiers:
- **Ingestion Producer Tier (`gujrera_pipeline`)**: Responsible for fetching, rate-limiting, verifying, archiving, and indexing raw RERA portal responses into an immutable run store.
- **Intelligence Consumer Tier (`real_estate_intelligence`)**: Responsible for parsing project snapshots, populating relational schemas and full-text indexes, running financial and engineering audits, modeling entity graphs, running ML pipelines, and presenting insights.

### 2. Canonical Seam: The `RunReader` Abstraction (ADR-0001)
To ensure complete decoupling between ingestion and consumption:
- All downstream consumers interface with data runs strictly through a reader interface (`RunReader`).
- The reader interface returns immutable, domain-typed `ProjectSnapshot` objects and lazy `DocumentRef` iterators.
- Two concrete adapters satisfy this interface:
  - `DiskRunReader`: Reads production compressed archives and SQLite manifests from disk.
  - `FakeRunReader`: In-memory implementation populated with deterministic fixtures for unit and integration testing.
- Direct database connections or filesystem traversal by consumers into raw run directories are strictly forbidden.

### 3. Append-Only, Run-Versioned Relational Fact Modeling (Q2)
Downstream analytics query a single normalized relational SQLite database. All entity and transaction tables incorporate `run_id` as part of composite primary keys to preserve longitudinal history across observation periods:

- `projects`: Master project records including `run_id`, `project_id`, registration number, promoter details, GPS coordinates, planning fields (TP scheme, FP number, Survey number), schedule velocity, engineering score, time elapsed percentage, booking rate, and complaint counts.
- `unit_transactions`: Granular unit-level registered sales from Form 3 filings, including `run_id`, `project_id`, `form_three_id`, block name, unit type (`Residential`, `Shop`, `Office`), asset class, carpet area (sqm and sqft), consideration amount, agreement date, and calculated rates per sqft/sqm.
- `finances`: Historical cost observations tracking `run_id`, `project_id`, `form_three_id`, filing date, filing type (`index` vs `latest`), estimated project cost, incurred and paid expenditure, and allowable escrow withdrawal.
- `banks`: Account-level banking disclosures distinguishing between Retention Escrow Accounts (Account Type 1) and Collection Accounts (Account Type 2), recording bank name, branch, masked account number, opening balance, deposit amount, withdrawal amount, and closing balance.
- `inventory_blocks`: Block-level physical tallies tracking `run_id`, `project_id`, block name, total units, booked units, unbooked units, and construction milestones.
- `quarterly_timeline`: Longitudinal tracking of physical progress reports across quarters, recording `run_id`, `project_id`, financial year, quarter period, progress percentage, and submission timestamps.
- `professionals`: Directory of architects, structural engineers, chartered accountants, and contractors bound to each project, capturing `run_id`, `project_id`, role, name, license number, and council registration.
- `promoters`: Developer entities with past track records, including `run_id`, `promoter_id`, name, promoter type (Company/Individual), completed project count, and ongoing project count.
- `noc_bu_records`: Municipal Building Use permissions and clearance certificates by block, capturing `run_id`, `project_id`, block name, BU status, and issue date.
- `form5_compliance`: Longitudinal compliance records of Section 4(2)(l)(D) annual audits, tracking `run_id`, `project_id`, financial year, submission status, and CA details.
- `documents_catalog`: Metadata catalog of all linked PDF filings with classification tags (`title_search_report`, `form_one_architect`, `form_two_engineer`, `form_three_ca`, `bu_permission_noc`, `form_five_audit`), source JSON path, and SHA-256 hashes.
- `document_fts`: SQLite FTS5 virtual table indexing extracted page-level text with BM25 ranking.
- `document_jobs`: Asynchronous worker queue table tracking heavy document download, OCR, and embedding generation tasks with statuses (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`), retry counts, and error logs.
- `market_listings`: External broker listing cache capturing listing portal source (`99acres`, `MagicBricks`), marketing scheme name, locality, asking rate per sqft, claimed configuration, matched `project_id`, and entity-matching confidence score.

A canonical SQL view (`v_current_projects`) exposes the latest observed run state for standard queries, while analytics modules accept an optional `--as-of-run <run_id>` parameter for point-in-time historical backtesting.

### 4. Decoupled Document Processing Micro-Architecture (`DocumentWorker`)
To guarantee that large PDF downloads, OCR, and vector embedding computations never degrade core platform availability:
- **Asynchronous Task Queue**: Tabular ingestion populates the `document_jobs` table with document references discovered during Phase 1.
- **Isolated Worker Process**: The `DocumentWorker` runs as a completely decoupled background worker that polls `document_jobs`. It fetches PDFs, computes SHA-256 digests, extracts text pages via `pypdf`/OCR, generates dense vector embeddings, and writes to `document_fts` and the vector index.
- **Fault-Tolerant Resilience**: Network drops, malformed PDFs, or out-of-memory errors in `DocumentWorker` update the job status to `FAILED` with retry backoff, leaving the main database, tabular fact store, and UI serving without disruption.
- **Optional Pruning**: When `--prune-binaries` is enabled, the worker deletes raw binary files after successful extraction, preserving text tokens, SHA-256 hashes, and download URLs.

### 5. Two-Phase Ingestion & Pluggable Transport Seam (Q1 & Q3)
- **Phase 1 (Tabular Ingestion)**: Ingests 100% of structured metadata, financial tables, inventory blocks, and party disclosures across all registered projects into the run store. Captures statewide baseline intelligence within a compact disk footprint (<10 GB).
- **Phase 2 (Selective Document Harvesting)**: Binary PDF downloading (`documents.py`) and text extraction are triggered on-demand by project ID, district, or audit risk threshold.
- **Pluggable Transport Interface**: The network layer is formalized as a `Transport` protocol interface. `CurlTransport` acts as an initial adapter to handle legacy portal SSL/TLS renegotiation, allowing alternative modern Python HTTP clients (`httpx` with custom SSLContext) to be swapped in without modifying `Collector`.

### 6. Statutory Discrepancy Auditing Logic & Remarks Reconciliation (Q5)
The auditor applies deterministic heuristic checks across relational tables:
- **Cost Reversals**: Flags projects where cumulative incurred expenditure in a newer Form 3 is lower than an earlier filing.
- **Velocity Lag**: Flags projects where the ratio of certified physical progress (Form 1) to elapsed schedule time is below 0.75x.
- **Escrow Liquidity Risk**: Flags projects where the Retention Escrow Account balance is under ₹50,000 despite high booking rates (>50%) and incomplete construction.
- **Escrow Cash Runway**: Computes monthly construction burn rate ($$ \Delta \text{Incurred Cost} / \Delta \text{Time} $$) against 70% Retention Escrow Account liquidity to project runway in months. Flags projects with under 3 months of cash runway as HIGH insolvency risk.
- **Regulatory Defaults**: Flags projects with overdue QPR filings, registered alterations, or active consumer complaints.
- **Remarks Reconciliation**: Deterministic regex pattern matching scans promoter remarks in Form 1 and Form 3 for statutory terms (e.g. court stays, municipal delays, phase revisions, force majeure). Flags audit leads as `explained_by_promoter: true` to prevent false-positive alarms on legitimate project adjustments.

### 7. Multi-Hop Contagion & Knowledge Graph (Q4)
- Graph nodes: `Project`, `Promoter`, `Professional`.
- Directed edges:
  - `DEVELOPED_BY`: Project to Promoter.
  - `CERTIFIED_BY`: Project to Professional (verified by Council of Architecture CoA or ICAI registration number).
  - `PROBABLE_SAME_AS`: Probable link between two professional records sharing normalized names with Levenshtein distance ≤ 2, annotated with a confidence score.
- Contagion algorithm: Multi-hop graph traversal identifying active projects connected to professionals associated with defaulted or delayed developments.

### 8. Quantitative Data Science, Commercial Real Estate (CRE) & Geospatial ML
- **Asset-Class Segmentation**: `PricingIntelligence` segments transactions into `Residential`, `Commercial_Office`, `Commercial_Retail`, and `Industrial_Warehouse`.
- **Vertical Floor-Gradient Modeling**: Models floor-wise pricing variance in commercial towers (ground-floor retail premium vs upper-floor office rates).
- **Hedonic Pricing Engine**:
  - Gradient boosting regressor (LightGBM) trained on CA-certified Form 3 unit sales.
  - Features: Asset class, carpet area (sqm/sqft), floor level, block/tower identifier, TP scheme geographic cluster, promoter portfolio track record, and registration year.
  - Interpretability: Integrated SHAP TreeExplainer outputs exact feature attributions for each prediction.
- **Completion Delay Survival Model**:
  - Cox Proportional Hazards regression and Kaplan-Meier estimators modeling time-to-completion.
  - Features: Current velocity ratio (Form 1 progress / elapsed time), ratio of incurred expenditure to estimated cost, escrow liquidity ratio, promoter complaints count, and default quarters.
  - Outputs: Estimated completion date probability curves (e.g. 50th, 75th, and 90th percentile handover dates).
- **Geospatial (GIS) Feature Engineering**:
  - Computes spatial density clusters (DBSCAN) and distance to key infrastructure (highways, metro lines, BRTS corridors) from project latitude and longitude coordinates.

### 9. External Market Listing Ingestion Seam (Data-Gated)
- **Schema & Seam Ready**: The pipeline defines the `market_listings` schema and a two-stage entity-matching engine:
  - Stage 1: Spatial radius search matching listings within 300 meters of project GPS coordinates.
  - Stage 2: Token similarity and Levenshtein string matching on project and promoter names, yielding a match confidence score ($0.0 - 1.0$).
- **Broker Markup Spread**: When listing data is present, computes the percentage markup between asking rates and Form 3 registered rates.
- **Data-Readiness Gating**: In accordance with Karpathy guidelines, this module remains dormant until external portal feeds or scraped CSV exports are provided.

### 10. Hybrid NLP & Document Intelligence
- **Hybrid Retrieval (RRF)**:
  - Lexical Search: SQLite FTS5 with BM25 ranking for exact legal identifiers (survey numbers, plot numbers, advocate names).
  - Semantic Search: Local dense vector embeddings (`sentence-transformers/all-MiniLM-L6-v2`) over extracted PDF page text.
  - Fusion: Reciprocal Rank Fusion (RRF) combines BM25 and vector similarity ranks to produce the final document ordering.
- **Document Classification**: Classifies PDFs based on JSON paths and file naming patterns into canonical categories.

### 11. Agentic Architecture & Evidentiary Citation Contract
- **MCP Server**: Implements tools (`get_project_summary`, `get_escrow_health`, `get_land_records`, `predict_pricing_benchmark`, `forecast_completion_delay`, `calculate_escrow_runway`, `search_certified_documents`, `trace_contagion_risk`) communicating via `stdio` transport.
- **Evidentiary Citation Contract**:
  - The AI agent is strictly restricted from generating factual claims without attaching a structured citation token:
    `[Source: Run <run_id> | Form <form_id> | DocSHA <sha256_prefix> | Page <num>]`
  - Uncited factual assertions are treated as validation errors by the execution harness.

### 12. Interactive Portfolio UI & Showcase
- Local web server serving:
  - **Diligence Dashboard**: Interactive charts displaying unit pricing distributions by asset class, historical velocity vs calendar schedule, and escrow health gauges.
  - **Network Explorer**: Interactive force-directed graph visualizing promoter-professional relationships and contagion paths.
  - **Agent Copilot Sidebar**: Natural-language chat interface displaying real-time tool execution traces and cited statutory evidence.
  - **CLI**: Commands for ingestion, pricing analysis, discrepancy audits, claims verification, document search, dossier generation, and server launching.

## Testing & Evaluation Decisions

### What Makes a Good Test
- **Behavioral Testing**: Only test public module interfaces (`RunReader`, `ProjectAuditor`, `PricingIntelligence`, `SalesClaimVerifier`, `KnowledgeGraph`, `DocumentSearchEngine`, `RealEstateIntelligenceMCP`, `DocumentWorker`).
- **Hermetic Isolation**: In-memory SQLite (`:memory:`) and mock adapters (`FakePortal`, `FakeRunReader`) for all automated test runs.
- **Deterministic & Fast**: Core unit and integration test suite must execute in under two seconds.

### Automated Evaluation Harness (AI/ML & Agent Benchmarking)
A dedicated evaluation suite (`tests/eval_harness.py`) benchmarks:
1. **ML Model Performance**:
   - Pricing Model: Evaluated on stratified 5-fold cross-validation (Target: RMSE < ₹500/sq.ft, $R^2 > 0.80$).
   - Survival Model: Evaluated on Concordance Index (Target: C-index > 0.75).
2. **Hybrid RAG Retrieval**:
   - Evaluated on a curated set of 30 statutory legal questions with ground-truth document page references (Target: MRR@5 > 0.85, Recall@5 > 0.90).
3. **Agent Factuality & Rubric Check**:
   - Automated evaluation running the agent across 10 multi-step due diligence tasks.
   - Evaluates:
     - Tool selection accuracy (100% correct tool sequence).
     - Citation coverage (100% of facts have valid citations).
     - Hallucination score (0% discrepancy against database ground truth).

### Prior Art
- `gujrera_pipeline/tests/test_pipeline.py`: Demonstrates `FakePortal` and `FakeRunReader` patterns for testing transport and ingestion boundaries.
- `real_estate_intelligence/tests/test_intelligence.py`: Demonstrates schema verification, FTS search, discrepancy audits, and MCP tool tests.

## Out of Scope (Q6)

1. **Multi-Tenant Hosted Cloud Infrastructure**: Distributed Kubernetes clusters, cloud IAM, and multi-tenant SaaS features are strictly out of scope. The platform is explicitly designed as a **Sovereign Local-First Analyst Workstation** (embedded SQLite, zero cloud dependencies, offline diligence).
2. **Statewide Distributed Crawling**: Automated bypass of portal bot protections, CAPTCHA cracking, or proxy rotation. Ingestion relies on authenticated REST transport.
3. **Non-Gujarat RERA Portals**: Expanding beyond Gujarat RERA (e.g. MahaRERA, UP RERA) is out of scope. The domain models are strictly anchored to Gujarat municipal planning standards (TP Schemes, FP numbers).
4. **Automated Judicial & Legal Filings**: The platform produces analytical leads and evidentiary dossiers; it does not file formal legal petitions with regulatory authorities.
5. **Black-Box Deep Learning Without Interpretability**: Large, unexplainable neural networks for pricing or valuation are rejected in favor of interpretable gradient boosting (SHAP) and survival models.
6. **Automated Document Redaction of Scanned Bitmaps**: Extracting and redacting PII from scanned non-searchable image PDFs is out of scope; PII exclusion is enforced at the structured tabular export layer.

## Further Notes & Data Readiness Status

### Data Readiness & Implementation Roadmap

In accordance with `/karpathy-guidelines`, features are implemented strictly as their required underlying data is present and verified:

| Capability / Module | Required Data Sources | Readiness Status in Codebase |
|---|---|---|
| **Relational Fact Base (14 Core Tables)** | Master Index CSV + Run JSON dumps | **IMPLEMENTED & VERIFIED** (Curated in `test_intelligence.sqlite` WAL) |
| **Section 4(2)(l)(D) Escrow Over-Withdrawal** | Form 3 cost history + 70% Escrow bank passbook | **IMPLEMENTED & VERIFIED** (Proviso 1 physical progress spend cap) |
| **Escrow Burn Rate & Cash Runway** | Form 3 cost history + Bank account balances | **IMPLEMENTED & VERIFIED** (Present in `finances` and `banks` tables) |
| **Encumbrance & Mortgage Risk Audit** | Sub-Registrar records + Form B declarations | **IMPLEMENTED & VERIFIED** (Active loan & mortgage check) |
| **Interpretable Hedonic Pricing ML** | Registered unit transactions + project covariates | **IMPLEMENTED & VERIFIED** (GBDT + Exact TreeSHAP Additive Efficiency) |
| **Completion Delay Survival Model** | Project durations + quarterly velocity + BU records | **IMPLEMENTED & VERIFIED** (Cox Proportional Hazards, C-index 1.0) |
| **Longitudinal Price Trajectory & CAGR** | Registered unit agreement dates across quarters | **IMPLEMENTED & VERIFIED** (Quarterly medians & annualized CAGR) |
| **Geospatial (GIS) Feature Engineering** | Project GPS coordinates + TP/FP numbers | **IMPLEMENTED & VERIFIED** (Haversine distance & micro-market density) |
| **Decoupled DocumentWorker Micro-Architecture** | `document_jobs` queue + downloaded PDFs | **IMPLEMENTED & VERIFIED** (2,006 parsed pages indexed in FTS5) |
| **Forensic Knowledge Graph & Contagion** | Professional & promoter assignment tables | **IMPLEMENTED & VERIFIED** (Vis.js interactive network explorer) |
| **Terminal Web Dashboard (Chart.js 4.4)** | Quantitative analytics APIs + Chart.js UMD | **IMPLEMENTED & VERIFIED** (Survival, SHAP waterfall, price trajectory) |
| **AI Diligence Copilot (MCP-Connected)** | `RealEstateIntelligenceMCP` + citation contract | **IMPLEMENTED & VERIFIED** (Embedded slide-over drawer with prompt chips) |
| **Columnar Parquet Data Lake & Manifest** | Date-stamped Parquet indexes + Form 3 filings | **IMPLEMENTED & VERIFIED** (11 Parquet indexes + 4 quarterly filings, ADR-0002) |
| **External Market Listing Ingestion** | Scraped listings from 99acres/MagicBricks | **SEAM DESIGNED** (Awaiting external listing crawl/import) |

- **Domain Terminology Compliance**: All code, documentation, and user interfaces must strictly adhere to `GLOSSARY.md`. Terms such as "scheme", "site", "property", "crawl", "batch", and "builder" must be avoided in favor of "project", "run", "project snapshot", "promoter", and "professional".
- **Temporal Lineage Preservation**: In accordance with the data contract, index form IDs, current QPR form IDs, filing submission dates, and run observation timestamps must remain distinct fields. They must never be merged into a single generic date column.
- **Portfolio Showcase Documentation**: The repository will maintain a dedicated `SHOWCASE.md` outlining the architecture, ML evaluation results, SHAP plots, and agent evaluation metrics to serve as an engineering portfolio piece.
