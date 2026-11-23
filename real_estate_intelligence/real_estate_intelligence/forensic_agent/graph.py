"""LangGraph Forensic Agent Workflow & Deliberation Loop.

Constructs the state graph:
input_guardrail -> investigator <-> tools -> citation_verifier -> deliver_answer -> END

Key Invariants:
1. Zero unverified draft tokens leak to the wire:
   - When investigator emits tool calls, empty-content AIMessage is appended to messages.
   - When investigator finishes draft prose, it is stored in draft_answer (NEVER in messages).
   - Only deliver_answer appends verified, scrubbed prose to messages.
2. Max 6 tool calls per turn to prevent runaway loops.
3. Citation verifier triggers a single retry via retry_feedback if citations fail.
4. Deterministic offline_mode resolution with live tool execution and candidate disambiguation.
"""

import json
import re
import sqlite3
import uuid
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from langchain_core.callbacks.manager import dispatch_custom_event
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .guardrails import (
    BU_CITATION_REGEX,
    PID_CITATION_REGEX,
    _scrub_text,
    run_input_guardrail,
    verify_evidentiary_output,
)
from .state import ForensicAgentState, PublicAgentState, PublicInputState
from ..db.queries import get_project_truth_flags


FORENSIC_SYSTEM_PROMPT = """You are the Sovereign GujRERA Real Estate Forensic Intelligence Analyst.
Your mandate is institutional-grade due diligence, forensic escrow auditing, and ground-truth verification.

STRICT CITATION RULES:
1. When referring to any Gujarat RERA project, you MUST cite it using the explicit marker [pid:<id>] (e.g. [pid:9036]).
2. When citing a verified Building Use (BU) certificate, you MUST use the project-bound marker [bu:<numeric_doc_id>@<pid>] (e.g. [bu:4095612@9036]).
3. NEVER cite a BU certificate doc ID without verifying that the queried project actually owns it (no cross-project or fabricated citations).
4. If a project has non-numeric placeholder values (e.g. 'BU-VERIFIED') or partial BU, do NOT cite a [bu:...] doc ID; state the status badge plainly.
5. If an audit report contains SKIPPED_UNINGESTED statutory filings, you are FORBIDDEN from claiming the project is 'clean' or 'fully compliant'. State clearly that disclosures are uningested under the statewide core tier.
6. Provide factual, quantitative, and concise forensic evaluations."""


