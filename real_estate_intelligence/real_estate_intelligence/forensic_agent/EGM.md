# forensic_agent — Sovereign LangGraph Forensic Due-Diligence Agent

## Overview
The `forensic_agent` package provides an institutional-grade, LangGraph-orchestrated forensic due-diligence agent architecture for the Gujarat Real Estate Regulatory Authority (GujRERA) platform. Built on `langgraph>=1.2` and `ag-ui-langgraph>=0.0.48`, it executes multi-turn conversational diligence, semantic intent routing via Granite Micro, hybrid map-reduce specialist fan-out (including macro market screening and fuzzy project disambiguation), rigorous evidentiary verification (`[pid:]`, `[bu:]`, `[agg:]`), server-bound A2UI 1.0 surfaces, and real-time streaming to the `/analyst` workbench.

> [!NOTE]
> Legacy `agent/copilot.py` and `POST /api/copilot` are preserved untouched for dashboard backward compatibility. However, the legacy `_deterministic_fallback` regex pattern in `copilot.py` is identified as a known brittle implementation and is strictly **not reused** in this package; the forensic agent implements deterministic evidentiary resolution strictly backed by verified live specialist executions and candidate disambiguation.
>
> **Security Notice (Wave 1A-2b):** Direct user prompt injection is screened by `input_guardrail` and routed to a dedicated refusal step before semantic routing or specialist execution. Indirect prompt injection inside untrusted third-party tool and filing outputs is sanitized via `sanitize_tool_prose` before synthesis.

## Interface
- `ForensicAgentState` — TypedDict state schema enforcing plain-JSON serializability with additive reducers (`findings: Annotated[list, operator.add]`, `tool_call_count: Annotated[int, operator.add]`, `messages: Annotated[list, add_messages]`, `draft_answer`, `retry_feedback`, `active_project_id`, `canvas_mode`, `highlight_pins`, `active_cluster`, `active_specialists`, `a2ui_surfaces`, `planned_tasks`, `hop_count`, `dispatched_keys`, `intent`, `active_playbook`, `guardrail_flags`, `verification_passed`, `offline_mode`) [state.py:ForensicAgentState]
- `create_forensic_graph(tools=None, checkpointer=None, llm=None, router_llm=None, offline_mode=False, con=None, db_path=None, recursion_limit=25)` — Compiles the hybrid coordinator map-reduce workflow with `recursion_limit` and `max_concurrency=5`: `input_guardrail` -> (`refusal` | `coordinator_plan`) -> (direct reply | `synthesizer` | parallel `Send` across `due_diligence_specialist`, `pilot_auditor_specialist`, `promoter_contagion_specialist`, `market_analyst_specialist`) -> `coordinator_reduce` -> (optional post-barrier `Send`) -> `synthesizer` -> `citation_verifier` -> `a2ui_emitter` -> `deliver_answer` -> `END` [graph.py:create_forensic_graph]
- `due_diligence_specialist(item)` — Deterministic specialist executing statutory truth flags, 4-quadrant dossier extraction, empirical spatial benchmarks, and sales claim verification (`ClaimVerdictCard` mapped from `SalesClaimVerifier`) under per-branch `mode=ro` connection isolation and watchdog timeout [specialists.py:due_diligence_specialist]
- `pilot_auditor_specialist(item)` — Conditional specialist auditing Section 4(2)(l)(D) escrow, quarterly delay velocity, and uningested filing detection under timeout isolation [specialists.py:pilot_auditor_specialist]
- `promoter_contagion_specialist(item)` — Specialist tracing developer portfolios, cross-scheme contagion, and multi-cluster geographic partitioning [specialists.py:promoter_contagion_specialist]
- `market_analyst_specialist(item)` — Market screening specialist querying indexed `project_summaries`, `markup_spread_snapshot.json`, and `get_zombie_radar_data` (zero `unit_transactions` scans) to produce MsgPack-safe `[agg:]` scalars and `MarketScreenTable` / `MarketStatsCard` payloads [specialists.py:market_analyst_specialist]
- `build_a2ui_surfaces(findings, run_id=None)` — Generates spec-compliant A2UI 1.0 JSON payloads (`version: "1.0"`, unique `surfaceId = f"{card}_{entity}_{run_id}"`, inline root components, scrubbed leaves) for 8 catalog cards: `DossierTruthCard`, `SpatialCompsCard`, `ClaimVerdictCard`, `ClusterSplitCard`, `AuditLeadsCard`, `ProjectDisambiguationCard`, `MarketScreenTable`, and `MarketStatsCard` [a2ui_surfaces.py:build_a2ui_surfaces]
- `load_playbook(name)` / `get_playbook_instructions(intent, data_tier)` — Loads and caches stripped institutional diligence instructions from `.agents/skills/*/SKILL.md` [playbooks.py:load_playbook]
- `get_llm(...)` / `get_router_llm()` / `get_synthesis_llm()` — Cloudflare AI Gateway REST client factory with synchronous guardrail enforcement (error codes 2016/2017), `disable_streaming=True`, bounded completion budgets (`384` router / `3072` synthesis), and automatic offline fallback [llm_gateway.py:get_llm]
- `run_input_guardrail(state)` — Turn initialization resetting deliberation channels and additive reducers via `Overwrite` while preserving conversation context [guardrails.py:run_input_guardrail]
- `verify_evidentiary_output(draft_text, tool_evidence)` — Synchronous citation verifier enforcing `[pid:<id>]`, project-bound `[bu:<doc_id>@<pid>]`, and `[agg:<id>]` markers against current turn evidence, and rejecting unqualified escrow/compliance assurances on `statewide_core` or `SKIPPED_UNINGESTED` schemes [guardrails.py:verify_evidentiary_output]
- `sanitize_tool_prose(text)` — Fences untrusted database strings against indirect prompt injection before feeding to LLM synthesis [guardrails.py:sanitize_tool_prose]

