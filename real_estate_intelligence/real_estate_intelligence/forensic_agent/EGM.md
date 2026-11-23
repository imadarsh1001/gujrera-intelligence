# forensic_agent — Sovereign LangGraph Forensic Due-Diligence Agent

## Overview
The `forensic_agent` package provides an institutional-grade, LangGraph-orchestrated forensic due-diligence agent loop for the Gujarat Real Estate Regulatory Authority (GujRERA) platform. Built on `langgraph>=1.2` and `ag-ui-langgraph>=0.0.48`, it executes multi-turn conversational diligence, tool calling against analytical fact bases, rigorous evidentiary verification, and real-time streaming to the `/analyst` workbench.

> [!NOTE]
> Legacy `agent/copilot.py` and `POST /api/copilot` are preserved untouched for dashboard backward compatibility. However, the legacy `_deterministic_fallback` regex pattern in `copilot.py` is identified as a known brittle implementation and is strictly **not reused** in this package; the forensic agent implements deterministic evidentiary resolution strictly backed by verified live tool executions and candidate disambiguation.
>
> **Security Notice (Wave 1A-1.5):** Direct user prompt injection is screened by `input_guardrail` and routed to a dedicated refusal step. Indirect prompt injection inside untrusted third-party tool and filing outputs will be scoped in Wave 1A-2.

## Interface
- `ForensicAgentState` — TypedDict state schema enforcing plain-JSON serializability (`messages`, `draft_answer`, `retry_feedback`, `active_project_id`, `canvas_mode`, `highlight_pins`, `active_cluster`, `tool_evidence`, `tool_call_count`, `retry_count`, `guardrail_flags`, `verification_passed`, `offline_mode`) [state.py:ForensicAgentState]
- `create_forensic_graph(tools, checkpointer=None, llm=None, offline_mode=False, con=None, recursion_limit=25)` — Compiles the five-node state graph: `input_guardrail` -> `investigator` <-> `tools` -> `citation_verifier` -> `deliver_answer` -> `END` [graph.py:create_forensic_graph]
- `build_forensic_tools(db_path_or_conn=None)` — Factory returning `(tools_list, teardown_callback)` with per-request `read_only=True` SQLite connection isolation and 6,000-token envelopes [tools.py:build_forensic_tools]
- `get_llm(llm_override=None, model_name=None, temperature=0.0)` — Cloudflare AI Gateway REST client factory with Guardrails error code (2016/2017) handling and automatic `offline_mode=True` fallback [llm_gateway.py:get_llm]
- `run_input_guardrail(state)` — Turn initialization resetting per-turn deliberation and counters while preserving conversation-level context [guardrails.py:run_input_guardrail]
- `verify_evidentiary_output(draft_text, tool_evidence)` — Synchronous citation verifier enforcing `[pid:<id>]` and project-bound `[bu:<doc_id>@<pid>]` markers against current turn evidence and rejecting uningested compliance claims [guardrails.py:verify_evidentiary_output]

## Invariants
- Zero unverified draft token leaks: `investigator` writes completed prose only to `draft_answer` in state (never appending to `messages`). Only `deliver_answer` appends verified, scrubbed prose to `messages`.
- Turn tool call ceiling: Hard-capped at 6 tool calls per turn to prevent runaway execution loops or API budget depletion.
- Single verification retry: If citations fail, `citation_verifier` sets `retry_feedback` and retries `investigator` exactly once; persistent failures or offline runs strip/flag invalid citations with a compliance notice.
- Strict read-only database isolation: Factory opens isolated `read_only=True` SQLite connections (`mode=ro`), ensuring zero write locks or mtime changes on `data/intelligence.sqlite`.
- Messagepack compatibility: Graph state uses standard Python primitives, lists, dicts, and `BaseMessage` reducers, guaranteeing clean deserialization under `LANGGRAPH_STRICT_MSGPACK=true`.

## Side Effects
- Opens a lightweight read-only SQLite connection per request, cleanly closed in `finally:` via the tool teardown callback.
- Emits real-time AG-UI SSE protocol events (`RunStarted`, `TextMessageStart/Content/End`, `ToolCallStart/Args/End/Result`, `StateSnapshot`, `StateDelta`, `MessagesSnapshot`, `RunFinished`).
- When `ENABLE_FORENSIC_AGENT` is not `"1"`/`"true"`, `POST /api/agent` returns HTTP `503`.

## Verification
- Test suite:
  - `python -m pytest real_estate_intelligence/tests/test_forensic_agent_core.py`
  - `python -m pytest real_estate_intelligence/tests/test_fastapi_server.py`