def create_forensic_graph(
    tools: Sequence[Any],
    checkpointer: Optional[Any] = None,
    llm: Optional[Any] = None,
    offline_mode: bool = False,
    con: Optional[sqlite3.Connection] = None,
    recursion_limit: int = 25,
) -> CompiledStateGraph:
    """Build and compile the sovereign forensic LangGraph workflow."""
    tool_map = {t.name: t for t in tools}

    # Node 1: Input Guardrail
    def input_guardrail_node(state: ForensicAgentState) -> Dict[str, Any]:
        return run_input_guardrail(state)

    # Dedicated Refusal Node for Prompt Injection Attempts
    def refusal_node(state: ForensicAgentState, config: RunnableConfig) -> Dict[str, Any]:
        refusal_msg = (
            "Security Notice: System prompt override or policy circumvention attempt detected. "
            "Forensic due diligence queries must adhere strictly to statutory Gujarat RERA regulatory context."
        )
        message_id = f"msg_{uuid.uuid4().hex}"
        dispatch_custom_event(
            "manually_emit_message",
            {"message_id": message_id, "message": refusal_msg, "role": "assistant"},
            config=config,
        )
        return {
            "messages": [AIMessage(id=message_id, content=refusal_msg)],
            "verification_passed": True,
        }

    # Conditional routing from input guardrail
    def route_guardrail(state: ForensicAgentState) -> str:
        if "PROMPT_INJECTION_DETECTED" in state.get("guardrail_flags", []):
            return "refusal"
        return "investigator"

    # Node 2: Investigator (deliberation & draft generation)
    def investigator_node(state: ForensicAgentState) -> Dict[str, Any]:
        is_offline = state.get("offline_mode", False) or offline_mode or (llm is None)
        if is_offline:
            return _resolve_offline_turn(state, tool_map, con)

        # Online LLM path
        bound_llm = llm.bind_tools(tools)
        system_content = FORENSIC_SYSTEM_PROMPT
        retry_fb = state.get("retry_feedback")
        if retry_fb:
            system_content += f"\n\n[VERIFIER REJECTION NOTICE - CORRECTION REQUIRED]:\n{retry_fb}\nYou must correct your citations or withdraw unverified claims."

        prompt_messages: List[BaseMessage] = [SystemMessage(content=system_content)]
        prompt_messages.extend(state.get("messages", []))

        # Pass emit-messages: False so draft tokens never stream live over SSE
        response = bound_llm.invoke(prompt_messages, config={"metadata": {"emit-messages": False}})

        # Check for tool invocations
        if hasattr(response, "tool_calls") and response.tool_calls:
            current_call_count = state.get("tool_call_count", 0)
            remaining = max(0, 6 - current_call_count)
            if remaining == 0:
                # Cap reached: stop tool execution and produce final draft
                draft = (
                    f"Forensic investigation reached turn tool invocation limit (6). "
                    f"Summary based on gathered evidence: {response.content or 'Analysis complete.'}"
                )
                return {"draft_answer": draft}

            tool_calls = response.tool_calls
            if len(tool_calls) > remaining:
                tool_calls = tool_calls[:remaining]

            # Append tool-call AIMessage with trimmed tool_calls and EMPTY content so no unverified tokens stream
            return {"messages": [AIMessage(content="", tool_calls=tool_calls)]}

        # Final prose produced: write ONLY to draft_answer (NEVER to messages)
        return {"draft_answer": str(response.content or "")}

    # Conditional routing from investigator
    def route_investigator(state: ForensicAgentState) -> str:
        if state.get("draft_answer"):
            return "citation_verifier"
        msgs = state.get("messages", [])
        if msgs:
            last_msg = msgs[-1]
            if isinstance(last_msg, AIMessage) and getattr(last_msg, "tool_calls", None):
                return "tools"
        return "citation_verifier"

    # Node 3: Tools execution
    def tools_node(state: ForensicAgentState) -> Dict[str, Any]:
        msgs = state.get("messages", [])
        if not msgs or not isinstance(msgs[-1], AIMessage):
            return {}

        last_ai = msgs[-1]
        tool_calls = getattr(last_ai, "tool_calls", []) or []

        tool_messages: List[ToolMessage] = []
        tool_evidence = dict(state.get("tool_evidence") or {})
        active_pid = state.get("active_project_id")
        canvas_mode = state.get("canvas_mode")

        for tc in tool_calls:
            t_name = tc.get("name")
            t_args = tc.get("args") or {}
            tc_id = tc.get("id")

            t_fn = tool_map.get(t_name)
            if t_fn:
                try:
                    res = t_fn.invoke(t_args)
                except Exception as e:
                    res = {"error": str(e)}
            else:
                res = {"error": f"Tool '{t_name}' not found"}

            content_str = json.dumps(res) if not isinstance(res, str) else res
            tool_messages.append(ToolMessage(content=content_str, tool_call_id=tc_id, name=t_name))

            # Track evidence and project context
            pid = t_args.get("project_id")
            if pid is not None:
                try:
                    active_pid = int(pid)
                except Exception:
                    pass

            # Digest evidence from tool output
            if isinstance(res, dict) and "data" in res:
                pids = res.get("provenance", {}).get("query_project_ids") or ([active_pid] if active_pid else [])
                data = res.get("data")
                for p in pids:
                    p_str = str(p)
                    ev = tool_evidence.setdefault(p_str, {})
                    if isinstance(data, dict):
                        if "truth_flags" in data:
                            ev["truth_flags"] = data["truth_flags"]
                        if "has_skipped_uningested" in data:
                            ev["has_skipped_uningested"] = data["has_skipped_uningested"]
                        if "dossier_markdown" in data:
                            ev["dossier"] = data["dossier_markdown"]
                    elif isinstance(data, list) and t_name == "compare_projects":
                        for item in data:
                            if isinstance(item, dict) and item.get("project_id") == p:
                                ev["truth_flags"] = item.get("truth_flags")

            # Determine canvas mode
            if t_name == "get_project_dossier":
                canvas_mode = "dossier"
            elif t_name == "audit_discrepancies":
                canvas_mode = "audit"
            elif t_name in ("get_spatial_pricing_benchmark", "verify_sales_claim"):
                canvas_mode = "pricing"
            elif t_name == "trace_entity_network":
                canvas_mode = "network"
            elif t_name == "compare_projects":
                canvas_mode = "comparison"
            elif t_name == "search_projects" and not canvas_mode:
                canvas_mode = "search"

        updated_count = state.get("tool_call_count", 0) + len(tool_calls)
        return {
            "messages": tool_messages,
            "tool_evidence": tool_evidence,
            "active_project_id": active_pid,
            "canvas_mode": canvas_mode,
            "tool_call_count": updated_count,
        }

    # Node 4: Citation Verifier
    def citation_verifier_node(state: ForensicAgentState) -> Dict[str, Any]:
        draft = state.get("draft_answer", "")
        tool_evidence = state.get("tool_evidence", {})
        is_valid, reason, sanitized = verify_evidentiary_output(draft, tool_evidence)

        if is_valid:
            return {"verification_passed": True, "draft_answer": sanitized, "retry_feedback": ""}

        # Verification failed
        retry_count = state.get("retry_count", 0)
        is_offline = state.get("offline_mode", False) or offline_mode or (llm is None)
        if retry_count < 1 and not is_offline:
            # Trigger one retry loop through investigator
            return {
                "verification_passed": False,
                "retry_count": retry_count + 1,
                "retry_feedback": reason,
                "draft_answer": "",  # Clear draft so investigator generates a new response
            }

        # Exceeded retry limit or in offline mode: sanitize draft and pass to delivery
        return {
            "verification_passed": False,
            "draft_answer": sanitized,
            "retry_feedback": "",
        }

    # Conditional routing from citation verifier
    def route_verifier(state: ForensicAgentState) -> str:
        if not state.get("verification_passed") and state.get("retry_feedback") and state.get("retry_count", 0) <= 1:
            return "investigator"
        return "deliver_answer"

    # Node 5: Deliver Answer (sole point where verified text enters messages and is streamed via custom event)
    def deliver_answer_node(state: ForensicAgentState, config: RunnableConfig) -> Dict[str, Any]:
        verified_text = _scrub_text(state.get("draft_answer", ""))
        message_id = f"msg_{uuid.uuid4().hex}"
        dispatch_custom_event(
            "manually_emit_message",
            {"message_id": message_id, "message": verified_text, "role": "assistant"},
            config=config,
        )
        return {"messages": [AIMessage(id=message_id, content=verified_text)]}

    # Assemble graph
    builder = StateGraph(
        ForensicAgentState,
        input_schema=PublicInputState,
        output_schema=PublicAgentState,
    )
    builder.add_node("input_guardrail", input_guardrail_node)
    builder.add_node("refusal", refusal_node)
    builder.add_node("investigator", investigator_node)
    builder.add_node("tools", tools_node)
    builder.add_node("citation_verifier", citation_verifier_node)
    builder.add_node("deliver_answer", deliver_answer_node)

    builder.set_entry_point("input_guardrail")
    builder.add_conditional_edges("input_guardrail", route_guardrail, {
        "investigator": "investigator",
        "refusal": "refusal",
    })
    builder.add_edge("refusal", END)
    builder.add_conditional_edges("investigator", route_investigator, {
        "tools": "tools",
        "citation_verifier": "citation_verifier",
    })
    builder.add_edge("tools", "investigator")
    builder.add_conditional_edges("citation_verifier", route_verifier, {
        "investigator": "investigator",
        "deliver_answer": "deliver_answer",
    })
    builder.add_edge("deliver_answer", END)

    saver = checkpointer if checkpointer is not None else MemorySaver()
    compiled = builder.compile(checkpointer=saver)
    return compiled


