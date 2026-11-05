"""Agentic Copilot with Model Context Protocol (MCP) Tool Calling.

Enables deep, open-ended conversational reasoning over GujRERA statutory filings,
quantitative GBDT/SHAP ML models, Cox survival delay forecasting, and relational
escrow audits using Gemini 2.0 Flash / OpenAI tool calling with zero hallucination.
"""

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

GEMINI_TOOLS = [
    {
        "name": "get_escrow_health",
        "description": "Audit Section 4(2)(l)(D) 70% retention escrow vs 100% collection accounts, closing balances, and Form 3 consideration received vs remaining receivables.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "project_id": {"type": "INTEGER", "description": "The GujRERA project registration ID (e.g. 16562)."}
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "forecast_completion_delay",
        "description": "Forecast project handover completion dates and delay probability percentiles (p50 median, p75 conservative, p90 high confidence) via Cox survival analysis.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "project_id": {"type": "INTEGER", "description": "The GujRERA project registration ID."}
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "predict_pricing_benchmark",
        "description": "Predict fair market valuation per sq.ft and explain exact Tree SHAP feature attributions (premiums/discounts) using the Hedonic GBDT ML model.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "project_id": {"type": "INTEGER", "description": "The GujRERA project registration ID."},
                "asset_class": {"type": "STRING", "description": "Residential, Commercial_Office, Commercial_Retail, or Industrial_Warehouse"},
                "carpet_area_sqft": {"type": "NUMBER", "description": "Unit carpet area in sq.ft (e.g. 1200.0)"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "audit_discrepancies",
        "description": "Run forensic discrepancy checks: cost estimate drops, construction velocity lag, missing BU permissions, active consumer complaints, and quarterly defaults.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "project_id": {"type": "INTEGER", "description": "The GujRERA project registration ID."}
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "query_inventory_breakdown",
        "description": "Query block-level inventory counts, booked vs unbooked units, absorption rate percentage, and commercial vs residential mix.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "project_id": {"type": "INTEGER", "description": "The GujRERA project registration ID."}
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "trace_entity_network",
        "description": "Trace developer network, certified professionals (architect, engineer, CA), cross-project sister schemes, and contagion risk from stalled projects.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "project_id": {"type": "INTEGER", "description": "The GujRERA project registration ID."}
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "calculate_escrow_runway",
        "description": "Calculate monthly construction spend velocity, 70% escrow cash burn rate, remaining cash runway in months, and insolvency risk.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "project_id": {"type": "INTEGER", "description": "The GujRERA project registration ID."}
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "get_land_records",
        "description": "Retrieve town planning scheme, final plot number, revenue survey numbers, GPS coordinates, and municipal block BU clearance permissions.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "project_id": {"type": "INTEGER", "description": "The GujRERA project registration ID."}
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "search_document_evidence",
        "description": "Perform hybrid full-text search with BM25 ranking across sworn Form 1, Form 2, and Form 3 PDF document clauses.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Search query keywords (e.g. 'title certificate', 'mortgage', 'encumbrance')"},
                "project_id": {"type": "INTEGER", "description": "Optional project ID filter."},
                "limit": {"type": "INTEGER", "description": "Max results to return (default 5)."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_project_dossier",
        "description": "Generate a comprehensive 4-quadrant executive diligence dossier summarizing master facts, physical velocity, escrow compliance, and regulatory radar.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "project_id": {"type": "INTEGER", "description": "The GujRERA project registration ID."}
            },
            "required": ["project_id"],
        },
    },
]

OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": {
                "type": "object",
                "properties": {
                    k: {
                        "type": v["type"].lower() if v["type"] != "NUMBER" else "number",
                        "description": v["description"]
                    }
                    for k, v in t["parameters"]["properties"].items()
                },
                "required": t["parameters"]["required"]
            }
        }
    }
    for t in GEMINI_TOOLS
]

SYSTEM_PROMPT = """You are the GujRERA Statutory Due-Diligence Copilot, a forensic real estate diligence specialist.
Your mission is to protect home buyers, real estate investors, and institutional lenders from developer fraud, construction delays, escrow siphoning (RERA Section 4(2)(l)(D)), hidden mortgages, and false marketing claims.

CRITICAL INSTRUCTIONS:
1. ALWAYS call the provided forensic tools to look up real numbers, dates, escrow balances, and statutory disclosures. NEVER guess or hallucinate any facts.
2. Synthesize clear, decisive, executive-ready answers in Markdown with bullet points and bold highlights.
3. If asked for advice (e.g. 'is it safe to buy?', 'what are the risks?', 'real price'), cross-examine:
   - Certified physical progress vs elapsed calendar schedule (velocity ratio).
   - Handover completion forecast (Cox survival p50 expected date).
   - Escrow 70% retention fund compliance and monthly cash runway.
   - Land title clearances, mortgages, and active consumer complaints.
4. Conclude every response with concrete statutory recommendations or next steps for the buyer/investor.
5. All financial amounts in Indian Rupees (₹ Lakhs or ₹ Crores).
"""