## Invariants
- Zero unverified draft token leaks: Router and synthesis LLM calls pass `emit-messages: False` and `disable_streaming=True`; `synthesizer` writes completed prose only to `draft_answer`. Only `deliver_answer` (or `refusal`) streams verified prose over the wire using `manually_emit_message` with matched `message_id`.
- Execution budget boundaries: Coordinator enforces `recursion_limit=25`, `max_concurrency=5`, and a global ceiling of max 35 tool calls and max 2 hops per conversation turn.
- Map-reduce fault isolation: Every specialist runs inside a `try...finally` block with `threading.Timer(timeout_s, con.interrupt)`. Query errors or timeouts return structured partial error findings without crashing sibling specialists or the coordinator.
- Concurrency isolation: Every specialist opens its own isolated `get_connection(db_path, read_only=True)` (`mode=ro`), guaranteeing zero thread lock contention or mtime mutations on `data/intelligence.sqlite`.
- `statewide_core` escrow honesty: Any `statewide_core` project in `tool_evidence` is treated as having uningested Form 3 / Form 5 / escrow disclosures; unqualified fund-diversion or clean-audit assurances are rejected unless explicitly qualified in the same sentence/clause.
- Additive state reducers & clean resets: Parallel findings merge via `operator.add`; turn boundaries cleanly reset reducers using `langgraph.types.Overwrite([])` and `Overwrite(0)`.
- A2UI 1.0 wire format: Emitted surfaces adhere strictly to `version: "1.0"` with scoped `surfaceId` descriptors and single root components (`id: "root"`).
- Single verification retry: If citations fail, `citation_verifier` sets `retry_feedback` and retries `synthesizer` exactly once; persistent failures strip/flag invalid citations (including unverified `[agg:...]`) with a compliance notice.

## Side Effects
- Opens lightweight read-only SQLite connections per specialist task, cleanly closed in `finally:` blocks.
- Emits real-time AG-UI SSE protocol events (`RunStarted`, `TextMessageStart/Content/End`, `StateSnapshot`, `MessagesSnapshot`, `RunFinished`).
- When `ENABLE_FORENSIC_AGENT` is not `"1"`/`"true"`, `POST /api/agent` returns HTTP `503`.

## Verification
- Test suite:
  - `python -m pytest real_estate_intelligence/tests/test_forensic_agent_core.py` (15 tests)
  - `python -m pytest real_estate_intelligence/tests/test_forensic_agent_wave1a2a.py` (6 tests)
  - `python -m pytest real_estate_intelligence/tests/test_forensic_agent_wave1a2b.py` (5 tests)
  - `python -m pytest real_estate_intelligence/tests/test_fastapi_server.py` (46 tests)
  - Full suite: `.venv\Scripts\pytest real_estate_intelligence/tests -q`