EXPLICIT_PID_REGEX = re.compile(
    r"(?:\[pid:\s*(\d+)\]|\b(?:project|pid)\s+(\d+)\b)",
    re.IGNORECASE,
)
FOLLOW_UP_REGEX = re.compile(
    r"\b(this project|its pricing|same project|the project|its status|its bu|its certificate|its audit|this scheme)\b",
    re.IGNORECASE,
)
OFFLINE_STOPWORDS = {
    "is", "in", "for", "the", "a", "an", "at", "to", "of", "and", "or",
    "fair", "rate", "price", "pricing", "project", "audit", "inspect",
    "dossier", "bu", "certificate", "building", "use", "status", "tell",
    "me", "about", "what", "how", "much", "does", "cost", "verify",
    "claim", "claims", "sales", "this", "its", "same",
}


def _extract_name_candidates(query: str) -> List[str]:
    """Extract candidate project names from 4 words down to 1, stripping numbers and stopwords."""
    q_no_nums = re.sub(r"\b\d+(?:,\d+)*(?:\.\d+)?\b", " ", query)
    q_clean = re.sub(r"[^\w\s]", " ", q_no_nums)
    words = [w for w in q_clean.split() if w.lower() not in OFFLINE_STOPWORDS]
    candidates: List[str] = []
    n = len(words)
    for length in range(min(4, n), 0, -1):
        for i in range(n - length + 1):
            candidates.append(" ".join(words[i : i + length]))
    return candidates