class AgenticCopilot:
    """Executes multi-turn agentic tool calling over local MCP tools."""

    def __init__(self, mcp_server):
        self.mcp = mcp_server

    def dispatch_tool(self, name: str, args: Dict[str, Any]) -> Any:
        """Route tool invocation to local MCP server instance with safe argument filtering and coercion."""
        func = getattr(self.mcp, name, None)
        if not func:
            return {"error": f"Tool '{name}' not found."}
        try:
            import inspect
            sig = inspect.signature(func)
            filtered_args = {}
            for param_name in sig.parameters.keys():
                if param_name in args:
                    val = args[param_name]
                    if param_name == "project_id" and val is not None:
                        try:
                            val = int(val)
                        except (ValueError, TypeError):
                            pass
                    elif param_name in ("carpet_area_sqft", "radius_km") and val is not None:
                        try:
                            val = float(val)
                        except (ValueError, TypeError):
                            pass
                    elif param_name == "limit" and val is not None:
                        try:
                            val = int(val)
                        except (ValueError, TypeError):
                            pass
                    filtered_args[param_name] = val
            return func(**filtered_args)
        except Exception as e:
            logger.warning(f"Error executing tool {name} with args {args}: {e}")
            return {"error": str(e)}

    def run_query(
        self,
        query: str,
        project_id: int,
        api_key: Optional[str] = None,
        provider: str = "gemini",
        max_turns: int = 4
    ) -> Optional[Dict[str, Any]]:
        """Run tool-calling loop using Gemini 2.0 Flash or OpenAI API.

        Returns:
            Dict with keys 'reply', 'citations', 'mode': 'agentic_llm', or None if unavailable.
        """
        key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            # Check OpenAI key fallback
            openai_key = api_key if (api_key and api_key.startswith("sk-")) else os.environ.get("OPENAI_API_KEY")
            if openai_key:
                return self._run_openai_loop(query, project_id, openai_key, max_turns=max_turns)
            return None

        return self._run_gemini_loop(query, project_id, key, max_turns=max_turns)

    def _run_gemini_loop(
        self, query: str, project_id: int, api_key: str, max_turns: int = 4
    ) -> Optional[Dict[str, Any]]:
        """Multi-turn Gemini 2.0 Flash function-calling execution loop."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

        user_content = f"The user is evaluating GujRERA Project ID {project_id}.\nUser Question: {query}"
        contents: List[Dict[str, Any]] = [
            {"role": "user", "parts": [{"text": user_content}]}
        ]

        tools_invoked = set()

        for turn in range(max_turns):
            payload = {
                "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": contents,
                "tools": [{"functionDeclarations": GEMINI_TOOLS}],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 2048
                }
            }

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                logger.error(f"Gemini API request error on turn {turn}: {e}")
                return None

            candidates = res_data.get("candidates", [])
            if not candidates:
                return None

            cand = candidates[0]
            parts = cand.get("content", {}).get("parts", [])

            # Check if model called any functions
            function_calls = [p["functionCall"] for p in parts if "functionCall" in p]

            if not function_calls:
                # Model returned final answer text
                final_text = "".join(p.get("text", "") for p in parts).strip()
                if not final_text:
                    return None

                citations = [
                    f"Tool: {t}" for t in tools_invoked
                ] or ["GujRERA Statutory Database"]
                return {
                    "reply": final_text,
                    "citations": citations,
                    "mode": "agentic_llm"
                }

            # Append the model's functionCall turn to contents
            contents.append({
                "role": "model",
                "parts": parts
            })

            # Execute all function calls and append functionResponse parts
            response_parts = []
            for fc in function_calls:
                fn_name = fc["name"]
                fn_args = fc.get("args", {})
                # Inject project_id if missing and tool takes project_id
                if "project_id" not in fn_args and fn_name != "search_document_evidence":
                    fn_args["project_id"] = project_id

                tools_invoked.add(fn_name)
                tool_output = self.dispatch_tool(fn_name, fn_args)

                response_parts.append({
                    "functionResponse": {
                        "name": fn_name,
                        "response": {
                            "name": fn_name,
                            "content": tool_output
                        }
                    }
                })

            contents.append({
                "role": "user",
                "parts": response_parts
            })

        return None

    def _run_openai_loop(
        self, query: str, project_id: int, api_key: str, max_turns: int = 4
    ) -> Optional[Dict[str, Any]]:
        """Multi-turn OpenAI / Ollama compatible function-calling execution loop."""
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        url = f"{base_url.rstrip('/')}/chat/completions"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"The user is evaluating GujRERA Project ID {project_id}.\nUser Question: {query}"}
        ]

        tools_invoked = set()

        for turn in range(max_turns):
            payload = {
                "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                "messages": messages,
                "tools": OPENAI_TOOLS,
                "temperature": 0.2
            }

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                },
                method="POST"
            )

            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                logger.error(f"OpenAI API request error on turn {turn}: {e}")
                return None

            choices = res_data.get("choices", [])
            if not choices:
                return None

            msg = choices[0].get("message", {})
            tool_calls = msg.get("tool_calls", [])

            if not tool_calls:
                final_text = (msg.get("content") or "").strip()
                if not final_text:
                    return None
                return {
                    "reply": final_text,
                    "citations": [f"Tool: {t}" for t in tools_invoked] or ["GujRERA Statutory Database"],
                    "mode": "agentic_llm"
                }

            messages.append(msg)

            for tc in tool_calls:
                fn_name = tc["function"]["name"]
                try:
                    fn_args = json.loads(tc["function"]["arguments"])
                except Exception:
                    fn_args = {}

                if "project_id" not in fn_args and fn_name != "search_document_evidence":
                    fn_args["project_id"] = project_id

                tools_invoked.add(fn_name)
                tool_output = self.dispatch_tool(fn_name, fn_args)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(tool_output)
                })

        return None
