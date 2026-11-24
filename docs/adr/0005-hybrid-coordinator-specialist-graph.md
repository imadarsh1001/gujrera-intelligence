# 0005. Hybrid Map-Reduce Coordinator, Specialist Subgraphs & Server-Bound A2UI 1.0 Architecture

## Context & Problem Statement

1. **Evolution from Single-Agent Investigator (ADR-0004)**: Wave 1A-1 introduced a monolithic single-agent investigator node (`investigator`) handling queries end-to-end. While sufficient for single-turn single-project inquiries, multi-project comparisons, promoter-wide contagion tracing, and deep pilot forensic audits quickly exhaust single-agent prompt context, serialize independent statutory database queries, and blur role responsibilities across distinct forensic playbooks.
2. **Deterministic Map-Reduce Parallelism**: Real estate due diligence decomposes naturally into parallelizable, domain-specific tasks: statutory compliance validation, sales claim verification, spatial density benchmarking, promoter contagion analysis, and discrepancy auditing. Running these tasks sequentially introduces unnecessary latency, while unconstrained autonomous multi-agent swarms risk non-deterministic hallucination, unpredictable execution order, and budget explosion.
3. **Database Concurrency & Read-Only Safety**: The GujRERA fact base (`data/intelligence.sqlite`) is an append-only relational database accessed strictly in read-only mode (`mode=ro`). Parallel branches in LangGraph executing concurrent queries require isolated connection lifecycles per worker thread/task to avoid SQLite multithreaded connection sharing, statement collision, or uncoordinated transactions.
4. **Resilient Fault Isolation**: A failure, timeout, or partial schema mismatch in one specialist branch (e.g. spatial pricing calculation or legacy grandfathered project missing Form 1/3/5 filings) must never crash the entire workflow or prevent other specialists from reporting verified statutory facts.
5. **Server-Bound A2UI 1.0 Protocol**: Frontend consumers require structured, interactive UI cards (such as Dossier Truth, Claim Verdict, Spatial Comps, and Audit Leads) delivered over the streaming AG-UI protocol. Legacy CopilotKit / AG-UI v0.9 widgets lack support for strict server-bound component catalogs, `@path` pointer bindings, and scoped surface lifecycles.

## Decision

We establish the Hybrid Map-Reduce Coordinator, Specialist Subgraph, and A2UI 1.0 architecture:

1. **Hybrid Map-Reduce Coordinator Pattern**:
   - **Ingress & Guardrails**: User queries enter `input_guardrail` (PII scrubbing, prompt-injection screening, entity extraction, and state resets via `Overwrite`).
   - **Coordinator Plan (`coordinator_plan`)**: Evaluates query intent via `[pid:N]` deterministic fast-path or Granite Micro semantic router (`get_router_llm`), extracts explicit PIDs before adjacent-cue price claim parsing, resolves exact or trigram fuzzy project matches, and fans out parallel tasks using LangGraph `Send` to specialized workers (or routes greetings/off-topic directly to `deliver_answer` with 0 DB tools). Parallel fan-out is strictly capped at 10 projects per request.
   - **Deterministic Specialist Branches**:
     - `due_diligence`: Validates statutory truth flags, project summaries, spatial pricing benchmarks (IQR spread), and sales claims (`verify_sales_claim` mapped cleanly into `ClaimVerdictCard`). Emits structured findings and optional followup requests.
     - `pilot_auditor`: Conditioned strictly on `data_tier == "pilot_deep"` or explicit forensic discrepancy intent. Audits Section 4(2)(l)(D) escrow compliance, quarterly timelines, cost reversals, and withdrawal velocity.
     - `promoter_contagion`: Traces cross-scheme entity networks, associated directors, and shared liabilities, registering full portfolio project IDs into `tool_evidence`.
     - `market_analyst`: Macro absorption density, `project_summaries` screening, `markup_spread_snapshot.json`, and `zombie_radar` summary metrics (zero `unit_transactions` scans) emitting MsgPack-safe `[agg:]` verified scalars.
   - **Coordinator Reduce Barrier (`coordinator_reduce`)**: Aggregates additive findings, registers portfolio/screened/disambiguation project IDs and `[agg:]` scalars into `tool_evidence`, deduplicates followups across branches (`dispatched_keys`), enforces global budgets (max 35 tool calls, max 2 hops), and conditionally triggers post-barrier specialists before synthesis.
2. **Single Verified Exit Gate**:
   - Synthesis is consolidated in a single writer node (`synthesizer`) operating under strict `.agents/skills/*/SKILL.md` guidance with indirect-injection fencing.
   - Output passes through `citation_verifier` ensuring every statutory claim and certificate is grounded in registered tool evidence `[pid:X]` / `[bu:D@P]`.
   - `a2ui_emitter` packages validated structured findings into server-bound A2UI 1.0 surfaces.
   - `deliver_answer` streams the verified final answer using `manually_emit_message` with matched `message_id`.
3. **Database Concurrency & Timeout Isolation**:
   - Every specialist branch opens its own independent, fresh SQLite connection via `get_connection(db_path, read_only=True)` wrapped in a `try...finally` block.
   - Each query operation is guarded by a watchdog timer (`threading.Timer(timeout_s, con.interrupt)`) to prevent stalled locks or pathological query plans from blocking worker threads.
   - LangGraph execution is configured with `max_concurrency=5` and `recursion_limit=25`. Remote database pooling (e.g. Turso HTTP/libsql connection management) is documented for Wave 3 serverless scale.
4. **State Schema & Public Surface Boundary**:
   - **Internal State (`ForensicAgentState`)**: Uses additive reducers (`findings: Annotated[list, operator.add]`, `tool_call_count: Annotated[int, operator.add]`), reset cleanly on turn boundary using `langgraph.types.Overwrite`.
   - **Public Ingress (`PublicInputState`)**: Restricts client input strictly to `messages` and optional `active_project_id`.
   - **Public Egress (`PublicAgentState`)**: Exposes only verified, non-leaking state channels: `messages`, `active_project_id`, `canvas_mode`, `highlight_pins`, `active_cluster`, `active_specialists`, `a2ui_surfaces`, and `verification_passed`.
   - **A2UI 1.0 Spec Wire Format**:
     - Structured components conform to A2UI v1.0 specifications (`version: "1.0"`, unique `surfaceId = f"{card}_{entity}_{run_id}"`, inline root components).
     - Catalog defined in `forensic_agent/a2ui_catalog.json` featuring 8 cards: `DossierTruthCard`, `ClaimVerdictCard`, `SpatialCompsCard`, `ClusterSplitCard`, `AuditLeadsCard`, `ProjectDisambiguationCard`, `MarketScreenTable`, and `MarketStatsCard`.

## Consequences & Operational Reality

- **Zero Contention**: Per-branch read-only SQLite connections eliminate thread lock contention and preserve database file immutability.
- **Fail-Soft Reliability**: If an individual specialist encounters a timeout or data irregularity, it yields a graceful partial error finding; other specialists proceed uninhibited, and the synthesizer explicitly reports partial data coverage.
- **Strict Grounding**: The decoupled map-reduce architecture separates factual data retrieval from creative natural language synthesis, preventing intermediate agent hallucination while keeping tool-call budgets strictly bounded.
- **Frontend Compatibility**: Emitted A2UI 1.0 JSON payloads are consumed natively by `@ag-ui/client >= 1.0.5` components on the `/analyst` Astryx workbench without dependency on legacy CopilotKit v0.9 client libraries.