def _resolve_offline_turn(
    state: ForensicAgentState,
    tool_map: Dict[str, Any],
    con: Optional[sqlite3.Connection],
) -> Dict[str, Any]:
    """Execute deterministic evidentiary resolution without calling an LLM."""
    msgs = state.get("messages", [])
    user_query = ""
    for m in reversed(msgs):
        if isinstance(m, HumanMessage):
            user_query = str(m.content or "")
            break

    tool_evidence = dict(state.get("tool_evidence") or {})
    active_pid = state.get("active_project_id")

    # (a) Explicit [pid:N] or phrases like 'project 9036' / 'pid 9036'
    target_pid: Optional[int] = None
    pid_match = EXPLICIT_PID_REGEX.search(user_query)
    if pid_match:
        target_pid = int(pid_match.group(1) or pid_match.group(2))

    # (b) Lightweight name extraction from 4 words down to 1
    if target_pid is None and "search_projects" in tool_map and user_query.strip():
        name_candidates = _extract_name_candidates(user_query)
        search_fn = tool_map["search_projects"]
        for candidate in name_candidates:
            if len(candidate.strip()) < 2:
                continue
            search_res = search_fn.invoke({"query": candidate.strip(), "limit": 5})
            data = search_res.get("data", []) if isinstance(search_res, dict) else []
            if 1 <= len(data) <= 5:
                if len(data) > 1:
                    # Record candidate evidence with honest name only (never fabricate truth_flags)
                    for p in data[:5]:
                        pid_s = str(p["project_id"])
                        tool_evidence[pid_s] = {"name": p.get("name")}
                    candidates = [
                        f"- [pid:{p['project_id']}] {p.get('name', 'Unknown')} ({p.get('district', '')})"
                        for p in data[:5]
                    ]
                    return {
                        "draft_answer": (
                            f"Multiple projects matched '{candidate}':\n"
                            + "\n".join(candidates)
                            + "\nPlease specify which project [pid:<id>] you would like to inspect."
                        ),
                        "offline_mode": True,
                        "canvas_mode": "search",
                        "tool_evidence": tool_evidence,
                    }
                # Exactly 1 match found
                target_pid = int(data[0]["project_id"])
                break

    # (c) Fall back to active_project_id ONLY for explicit follow-ups
    if target_pid is None:
        if active_pid and FOLLOW_UP_REGEX.search(user_query):
            target_pid = active_pid

    if target_pid is None:
        if user_query.strip():
            return {
                "draft_answer": f"No Gujarat RERA projects matching '{user_query}' were found in the statutory registry. Please provide a valid project name or RERA ID.",
                "offline_mode": True,
            }
        return {
            "draft_answer": "Please specify a Gujarat RERA project name or ID [pid:<id>] to begin forensic due diligence.",
            "offline_mode": True,
        }

    # 3. Target PID resolved: invoke tools to gather evidentiary proof
    active_pid = target_pid
    p_str = str(active_pid)
    ev = tool_evidence.setdefault(p_str, {})

    # Fetch truth flags directly or via dossier
    if "get_project_dossier" in tool_map:
        dossier_res = tool_map["get_project_dossier"].invoke({"project_id": active_pid})
        if isinstance(dossier_res, dict) and "data" in dossier_res:
            d_data = dossier_res["data"]
            if isinstance(d_data, dict):
                ev["truth_flags"] = d_data.get("truth_flags")
                ev["dossier"] = d_data.get("dossier_markdown")

    if "audit_discrepancies" in tool_map:
        audit_res = tool_map["audit_discrepancies"].invoke({"project_id": active_pid})
        if isinstance(audit_res, dict) and "data" in audit_res:
            a_data = audit_res["data"]
            if isinstance(a_data, dict):
                ev["has_skipped_uningested"] = a_data.get("has_skipped_uningested", False)
                ev["discrepancies"] = a_data.get("discrepancies", [])

    tf = ev.get("truth_flags")
    if not tf and con is not None:
        tf = get_project_truth_flags(con, active_pid)
        ev["truth_flags"] = tf

    tf = tf or {}
    badge = tf.get("status_badge", "REGISTERED")
    data_tier = tf.get("data_tier", "statewide_core")
    bu_cert = tf.get("bu_certificate_no")
    bu_ev = tf.get("bu_evidence")
    has_skipped = ev.get("has_skipped_uningested", False)

    lines = [
        f"### Forensic Intelligence Summary: [pid:{active_pid}]",
        f"- **Project ID**: [pid:{active_pid}]",
        f"- **Data Tier**: `{data_tier}`",
        f"- **Status Badge**: {badge}",
    ]

    if bu_cert and bu_ev == "doc_id":
        lines.append(f"- **Building Use (BU) Certificate**: Verified Document ID [bu:{bu_cert}@{active_pid}]")
    elif bu_ev == "verified_flag":
        lines.append("- **Building Use (BU) Certificate**: Verified by regulatory authority flag (numeric certificate document ID not published).")
    elif tf.get("bu_status") == "partial":
        lines.append(f"- **Building Use (BU) Certificate**: Partial BU granted ({tf.get('bu_blocks_granted')}/{tf.get('bu_blocks_total')} blocks).")
    else:
        lines.append("- **Building Use (BU) Certificate**: None / Not granted.")

    if has_skipped or data_tier == "statewide_core":
        lines.append("- **Statutory Disclosure Status**: Form 1-5 filing history is uningested or partial under statewide core tier.")
    else:
        lines.append("- **Statutory Disclosure Status**: Full statutory Form 1-5 filings ingested and audited.")

    draft_prose = "\n".join(lines)
    return {
        "draft_answer": draft_prose,
        "active_project_id": active_pid,
        "canvas_mode": "dossier",
        "tool_evidence": tool_evidence,
        "offline_mode": True,
    }
