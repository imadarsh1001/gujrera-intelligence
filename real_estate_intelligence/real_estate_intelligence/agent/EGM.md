# agent — Agentic LLM Copilot with MCP Tool Calling

## Overview
Conversational agent layer that wires an LLM (Gemini 2.0 Flash or an OpenAI-compatible endpoint) to the local MCP tool server (`mcp.server.RealEstateIntelligenceMCP`) via multi-turn function calling. Declares 10 forensic tool schemas, dispatches tool calls with argument coercion, and grounds answers in tool output by injecting `project_id` and returning tool citations. Returns `None` when no API key is configured or the API loop fails; the caller then falls back to the deterministic, keyword-routed copilot in the `ui` subsystem (see [../ui/EGM.md]).

## Interface
- `GEMINI_TOOLS` — list of 10 Gemini function declarations: `get_escrow_health`, `forecast_completion_delay`, `predict_pricing_benchmark`, `audit_discrepancies`, `query_inventory_breakdown`, `trace_entity_network`, `calculate_escrow_runway`, `get_land_records`, `search_document_evidence`, `get_project_dossier` [copilot.py:GEMINI_TOOLS]
- `OPENAI_TOOLS` — OpenAI `tools` schema derived programmatically from `GEMINI_TOOLS` [copilot.py:OPENAI_TOOLS]
- `SYSTEM_PROMPT` — forensic due-diligence persona instructions (mandatory tool use, markdown answers, INR units) [copilot.py:SYSTEM_PROMPT]
- `AgenticCopilot(mcp_server)` with `dispatch_tool(name, args)` and `run_query(query, project_id, api_key=None, provider="gemini", max_turns=4) -> Optional[Dict]` (`provider` is currently never read — loop selection is driven solely by key resolution; see Invariants) [copilot.py:AgenticCopilot]
- Package export: `AgenticCopilot` [__init__.py:__all__]

## Invariants
- `run_query` returns `None` (never raises) when no key is resolvable or the single selected LLM loop fails; on success it returns exactly `{"reply": str, "citations": List[str], "mode": "agentic_llm"}` [copilot.py:run_query]
- Key resolution order: explicit `api_key` arg, else env `GEMINI_API_KEY`, else env `GOOGLE_API_KEY` — whichever resolves first drives the Gemini loop; an explicit key is never rerouted, so an `sk-`-prefixed key is still sent to the Gemini endpoint [copilot.py:run_query]
- The OpenAI loop runs only when no Gemini-family key resolves at all and env `OPENAI_API_KEY` is set; its key comes from `OPENAI_API_KEY` (the `sk-`-prefix test in the OpenAI fallback is dead code — `api_key` is always falsy by the time that branch runs) [copilot.py:run_query]
- `dispatch_tool` resolves tools by `getattr(self.mcp, name)` (so only real MCP methods are callable), filters arguments to the method's `inspect.signature` parameters, and coerces `project_id`/`limit` to `int` and `carpet_area_sqft`/`radius_km` to `float`; unknown tools return `{"error": ...}` [copilot.py:dispatch_tool]
- `project_id` is injected into every tool call that lacks it, except `search_document_evidence` [copilot.py:_run_gemini_loop], [copilot.py:_run_openai_loop]
- The Gemini endpoint is fixed to `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent` with `temperature=0.2`, `maxOutputTokens=2048`, and a 30-second urllib timeout; the loop runs at most `max_turns` (default 4) [copilot.py:_run_gemini_loop]
- OpenAI loop reads base URL from env `OPENAI_BASE_URL` (default `https://api.openai.com/v1`) and model from env `OPENAI_MODEL` (default `gpt-4o-mini`) [copilot.py:_run_openai_loop]
- If the model returns no text and no tool calls, the loop returns `None` rather than an empty reply [copilot.py:_run_gemini_loop]

## Side Effects
- Outbound HTTPS POST calls to the Gemini or OpenAI chat-completions API using `urllib.request` (network side effect; API key is passed in the URL query string for Gemini and the `Authorization: Bearer` header for OpenAI) [copilot.py:_run_gemini_loop], [copilot.py:_run_openai_loop]
- Reads environment variables `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` [copilot.py:run_query], [copilot.py:_run_openai_loop]
- Tool dispatch executes the MCP server's methods, which read the shared SQLite database (see `../mcp/EGM.md`); the agent itself holds no database connection [copilot.py:dispatch_tool]
- Logs warnings/errors via `logging.getLogger(__name__)` [copilot.py:logger]

## Verification
- Run: `python -m pytest real_estate_intelligence/tests`
