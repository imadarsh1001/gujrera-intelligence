# 0004. Analyst Workbench (Astryx + AG-UI) & Agent Runtime Architecture

## Context & Problem Statement

1. **Analyst Due-Diligence Interface**: The legacy frontend (`ui/static/index.html`) is a single-page static dashboard with vanilla Chart.js charts and a basic copilot drawer. While effective for executive overviews, it does not support multi-step investigative workflows, interactive forensic audits, side-by-side comparative diligence, or streaming generative agent interactions.
2. **Design System & High-Density UI**: Institutional analysts require high-density, accessible, and structured data visualization. To achieve Bloomberg/Palantir-grade visual polish without ad-hoc styling sprawl, we require a unified component design system (`@astryxdesign/core`, `@astryxdesign/theme-neutral`) backed by `@stylexjs/stylex` and Tailwind CSS v4.
3. **Agentic Diligence Runtime**: The `/analyst` workbench requires an agentic runtime powered by LangGraph (`langgraph>=1.2`) and CopilotKit / AG-UI (`ag-ui-langgraph`). Due-diligence agents must support stateful graph orchestration, step-by-step tool invocation, streaming responses, and human-in-the-loop verification gates.
4. **Local Workstation vs. Vercel Serverless Checkpointer Policy**:
   - Sovereign workstations execute locally with an append-only SQLite checkpointer (`data/agent_checkpoints.sqlite` / `real_estate_intelligence/data/agent_checkpoints.sqlite`), fully decoupled from the read-only relational fact base.
   - Serverless cloud environments (such as Vercel) have ephemeral, read-only root filesystems where local SQLite writes fail or do not persist across lambdas. A clean checkpointer abstraction is necessary to allow ephemeral memory or remote persistence in cloud runtimes.
5. **Deferral of Hybrid Vector Search**: While `document_manifest` schemas exist, the full-text optical character recognition (OCR) corpus (`document_fts`) is currently unpopulated in the public repository tier. Introducing dense vector search (e.g. `sqlite-vec`, Chroma, or external vector stores) before `document_fts` contains extracted filing text would introduce binary dependency bloat, Windows WDAC friction, and ungrounded embeddings.

## Decision

We establish the following architectural standards for the analyst workbench and agent runtime:

1. **Frontend Architecture (`frontend/`)**:
   - Scaffolded as a modern React 19 + TypeScript single-page application built with Vite.
   - Core design primitives provided by `@astryxdesign/core` and `@astryxdesign/theme-neutral` via `@stylexjs/stylex`.
   - Utility styling powered by Tailwind CSS v4 via `@tailwindcss/vite`.
   - Strict CSS layer cascade declared at line 1 of `frontend/src/index.css`:
     ```css
     @layer reset, theme, base, astryx-base, astryx-theme, components, utilities;
     ```
   - Automated testing via Vitest with `jsdom` environment.
2. **Analyst Workbench Delivery (`/analyst`)**:
   - The `/analyst` route hosts the interactive diligence workbench with real-time agent streaming.
   - The legacy dashboard remains available at `/` and `/static/index.html` for backward compatibility.
   - Real-time agent events stream via the AG-UI protocol (`ag-ui-langgraph`).
3. **Checkpointer Policy & Database Isolation**:
   - Local: `SqliteSaver` targets `data/agent_checkpoints.sqlite`.
   - Cloud (Vercel): Configurable checkpointer factory defaulting to in-memory checkpointer (`MemorySaver`) or managed remote store when running without persistent local storage.
   - Fact Base Invariant: `data/intelligence.sqlite` remains strictly read-only (`mode=ro`). The agent checkpoint database is entirely separate and never shares a SQLite connection or file lock with the fact base.
4. **Information Retrieval Strategy**:
   - Agents retrieve statutory ground truth using structured queries against `db/queries.py` and FastMCP tools (`get_project_dossier`, `audit_discrepancies`, `verify_sales_claim`, `get_spatial_pricing_benchmark`).
   - Dense vector embeddings and hybrid vector search are formally deferred until `document_fts` is populated from filing PDFs in subsequent waves.

## Consequences & Operational Reality

- **Windows WDAC Pre-Flight Gate**: All compiled native extensions (`.pyd` / C-DLLs) required by LangGraph and AG-UI (`ormsgpack`, `xxhash`, `tiktoken`, `jiter`) are verified under Windows Defender Application Control (WDAC) before promotion to the main environment.
- **Decoupled State**: Ingestion pipelines, analytical fact bases, and conversational agent memory reside in separate storage artifacts, preventing schema corruption and write-lock contention.
- **Build & Test Verification**: The frontend workspace is validated via `npm.cmd run build` and `npm.cmd test`, ensuring zero bundle regressions and full TypeScript compliance.
