# agent — Agentic LLM Copilot with MCP Tool Calling

## Overview
Conversational agent layer that wires an LLM (Gemini 2.0 Flash or an OpenAI-compatible endpoint) to the local MCP tool server (`mcp.server.RealEstateIntelligenceMCP`) via multi-turn function calling. Declares 12 forensic tool schemas (including trailing-4Q pricing and claim verification with `asset_class` parity), dispatches tool calls with argument coercion, and grounds answers in tool output by injecting `project_id` and returning tool citations. Returns `None` when no API key is configured or the API loop fails; the caller then falls back to the deterministic, keyword-routed copilot in the `ui` subsystem.

## Interface
- `GEMINI_TOOLS` — list of 12 Gemini function declarations maintaining 1:1 schema parity with FastMCP tools: `get_escrow_health`, `forecast_completion_delay`, `predict_pricing_benchmark`, `audit_discrepancies`, `query_inventory_breakdown`, `trace_entity_network`, `calculate_escrow_runway`, `get_land_records`, `search_document_evidence`, `get_project_dossier`, `get_pricing_appreciation_trend`, `verify_sales_claim` [copilot.py:GEMINI_TOOLS]
- `OPENAI_TOOLS` — OpenAI `tools` schema derived programmatically from `GEMINI_TOOLS` [copilot.py:OPENAI_TOOLS]
- `SYSTEM_PROMPT` — forensic due-diligence persona instructions (mandatory tool use, markdown answers, INR units) [copilot.py:SYSTEM_PROMPT]
- `AgenticCopilot(mcp_server)` with `dispatch_tool(name, args)` and `run_query(query, project_id, api_key=None, provider="gemini", max_turns=4) -> Optional[Dict]` [copilot.py:AgenticCopilot]
- `handle_copilot_query(...)` — unified gateway handling agentic LLM routing with deterministic local keyword fallback [copilot.py:handle_copilot_query]

## Invariants
- 1:1 Schema Parity: `verify_sales_claim` and `get_pricing_appreciation_trend` schemas explicitly declare optional `asset_class: "Residential" | "Commercial" | "All"` [copilot.py:GEMINI_TOOLS], [copilot.py:OPENAI_TOOLS]
- `run_query` returns `None` (never raises) when no key is resolvable or the LLM loop fails; on success it returns `{"reply": str, "citations": List[str], "mode": "agentic_llm"}` [copilot.py:run_query]
- Key resolution order: explicit `api_key` arg, else env `GEMINI_API_KEY`, else env `GOOGLE_API_KEY` — whichever resolves first drives the Gemini loop [copilot.py:run_query]
- OpenAI loop fallback: runs only when no Gemini key resolves and env `OPENAI_API_KEY` is present [copilot.py:run_query]
- Coercion and Security: arguments pass through `inspect.signature` validation, and responses are sanitized against PII leakage [copilot.py:dispatch_tool]

## Side Effects
- Outbound HTTPS POST calls to the Gemini or OpenAI chat-completions API using `urllib.request` [copilot.py:_run_gemini_loop], [copilot.py:_run_openai_loop]
- Reads environment variables `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` [copilot.py:run_query]
- Executes read-only MCP methods on the shared SQLite database [copilot.py:dispatch_tool]

## Verification
- Run test suites:
  - `python -m pytest real_estate_intelligence/tests/test_agent_copilot.py`
  - `python -m pytest real_estate_intelligence/tests/test_phase1_5_polish.py`
