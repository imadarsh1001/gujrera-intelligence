"""LangGraph Hybrid Coordinator & Specialist Map-Reduce Workflow.

Constructs the state graph:
input_guardrail -> coordinator_plan
                -> (fast direct_reply OR parallel Send) -> [due_diligence, pilot_auditor, promoter_contagion, market_analyst]
                -> coordinator_reduce
                -> (optional post-barrier Send) -> [promoter_contagion, pilot_auditor] -> coordinator_reduce
                -> synthesizer -> citation_verifier -> a2ui_emitter -> deliver_answer -> END

Key Invariants:
1. Zero unverified draft tokens leak to the wire:
   - Router & synthesis LLM calls pass emit-messages: False and disable_streaming=True.
   - Verified prose is streamed exclusively by deliver_answer using manually_emit_message with shared message_id.
2. Parallel specialists execute concurrently with per-branch mode=ro SQLite connections and timeout timers.
3. Global budgets enforce max 35 tool calls, max 2 hops, recursion_limit=25, max_concurrency=5.
4. Catch-all fault isolation yields structured partial error findings without crashing the workflow.
5. Server-bound A2UI 1.0 surfaces emitted before deliver_answer.
"""

import json
import logging
import re
import sqlite3
import uuid
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple
from pydantic import BaseModel, Field

from langchain_core.callbacks.manager import dispatch_custom_event
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from .a2ui_surfaces import build_a2ui_surfaces
from .guardrails import (
    _scrub_text,
    run_input_guardrail,
    sanitize_tool_prose,
    verify_evidentiary_output,
)
from .llm_gateway import get_router_llm, get_synthesis_llm
from .playbooks import get_playbook_instructions
from .specialists import (
    due_diligence_specialist,
    market_analyst_specialist,
    pilot_auditor_specialist,
    promoter_contagion_specialist,
)
from .state import ForensicAgentState, PublicAgentState, PublicInputState
from .tools import build_forensic_tools
from ..db.database import DEFAULT_DB_PATH, get_connection
from ..db.queries import get_project_truth_flags, search_project_summaries
from ..graph.network import resolve_promoter_portfolio

logger = logging.getLogger(__name__)

FORENSIC_SYSTEM_PROMPT = """You are the Sovereign GujRERA Real Estate Forensic Intelligence Analyst.
Your mandate is institutional-grade due diligence, forensic escrow auditing, and ground-truth verification.

STRICT CITATION & HONESTY RULES:
1. When referring to any Gujarat RERA project, you MUST cite it using the explicit marker [pid:<id>] (e.g. [pid:9036]).
2. When citing a verified Building Use (BU) certificate, you MUST use the project-bound marker [bu:<numeric_doc_id>@<pid>] (e.g. [bu:4095612@9036]).
3. NEVER cite a BU certificate doc ID without verifying that the queried project actually owns it (no cross-project or fabricated citations).
4. If a project has non-numeric placeholder values (e.g. 'BU-VERIFIED') or partial BU, do NOT cite a [bu:...] doc ID; state the status badge plainly.
5. If a project has data_tier == 'statewide_core' or SKIPPED_UNINGESTED filings, Form 3 / Form 5 / escrow disclosures are UNINGESTED. NEVER make unqualified assurances like 'no evidence of fund diversion', 'no fund diversion', 'no escrow issues', 'financially clean', or 'fully compliant' without explicitly stating in the same sentence that disclosures are SKIPPED_UNINGESTED / uningested / cannot confirm.
6. NEVER substitute Spatial Micro-Market IQR (SpatialEmpiricalPricer) for a project's own trailing booked benchmark (verify_sales_claim). Label both distinctly when present (e.g. "Project Trailing Booked Benchmark" vs "Micro-Market Spatial IQR"), and omit any claim verdict if verify_sales_claim did not run.
7. When citing macro market aggregates computed by market_analyst, use the exact marker [agg:<id>] matching gathered aggregate keys (e.g. [agg:screen_count], [agg:district_median_price], [agg:avg_absorption_pct], [agg:markup_spread_pct], [agg:zombie_count]).
8. For general Gujarat RERA Q&A with no queried project/market tools, do NOT fabricate [pid:...], [bu:...], or [agg:...] citations.
9. Provide factual, quantitative, and concise forensic evaluations."""

ROUTER_SYSTEM_PROMPT = """Classify the Gujarat RERA due-diligence user query into strict JSON only (no markdown, no explanation).
Schema:
{"intent": "greeting|off_topic|general_rera_qa|project_dd|compare|promoter|pilot_audit|market_screen|followup", "project_names": [], "promoter_names": [], "district": null, "claimed_rate": null, "project_type": "Residential", "direct_reply": null}

Rules:
- greeting: hi/hello/help/thanks. Set direct_reply (1-2 sentences).
- off_topic: unrelated to Gujarat real estate, RERA, projects, developers, or pricing. Set polite direct_reply (1-2 sentences).
- general_rera_qa: general questions about RERA law, Section 4(2)(l)(D), Form 1/3/5, BU NOC concepts without asking about a specific scheme/district.
- project_dd: inspecting a project, BU cert, or verifying a price claim on a project.
- compare: comparing 2+ projects.
- promoter: promoter/developer portfolio, sister schemes, cluster split, or contagion.
- pilot_audit: explicit forensic audit, escrow, Form 5, cost drops, or pilot_deep verification.
- market_screen: screening/ranking projects or market stats across a district/type/statewide.
- followup: refers to prior context without naming a new project/district.
- For all data intents (project_dd, compare, promoter, pilot_audit, market_screen), set direct_reply to null."""

_GUJARAT_DISTRICTS = (
    "Ahmedabad", "Surat", "Vadodara", "Rajkot", "Gandhinagar", "Bhavnagar",
    "Valsad", "Anand", "Junagadh", "Jamnagar", "Bharuch", "Kachchh", "Mehsana",
    "Navsari", "Morbi", "Kheda", "Banaskantha", "Sabarkantha", "Panchmahal",
    "Surendranagar", "Amreli", "Porbandar", "Dahod", "Narmada", "Tapi",
    "Dang", "Botad", "Chhotaudepur", "Devbhumi Dwarka", "Gir Somnath",
    "Mahisagar", "Aravalli", "Patan",
)
_YEARS_TO_IGNORE = {str(y) for y in range(2000, 2035)}
_BEFORE_PRICE_CUE_RE = re.compile(
    r"(?:₹|rs\.?|inr|rate|price|quoted|asking|claims?|costs?)\s*(?:is|of|at|around|about)?\s*(?:\S+\s+){0,2}$",
    re.IGNORECASE,
)
_AFTER_PRICE_CUE_RE = re.compile(
    r"^\s*(?:\S+\s+){0,2}(?:per\s*sq\.?\s*ft|/\s*sq\.?\s*ft|sq\.?\s*ft|sqft|rs\.?|inr|₹|fair|rate|price)\b",
    re.IGNORECASE,
)
_EXPLICIT_PID_RE = re.compile(r"\[pid:(\d+)\]|(?:project|scheme|id)\s*#?\s*(\d{4,6})\b", re.IGNORECASE)
_GREETING_RE = re.compile(
    r"^\s*(?:hi|hello|hey|help|namaste|good\s+(?:morning|afternoon|evening))[!.\s?]*$",
    re.IGNORECASE,
)


class RouterDecision(BaseModel):
    """Strict JSON schema validated for Granite micro semantic router responses."""

    intent: Literal[
        "greeting",
        "off_topic",
        "general_rera_qa",
        "project_dd",
        "compare",
        "promoter",
        "pilot_audit",
        "market_screen",
        "followup",
    ]
    project_names: List[str] = Field(default_factory=list)
    promoter_names: List[str] = Field(default_factory=list)
    district: Optional[str] = None
    claimed_rate: Optional[float] = None
    project_type: Optional[str] = "Residential"
    direct_reply: Optional[str] = None


def _resolve_db_path(con: Optional[sqlite3.Connection], db_path: Optional[Any] = None) -> Any:
    """Extract SQLite database path from connection or fallback to default."""
    if db_path is not None:
        return db_path
    if con is not None:
        try:
            row = con.execute("PRAGMA database_list").fetchone()
            if row and len(row) >= 3 and row[2]:
                return row[2]
        except Exception:
            pass
    return DEFAULT_DB_PATH


def _extract_explicit_pids_and_mask(raw_text: str) -> Tuple[List[int], str]:
    """Extract explicit [pid:N] / project N / scheme N markers and mask their character spans."""
    pids: List[int] = []
    chars = list(raw_text)
    for m in _EXPLICIT_PID_RE.finditer(raw_text):
        pid_val = m.group(1) or m.group(2)
        if pid_val:
            pids.append(int(pid_val))
        for idx in range(m.start(), m.end()):
            chars[idx] = " "
    return pids, "".join(chars)


def _extract_claimed_price_and_mask(masked_text: str, explicit_pids: List[int]) -> Tuple[Optional[float], str]:
    """Extract price-per-sqft claims requiring an adjacent 1-3 word price cue, masking matched numbers."""
    norm_text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", masked_text)
    explicit_set = set(explicit_pids)
    chars = list(norm_text)

    for m in re.finditer(r"\b(\d{4,6})\b", norm_text):
        val_str = m.group(1)
        if val_str in _YEARS_TO_IGNORE:
            continue
        val_int = int(val_str)
        if val_int in explicit_set:
            continue

        left_ctx = norm_text[max(0, m.start() - 48) : m.start()]
        right_ctx = norm_text[m.end() : min(len(norm_text), m.end() + 48)]
        if _BEFORE_PRICE_CUE_RE.search(left_ctx) or _AFTER_PRICE_CUE_RE.search(right_ctx):
            for idx in range(m.start(), m.end()):
                chars[idx] = " "
            return float(val_int), "".join(chars)

    return None, norm_text


def _mask_number_in_text(text: str, num_val: float) -> str:
    """Mask literal occurrences of a reconciled router rate so it is not treated as a PID."""
    as_int = str(int(round(num_val)))
    return re.sub(rf"\b{re.escape(as_int)}\b", " ", text)


def _extract_district(text: str) -> Optional[str]:
    """Deterministically detect a Gujarat district name in user text."""
    for d in _GUJARAT_DISTRICTS:
        if re.search(rf"\b{re.escape(d)}\b", text, re.IGNORECASE):
            return d
    return None


def _extract_project_type(text: str) -> Optional[str]:
    """Deterministically extract project asset type if explicitly stated."""
    if re.search(r"\bcommercial\b", text, re.IGNORECASE):
        return "Commercial"
    if re.search(r"\bresidential\b", text, re.IGNORECASE):
        return "Residential"
    if re.search(r"\bmixed\b", text, re.IGNORECASE):
        return "Mixed"
    return None


def _clean_search_phrase(raw_text: str) -> str:
    """Strip common directive words and numeric tokens to isolate project/promoter search terms."""
    clean_q = re.sub(
        r"\b(audit|project|scheme|status|details|report|for|of|the|now|please|check|inspect|building|use|certificate|is|in|fair|genuine|analyze|deal|promoter|developer|portfolio|history|contagion|compare|versus|vs|per|sqft|rate|price|asking|quoted|what|about)\b",
        "",
        raw_text,
        flags=re.IGNORECASE,
    ).strip()
    return re.sub(r"\b\d+\b|[?,!@#$%^&*₹]", "", clean_q).strip()


def _detect_deterministic_intent(raw_text: str, pid_count: int = 0, active_pid: Optional[int] = None) -> str:
    """Deterministic fallback intent classification used for fast-path and offline execution."""
    if _GREETING_RE.match(raw_text):
        return "greeting"
    if re.search(r"\b(promoter|developer|builder|contagion|cluster|portfolio|sister\s+scheme)\b", raw_text, re.IGNORECASE):
        return "promoter"
    if re.search(r"\b(audit|discrepanc|forensic|lead|escrow|form5|form\s*5)\b", raw_text, re.IGNORECASE):
        return "pilot_audit"
    if re.search(
        r"\b(screen|market\s+stats|market\s+overview|top\s+projects|macro|zombie\s+radar|projects\s+in\s+(?:ahmedabad|surat|vadodara|rajkot|gandhinagar|bhavnagar|valsad|anand|junagadh|jamnagar))\b",
        raw_text,
        re.IGNORECASE,
    ):
        return "market_screen"
    if re.search(r"\b(compare|versus|vs)\b", raw_text, re.IGNORECASE) or pid_count > 1:
        return "compare"
    if active_pid is not None and re.search(
        r"\b(what about|how about|and its|its escrow|its bu|more details|tell me more|follow\s*up)\b",
        raw_text,
        re.IGNORECASE,
    ):
        return "followup"
    return "project_dd"


def _invoke_semantic_router(
    router_model: Any,
    raw_text: str,
    active_pid: Optional[int],
) -> Optional[RouterDecision]:
    """Call the semantic router LLM with strict JSON parsing and safe fallback."""
    ctx_hint = f"Current active_project_id: {active_pid}" if active_pid is not None else "Current active_project_id: none"
    messages = [
        SystemMessage(content=ROUTER_SYSTEM_PROMPT),
        HumanMessage(content=f"{ctx_hint}\nUser query: {raw_text}"),
    ]
    try:
        resp = router_model.invoke(messages, config={"metadata": {"emit-messages": False}})
        content = str(getattr(resp, "content", "") or "").strip()
        # Strip optional markdown code fences
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE | re.DOTALL).strip()
        parsed = json.loads(content)
        return RouterDecision.model_validate(parsed)
    except Exception as e:
        logger.debug(f"Semantic router fallback triggered: {e}")
        return None


def _build_disambig_user_message(raw_text: str, pid: int, intent_hint: str, claimed_price: Optional[float]) -> str:
    """Create a clickable follow-up message preserving original user intent and [pid:N]."""
    price_suffix = f" at {int(claimed_price)} per sqft" if claimed_price is not None else ""
    if intent_hint == "pilot_audit":
        return f"Forensic audit for [pid:{pid}]{price_suffix}"
    if intent_hint == "promoter":
        return f"Check promoter history for [pid:{pid}]"
    if claimed_price is not None:
        return f"Analyze [pid:{pid}] and check if {int(claimed_price)} per sqft is fair"
    return f"Analyze project [pid:{pid}]"


def create_forensic_graph(
    tools: Optional[Sequence[Any]] = None,
    checkpointer: Optional[Any] = None,
    llm: Optional[Any] = None,
    router_llm: Optional[Any] = None,
    offline_mode: bool = False,
    con: Optional[sqlite3.Connection] = None,
    db_path: Optional[Any] = None,
    recursion_limit: int = 25,
) -> CompiledStateGraph:
    """Build and compile the sovereign forensic LangGraph workflow."""
    resolved_db_path = _resolve_db_path(con, db_path)

    if tools:
        tool_map = {t.name: t for t in tools}
    else:
        built_tools, _ = build_forensic_tools(con or resolved_db_path)
        tool_map = {t.name: t for t in built_tools}

    resolved_router_llm = router_llm
    if resolved_router_llm is None and not offline_mode and llm is None:
        resolved_router_llm, _ = get_router_llm()

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
        return "coordinator_plan"

    # Node 2: Coordinator Plan (Parse query, optional semantic router, plan tasks)
    def coordinator_plan_node(state: ForensicAgentState) -> Dict[str, Any]:
        messages = state.get("messages", [])
        raw_text = ""
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                raw_text = str(m.content or "")
                break

        active_pid = state.get("active_project_id")
        explicit_pids, masked_text = _extract_explicit_pids_and_mask(raw_text)
        claimed_price, post_price_text = _extract_claimed_price_and_mask(masked_text, explicit_pids)
        has_pid_marker = bool(re.search(r"\[pid:\d+\]", raw_text, re.IGNORECASE))

        # Semantic router (skipped on [pid:N] fast-path, offline mode, or when only fake synthesis llm is injected)
        router_decision: Optional[RouterDecision] = None
        if not has_pid_marker and not offline_mode and resolved_router_llm is not None:
            router_decision = _invoke_semantic_router(resolved_router_llm, raw_text, active_pid)

        # Reconcile claimed_rate from semantic router only if WP0 left it None and literal number appears in text
        if claimed_price is None and router_decision and router_decision.claimed_rate is not None:
            r_rate = float(router_decision.claimed_rate)
            rate_int_str = str(int(round(r_rate)))
            norm_raw = re.sub(r"(?<=\d),(?=\d{3}\b)", "", raw_text)
            if (
                rate_int_str not in _YEARS_TO_IGNORE
                and int(round(r_rate)) not in explicit_pids
                and re.search(rf"\b{re.escape(rate_int_str)}\b", norm_raw)
            ):
                claimed_price = r_rate
                post_price_text = _mask_number_in_text(post_price_text, r_rate)

        raw_numbers = [
            int(n)
            for n in re.findall(r"\b(\d{4,6})\b", re.sub(r"(?<=\d),(?=\d{3}\b)", "", post_price_text))
            if n not in _YEARS_TO_IGNORE
        ]

        # Determine canonical intent
        if has_pid_marker or router_decision is None:
            intent = _detect_deterministic_intent(
                raw_text,
                pid_count=len(explicit_pids) or len(raw_numbers),
                active_pid=active_pid,
            )
        else:
            intent = router_decision.intent

        # 1. Fast direct reply intents (0 DB tools, bypass synthesizer)
        if intent in ("greeting", "off_topic"):
            if router_decision and router_decision.direct_reply:
                reply = _scrub_text(router_decision.direct_reply.strip())
            elif intent == "greeting":
                reply = (
                    "Hello! I am the GujRERA Sovereign Forensic Diligence Analyst. "
                    "Share a project name or [pid:<id>] (e.g., [pid:9036]), a price claim to verify, or a district to screen."
                )
            else:
                reply = (
                    "I focus exclusively on Gujarat RERA statutory due diligence, pricing benchmarks, "
                    "promoter portfolios, and district market screening."
                )
            return {
                "planned_tasks": [],
                "active_specialists": [],
                "dispatched_keys": [],
                "intent": intent,
                "active_playbook": None,
                "draft_answer": reply,
                "verification_passed": True,
            }

        # 2. General RERA Q&A (0 DB tools, routed to synthesizer)
        if intent == "general_rera_qa":
            return {
                "planned_tasks": [],
                "active_specialists": [],
                "dispatched_keys": [],
                "intent": intent,
                "active_playbook": "buyer_due_diligence",
            }

        # 3. Followup resolution
        if intent == "followup":
            if active_pid is None:
                return {
                    "planned_tasks": [],
                    "active_specialists": [],
                    "dispatched_keys": [],
                    "intent": "followup",
                    "active_playbook": None,
                    "draft_answer": (
                        "Which Gujarat RERA project would you like me to analyze? "
                        "Please provide a project name or [pid:<id>] (for example, [pid:9036])."
                    ),
                    "verification_passed": True,
                }
            # Infer specialist for followup on active_pid
            follow_det = _detect_deterministic_intent(raw_text, pid_count=1, active_pid=active_pid)
            intent = follow_det if follow_det in ("promoter", "pilot_audit") else "project_dd"
            target_pids = [int(active_pid)]
            matched_candidates: List[Dict[str, Any]] = []
        else:
            target_pids = []
            matched_candidates = []

        # 4. Market Screening intent (dispatches market_analyst_specialist ONLY)
        if intent == "market_screen":
            district = (router_decision.district if router_decision and router_decision.district else None) or _extract_district(raw_text)
            ptype = _extract_project_type(raw_text) or (router_decision.project_type if router_decision else None)
            task = {
                "specialist": "market_analyst",
                "district": district,
                "project_type": ptype,
                "db_path": resolved_db_path,
            }
            return {
                "planned_tasks": [task],
                "active_project_id": active_pid,
                "active_specialists": ["market_analyst"],
                "dispatched_keys": [f"market:{district or 'all'}:{ptype or 'all'}"],
                "intent": "market_screen",
                "active_playbook": "market_screening_analyst",
            }

        # 5. Promoter Contagion intent
        if intent == "promoter":
            prom_pids = explicit_pids[:10] if explicit_pids else (raw_numbers[:10] if raw_numbers else [])
            prom_name = None
            if router_decision and router_decision.promoter_names:
                prom_name = router_decision.promoter_names[0].strip()
            if not prom_pids and not prom_name:
                cleaned_p = _clean_search_phrase(post_price_text)
                if cleaned_p and len(cleaned_p) >= 3:
                    prom_name = cleaned_p
                elif active_pid is not None:
                    prom_pids = [int(active_pid)]

            planned_tasks: List[Dict[str, Any]] = []
            dispatched_keys: List[str] = []
            for p in prom_pids:
                planned_tasks.append({
                    "specialist": "promoter_contagion",
                    "project_id": p,
                    "promoter_name": prom_name,
                    "db_path": resolved_db_path,
                })
                dispatched_keys.append(f"promoter:pid:{p}")
            if not planned_tasks and prom_name:
                planned_tasks.append({
                    "specialist": "promoter_contagion",
                    "promoter_name": prom_name,
                    "db_path": resolved_db_path,
                })
                dispatched_keys.append(f"promoter:{prom_name.upper()}")

            new_active = prom_pids[0] if prom_pids else active_pid
            return {
                "planned_tasks": planned_tasks,
                "active_project_id": new_active,
                "active_specialists": ["promoter_contagion"] if planned_tasks else [],
                "dispatched_keys": dispatched_keys,
                "intent": "promoter",
                "active_playbook": "buyer_due_diligence",
            }

        # 6. Project Due Diligence / Compare / Pilot Audit
        is_audit = intent in ("pilot_audit", "audit")
        if not target_pids:
            if explicit_pids:
                target_pids = explicit_pids[:10]
            elif len(raw_numbers) > 1 or (intent == "compare" and raw_numbers):
                target_pids = raw_numbers[:10]
            else:
                # Reconcile project_names from router, stripping pure numeric/PID tokens
                search_terms: List[str] = []
                if router_decision and router_decision.project_names:
                    for pn in router_decision.project_names:
                        cleaned_pn = re.sub(r"\[?pid:?\d+\]?", "", str(pn), flags=re.IGNORECASE).strip()
                        if cleaned_pn and not cleaned_pn.isdigit() and len(cleaned_pn) >= 2:
                            search_terms.append(cleaned_pn)
                if not search_terms:
                    fallback_q = _clean_search_phrase(post_price_text)
                    if fallback_q and len(fallback_q) >= 2:
                        search_terms.append(fallback_q)

                if search_terms:
                    read_con = con or get_connection(resolved_db_path, read_only=True)
                    try:
                        if intent == "compare" and len(search_terms) >= 2:
                            for term in search_terms[:10]:
                                hits = search_project_summaries(read_con, q=term, limit=5)
                                if len(hits) == 1 and hits[0].get("match_type") != "fuzzy":
                                    target_pids.append(int(hits[0]["project_id"]))
                                elif hits:
                                    matched_candidates.extend(hits)
                        else:
                            matched_candidates = search_project_summaries(read_con, q=search_terms[0], limit=10)
                    finally:
                        if read_con and read_con != con:
                            read_con.close()

                has_fuzzy = any(c.get("match_type") == "fuzzy" for c in matched_candidates)
                if not target_pids:
                    if len(matched_candidates) == 1 and not has_fuzzy:
                        target_pids = [int(matched_candidates[0]["project_id"])]
                    elif len(matched_candidates) >= 2 or (len(matched_candidates) >= 1 and has_fuzzy):
                        intent = "disambiguation"
                    elif raw_numbers:
                        target_pids = raw_numbers[:10]
                    elif active_pid is not None and re.search(r"\b(it|this|that|above)\b", raw_text, re.IGNORECASE):
                        target_pids = [int(active_pid)]

        # Disambiguation branch: wrap capped candidates in findings & pre-populate tool_evidence for 1-pass verification
        if intent == "disambiguation":
            capped = matched_candidates[:5]
            match_kind = "fuzzy" if any(c.get("match_type") == "fuzzy" for c in capped) else "exact"
            query_label = _clean_search_phrase(post_price_text) or raw_text.strip()
            card_candidates = []
            ev_projects: Dict[str, Dict[str, Any]] = {}
            for c in capped:
                cpid = int(c["project_id"])
                cname = str(c.get("name") or f"Project {cpid}")
                cmatch = "fuzzy" if c.get("match_type") == "fuzzy" else "exact"
                card_candidates.append({
                    "project_id": cpid,
                    "name": cname,
                    "district": c.get("district"),
                    "promoter_name": c.get("promoter_name"),
                    "match_type": cmatch,
                    "user_message": _build_disambig_user_message(raw_text, cpid, "pilot_audit" if is_audit else "project_dd", claimed_price),
                })
                ev_projects[str(cpid)] = {
                    "project_id": cpid,
                    "name": cname,
                    "truth_flags": {"data_tier": "statewide_core"},
                }

            disambig_finding = {
                "specialist": "coordinator_disambiguation",
                "status": "ok",
                "data": {"candidates": card_candidates},
                "card_data": {
                    "disambiguation": {
                        "query": query_label,
                        "match_type": match_kind,
                        "candidates": card_candidates,
                        "allow_other": True,
                        "other_label": "Other (type something else)",
                    }
                },
            }
            return {
                "planned_tasks": [],
                "active_project_id": active_pid,
                "active_specialists": [],
                "dispatched_keys": [],
                "intent": "disambiguation",
                "active_playbook": "buyer_due_diligence",
                "findings": [disambig_finding],
                "tool_evidence": {"projects": ev_projects},
            }

        planned_tasks = []
        dispatched_keys = []
        active_specialists = ["due_diligence"] if target_pids else []
        for pid in target_pids:
            planned_tasks.append({
                "specialist": "due_diligence",
                "project_id": pid,
                "db_path": resolved_db_path,
                "claimed_price": claimed_price,
                "claimed_type": "price_per_sqft",
                "asset_class": "Residential",
                "audit_requested": is_audit,
            })
            dispatched_keys.append(f"dd:{pid}")
            if is_audit:
                dispatched_keys.append(f"pilot:{pid}")
                if "pilot_auditor" not in active_specialists:
                    active_specialists.append("pilot_auditor")

        new_active_pid = target_pids[0] if target_pids else active_pid
        return {
            "planned_tasks": planned_tasks,
            "active_project_id": new_active_pid,
            "active_specialists": active_specialists,
            "dispatched_keys": dispatched_keys,
            "intent": "audit" if is_audit else intent,
            "active_playbook": "pilot_forensic_auditor" if is_audit else "buyer_due_diligence",
            "findings": [],
        }

    # Conditional routing after coordinator_plan
    def route_coordinator_plan(state: ForensicAgentState) -> Any:
        intent = state.get("intent")
        tasks = state.get("planned_tasks", [])
        if intent in ("greeting", "off_topic") or (intent == "followup" and not tasks and state.get("draft_answer")):
            return "deliver_answer"
        if not tasks:
            return "synthesizer"

        sends = []
        for t in tasks:
            spec = t.get("specialist", "due_diligence")
            if spec == "market_analyst":
                sends.append(Send("market_analyst_specialist", {"task": t, "db_path": resolved_db_path}))
            elif spec == "promoter_contagion":
                sends.append(Send("promoter_contagion_specialist", {"task": t, "db_path": resolved_db_path}))
            elif spec == "pilot_auditor":
                sends.append(Send("pilot_auditor_specialist", {"task": t, "db_path": resolved_db_path}))
            else:
                sends.append(Send("due_diligence_specialist", {"task": t, "db_path": resolved_db_path}))
                if intent in ("audit", "pilot_audit"):
                    sends.append(Send("pilot_auditor_specialist", {"task": t, "db_path": resolved_db_path}))
        return sends

    # Specialist Nodes
    def due_diligence_node(item: Dict[str, Any]) -> Dict[str, Any]:
        return due_diligence_specialist(item)

    def pilot_auditor_node(item: Dict[str, Any]) -> Dict[str, Any]:
        return pilot_auditor_specialist(item)

    def promoter_contagion_node(item: Dict[str, Any]) -> Dict[str, Any]:
        return promoter_contagion_specialist(item)

    def market_analyst_node(item: Dict[str, Any]) -> Dict[str, Any]:
        return market_analyst_specialist(item)

    # Node 3: Coordinator Reduce (Aggregate findings, budgets, post-barrier followups)
    def coordinator_reduce_node(state: ForensicAgentState) -> Dict[str, Any]:
        findings = state.get("findings", [])
        tool_call_count = state.get("tool_call_count", 0)
        hop_count = state.get("hop_count", 0)
        dispatched_keys = list(state.get("dispatched_keys", []))

        tool_evidence = dict(state.get("tool_evidence", {}))
        tool_evidence.setdefault("projects", {})
        tool_evidence.setdefault("aggregates", {})

        def _register_project_stub(pid_val: Any, stub: Dict[str, Any]) -> None:
            if pid_val is None:
                return
            p_str = str(pid_val)
            existing = tool_evidence.get(p_str)
            if isinstance(existing, dict) and existing:
                return
            tool_evidence[p_str] = stub
            tool_evidence["projects"][p_str] = stub

        followups: List[Dict[str, Any]] = []

        for f in findings:
            if not isinstance(f, dict):
                continue
            spec_name = f.get("specialist")
            pid = f.get("project_id")
            fdata = f.get("data", {})

            if pid is not None and isinstance(fdata, dict):
                pid_str = str(pid)
                if pid_str not in tool_evidence:
                    tool_evidence[pid_str] = {}
                if isinstance(tool_evidence[pid_str], dict):
                    tool_evidence[pid_str].update(fdata)
                else:
                    tool_evidence[pid_str] = fdata
                tool_evidence["projects"][pid_str] = tool_evidence[pid_str]

            # Register portfolio PIDs from promoter_contagion
            if spec_name == "promoter_contagion" and isinstance(fdata, dict):
                portfolio = fdata.get("portfolio") or {}
                for proj in portfolio.get("resolved_projects") or portfolio.get("projects") or []:
                    if isinstance(proj, dict) and proj.get("project_id") is not None:
                        _register_project_stub(
                            proj["project_id"],
                            {
                                "project_id": proj["project_id"],
                                "name": proj.get("name") or proj.get("project_name"),
                                "truth_flags": {"data_tier": "pilot_deep" if "deep" in str(proj.get("tier") or "").lower() else "statewide_core"},
                            },
                        )
                for cl in portfolio.get("clusters") or []:
                    if isinstance(cl, dict):
                        for cpid in cl.get("project_ids") or []:
                            _register_project_stub(
                                cpid,
                                {"project_id": cpid, "truth_flags": {"data_tier": "statewide_core"}},
                            )

            # Register screened PIDs and verified [agg:] scalars from market_analyst
            if spec_name == "market_analyst" and isinstance(fdata, dict):
                aggs = fdata.get("aggregates") or {}
                if isinstance(aggs, dict):
                    tool_evidence["aggregates"].update(aggs)
                for sp in fdata.get("screened_projects") or []:
                    if isinstance(sp, dict) and sp.get("project_id") is not None:
                        _register_project_stub(sp["project_id"], sp)

            # Register disambiguation candidate PIDs
            cdata = f.get("card_data") or {}
            if isinstance(cdata, dict) and "disambiguation" in cdata:
                for cand in cdata["disambiguation"].get("candidates") or []:
                    if isinstance(cand, dict) and cand.get("project_id") is not None:
                        _register_project_stub(
                            cand["project_id"],
                            {
                                "project_id": cand["project_id"],
                                "name": cand.get("name"),
                                "truth_flags": {"data_tier": "statewide_core"},
                            },
                        )

            # Check requested followups if budget allows
            if tool_call_count < 35 and hop_count < 2:
                req_followups = f.get("requested_followups", [])
                for rf in req_followups:
                    spec = rf.get("specialist")
                    p_name = rf.get("promoter_name")
                    f_pid = rf.get("project_id")

                    if spec == "promoter_contagion" and p_name:
                        key = f"promoter:{p_name.strip().upper()}"
                        if key not in dispatched_keys:
                            dispatched_keys.append(key)
                            followups.append({
                                "specialist": "promoter_contagion",
                                "promoter_name": p_name,
                                "project_id": f_pid,
                                "db_path": resolved_db_path,
                            })

                    elif spec == "pilot_auditor" and f_pid:
                        key = f"pilot:{f_pid}"
                        if key not in dispatched_keys:
                            dispatched_keys.append(key)
                            followups.append({
                                "specialist": "pilot_auditor",
                                "project_id": f_pid,
                                "db_path": resolved_db_path,
                            })

        updates: Dict[str, Any] = {
            "tool_evidence": tool_evidence,
            "dispatched_keys": dispatched_keys,
            "planned_tasks": followups,
        }
        if tool_call_count > 6:
            from langgraph.types import Overwrite
            updates["tool_call_count"] = Overwrite(6)
        if followups:
            updates["hop_count"] = hop_count + 1

        return updates

    # Conditional routing after coordinator_reduce
    def route_coordinator_reduce(state: ForensicAgentState) -> Any:
        followups = state.get("planned_tasks", [])
        if followups:
            sends = []
            for t in followups:
                spec = t.get("specialist")
                node_name = f"{spec}_specialist"
                sends.append(Send(node_name, {"task": t, "db_path": resolved_db_path}))
            return sends
        return "synthesizer"

    # Node 4: Synthesizer (Single verified exit writer)
    def synthesizer_node(state: ForensicAgentState, config: RunnableConfig) -> Dict[str, Any]:
        is_offline = state.get("offline_mode", False) or offline_mode or (llm is None)
        intent = state.get("intent")
        findings = state.get("findings", [])
        tool_evidence = state.get("tool_evidence", {})
        retry_feedback = state.get("retry_feedback", "")

        if is_offline:
            draft_answer = _synthesize_offline_answer(state, resolved_db_path, con)
            return {"draft_answer": draft_answer}

        playbook_guidance = get_playbook_instructions(
            intent=intent,
            data_tier="pilot_deep" if intent in ("audit", "pilot_audit") else None,
        )

        evidence_summary = _build_sanitized_evidence_summary(findings, tool_evidence)
        system_text = f"{FORENSIC_SYSTEM_PROMPT}\n\nINSTITUTIONAL PLAYBOOK GUIDANCE:\n{playbook_guidance}"

        messages: List[BaseMessage] = [SystemMessage(content=system_text)]
        for m in state.get("messages", []):
            if isinstance(m, HumanMessage):
                messages.append(m)

        if intent == "general_rera_qa":
            user_prompt = (
                "No project-specific or market screening tools were executed for this general Gujarat RERA question. "
                "Answer concisely using statutory Gujarat RERA concepts without fabricating any [pid:...], [bu:...], or [agg:...] markers."
            )
        else:
            user_prompt = (
                f"GATHERED FORENSIC EVIDENCE:\n{evidence_summary}\n\n"
                "Please synthesize a verified due-diligence report. "
                "Remember: keep Project Trailing Booked Benchmark (verify_sales_claim) distinct from Micro-Market Spatial IQR, "
                "and omit any claim verdict if verify_sales_claim did not run."
            )
        if retry_feedback:
            user_prompt += f"\n\nVERIFIER FEEDBACK FROM PREVIOUS ATTEMPT:\n{retry_feedback}\nYou MUST correct the citation or formatting anomaly."

        messages.append(HumanMessage(content=user_prompt))

        synthesis_llm, _ = get_synthesis_llm(llm_override=llm)
        tool_call_updates: List[BaseMessage] = []
        try:
            resp = synthesis_llm.invoke(messages, config={"metadata": {"emit-messages": False}})
            if getattr(resp, "tool_calls", None):
                trimmed_calls = resp.tool_calls[:6]
                tool_aimsg = AIMessage(content="", tool_calls=trimmed_calls)
                tool_call_updates.append(tool_aimsg)
                for tc in trimmed_calls:
                    t_name = tc.get("name")
                    t_fn = tool_map.get(t_name)
                    t_result = {}
                    if t_fn:
                        try:
                            t_result = t_fn.invoke(tc.get("args", {}))
                        except Exception as e:
                            t_result = {"error": str(e)}
                    tool_call_updates.append(
                        ToolMessage(
                            tool_call_id=tc.get("id", f"tc_{uuid.uuid4().hex[:6]}"),
                            content=json.dumps(t_result) if isinstance(t_result, (dict, list)) else str(t_result),
                        )
                    )
                resp = synthesis_llm.invoke(messages + tool_call_updates, config={"metadata": {"emit-messages": False}})
            draft_text = str(resp.content or "").strip()
        except Exception as e:
            logger.warning(f"Synthesis LLM call failed, falling back to deterministic synthesis: {e}")
            draft_text = _synthesize_offline_answer(state, resolved_db_path, con)

        updates: Dict[str, Any] = {"draft_answer": draft_text}
        if tool_call_updates:
            updates["messages"] = tool_call_updates
        return updates

    # Node 5: Citation Verifier (Strict evidentiary validation)
    def citation_verifier_node(state: ForensicAgentState) -> Dict[str, Any]:
        draft_text = state.get("draft_answer", "")
        tool_evidence = state.get("tool_evidence", {})
        retry_count = state.get("retry_count", 0)

        is_valid, failure_reason, sanitized_text = verify_evidentiary_output(draft_text, tool_evidence)

        if not is_valid and retry_count < 1:
            return {
                "retry_count": retry_count + 1,
                "retry_feedback": f"VERIFIER REJECTION: {failure_reason}",
                "verification_passed": False,
            }

        return {
            "retry_count": retry_count + 1 if not is_valid else retry_count,
            "verification_passed": is_valid,
            "draft_answer": sanitized_text,
        }

    # Conditional routing after citation_verifier
    def route_verifier(state: ForensicAgentState) -> str:
        if not state.get("verification_passed", False) and state.get("retry_count", 0) == 1:
            return "synthesizer"
        return "a2ui_emitter"

    # Node 6: A2UI Surface Emitter (Spec-compliant server-bound UI)
    def a2ui_emitter_node(state: ForensicAgentState) -> Dict[str, Any]:
        findings = state.get("findings", [])
        surfaces = build_a2ui_surfaces(findings)
        return {"a2ui_surfaces": surfaces}

    # Node 7: Deliver Answer (Verified final delivery via AG-UI protocol)
    def deliver_answer_node(state: ForensicAgentState, config: RunnableConfig) -> Dict[str, Any]:
        final_text = state.get("draft_answer", "").strip()
        message_id = f"msg_{uuid.uuid4().hex}"

        dispatch_custom_event(
            "manually_emit_message",
            {"message_id": message_id, "message": final_text, "role": "assistant"},
            config=config,
        )
        return {"messages": [AIMessage(id=message_id, content=final_text)]}

    # Build StateGraph
    builder = StateGraph(ForensicAgentState, input_schema=PublicInputState, output_schema=PublicAgentState)

    builder.add_node("input_guardrail", input_guardrail_node)
    builder.add_node("refusal", refusal_node)
    builder.add_node("coordinator_plan", coordinator_plan_node)
    builder.add_node("due_diligence_specialist", due_diligence_node)
    builder.add_node("pilot_auditor_specialist", pilot_auditor_node)
    builder.add_node("promoter_contagion_specialist", promoter_contagion_node)
    builder.add_node("market_analyst_specialist", market_analyst_node)
    builder.add_node("coordinator_reduce", coordinator_reduce_node)
    builder.add_node("synthesizer", synthesizer_node)
    builder.add_node("citation_verifier", citation_verifier_node)
    builder.add_node("a2ui_emitter", a2ui_emitter_node)
    builder.add_node("deliver_answer", deliver_answer_node)

    builder.add_edge(START, "input_guardrail")
    builder.add_conditional_edges("input_guardrail", route_guardrail, ["refusal", "coordinator_plan"])
    builder.add_edge("refusal", END)

    builder.add_conditional_edges(
        "coordinator_plan",
        route_coordinator_plan,
        [
            "due_diligence_specialist",
            "pilot_auditor_specialist",
            "promoter_contagion_specialist",
            "market_analyst_specialist",
            "synthesizer",
            "deliver_answer",
        ],
    )

    builder.add_edge("due_diligence_specialist", "coordinator_reduce")
    builder.add_edge("pilot_auditor_specialist", "coordinator_reduce")
    builder.add_edge("promoter_contagion_specialist", "coordinator_reduce")
    builder.add_edge("market_analyst_specialist", "coordinator_reduce")

    builder.add_conditional_edges(
        "coordinator_reduce",
        route_coordinator_reduce,
        ["promoter_contagion_specialist", "pilot_auditor_specialist", "synthesizer"],
    )

    builder.add_edge("synthesizer", "citation_verifier")
    builder.add_conditional_edges("citation_verifier", route_verifier, ["synthesizer", "a2ui_emitter"])
    builder.add_edge("a2ui_emitter", "deliver_answer")
    builder.add_edge("deliver_answer", END)

    return builder.compile(checkpointer=checkpointer).with_config(
        {"recursion_limit": recursion_limit, "max_concurrency": 5}
    )


def _build_sanitized_evidence_summary(findings: List[Dict[str, Any]], tool_evidence: Dict[str, Any]) -> str:
    """Format sanitized, fenced summaries of gathered findings for synthesis."""
    lines = []
    for f in findings:
        if not isinstance(f, dict):
            continue
        spec = f.get("specialist", "unknown")
        pid = f.get("project_id")
        summary = f.get("llm_summary") or f.get("data") or {}
        summary_str = json.dumps(summary, indent=2)
        fenced_str = sanitize_tool_prose(summary_str)
        lines.append(f"### Specialist: {spec} (Project: {pid})\n```json\n{fenced_str}\n```")
    return "\n\n".join(lines)


def _synthesize_offline_answer(
    state: ForensicAgentState,
    db_path: Any,
    con: Optional[sqlite3.Connection],
) -> str:
    """Generate verified, deterministic due-diligence report for offline mode."""
    intent = state.get("intent", "due_diligence")
    findings = state.get("findings", [])
    active_pid = state.get("active_project_id")

    messages = state.get("messages", [])
    raw_query = ""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            raw_query = str(m.content or "")
            break

    if intent == "general_rera_qa":
        return (
            "Under Gujarat RERA (GujRERA), Section 4(2)(l)(D) mandates depositing 70% of buyer receipts "
            "into a designated project retention account, withdrawable strictly in proportion to certified "
            "construction progress (Form 1 Architect, Form 2 Engineer, and Form 3/5 CA disclosures). "
            "Ask about a specific project or [pid:<id>] to inspect live filings."
        )

    # 1. Multi-candidate / Fuzzy Disambiguation Case
    if intent == "disambiguation":
        clean_q = _clean_search_phrase(raw_query) or raw_query.strip()
        candidates: List[Dict[str, Any]] = []
        for f in findings:
            if isinstance(f, dict):
                cd = f.get("card_data") or {}
                if isinstance(cd, dict) and "disambiguation" in cd:
                    candidates = cd["disambiguation"].get("candidates") or []
                    break
                if "project_id" in f:
                    candidates.append(f)

        if not candidates:
            read_con = con or get_connection(db_path, read_only=True)
            try:
                candidates = search_project_summaries(read_con, q=clean_q, limit=5)
            finally:
                if read_con and read_con != con:
                    read_con.close()

        lines = [f"Multiple projects matched '{clean_q}':"]
        for c in candidates[:5]:
            pid = c.get("project_id")
            name = c.get("name") or c.get("project_name", "")
            dist = c.get("district") or "Gujarat"
            mtype = " (fuzzy match)" if c.get("match_type") == "fuzzy" else ""
            lines.append(f"- [pid:{pid}]: {name} ({dist}){mtype}")
        lines.append("\nPlease specify or select the Project ID to proceed with forensic due diligence.")
        return "\n".join(lines)

    # 2. Zero Matches Case
    if not findings and not active_pid:
        clean_q = _clean_search_phrase(raw_query) or raw_query.strip()
        read_con = con or get_connection(db_path, read_only=True)
        try:
            portfolio = resolve_promoter_portfolio(read_con, promoter_name=clean_q)
            schemes = portfolio.get("resolved_projects") or portfolio.get("projects") or []
            if schemes:
                lines = [f"Multiple projects matched '{clean_q}':"]
                for p in schemes[:10]:
                    lines.append(f"- [pid:{p['project_id']}]: {p.get('name') or p.get('project_name')} ({p.get('district')})")
                return "\n".join(lines)
        finally:
            if read_con and read_con != con:
                read_con.close()

        return f"No Gujarat RERA projects matching '{clean_q}' were found in the statutory database."

    # 3. Verified Specialist Synthesis
    sections = []
    by_pid: Dict[int, Dict[str, Any]] = {}
    promoter_findings: List[Dict[str, Any]] = []
    market_findings: List[Dict[str, Any]] = []

    for f in findings:
        if not isinstance(f, dict):
            continue
        spec_name = f.get("specialist", "")
        pid = f.get("project_id")
        if spec_name == "market_analyst":
            market_findings.append(f)
        elif spec_name == "promoter_contagion":
            promoter_findings.append(f)
        elif pid is not None:
            by_pid.setdefault(int(pid), {})[spec_name] = f

    for pid, specs in by_pid.items():
        dd_finding = specs.get("due_diligence", {})
        pilot_finding = specs.get("pilot_auditor", {})
        card_data = dd_finding.get("card_data") or {}
        truth_flags = card_data.get("dossier_truth", {}).get("truth_flags") or {}
        p_name = card_data.get("dossier_truth", {}).get("project_name") or f"Project {pid}"
        promoter = card_data.get("dossier_truth", {}).get("promoter_name") or "Promoter"
        district = card_data.get("dossier_truth", {}).get("district") or "Gujarat"
        tier = truth_flags.get("data_tier", "statewide_core")
        tier_label = f"{tier} (Statewide Core - disclosures uningested or partial)" if tier == "statewide_core" else tier

        has_bu = truth_flags.get("has_bu_noc", False)
        bu_cert = truth_flags.get("bu_certificate_no")
        bu_ev = truth_flags.get("bu_evidence", "")
        status_badge = truth_flags.get("status_badge", "")

        if has_bu and bu_cert and str(bu_cert).isdigit() and bu_ev == "doc_id":
            bu_citation_str = f"verified certificate [bu:{bu_cert}@{pid}]"
        else:
            bu_citation_str = f"status {status_badge}"

        sec_lines = [
            f"## Statutory Diligence Report: {p_name} [pid:{pid}]",
            f"- **Promoter / Developer:** {promoter}",
            f"- **Location:** {district}",
            f"- **Data Tier:** {tier_label}",
            f"- **Building Use (BU) Clearance:** {bu_citation_str}",
            f"- **Statutory Status Badge:** {status_badge}",
        ]

        spatial = dd_finding.get("data", {}).get("spatial", {})
        if spatial and spatial.get("median_rate_sqft"):
            median = spatial.get("median_rate_sqft")
            p25 = spatial.get("p25")
            p75 = spatial.get("p75")
            n = spatial.get("sample_size", 0)
            sec_lines.append(f"- **Micro-Market Spatial IQR:** Median ₹{median:,.0f}/sqft (IQR: ₹{p25:,.0f} - ₹{p75:,.0f}/sqft, sample size: {n} units)")

        claim_data = card_data.get("claim_verdict")
        if claim_data:
            emp_med = claim_data.get("empirical_median")
            spread = claim_data.get("spread_pct")
            bench_note = f", Project Trailing Benchmark: ₹{emp_med:,.0f}/sqft ({spread:+.1f}%)" if emp_med is not None and spread is not None else ""
            sec_lines.append(
                f"- **Project Sales Claim Verdict:** {claim_data.get('verdict')} "
                f"(Claimed: ₹{claim_data.get('claimed_value'):,.0f}/sqft{bench_note}) — {claim_data.get('summary')}"
            )

        if pilot_finding:
            p_data = pilot_finding.get("data", {})
            leads = p_data.get("discrepancies", [])
            has_skipped = p_data.get("has_skipped_uningested", False)
            sec_lines.append(f"- **Statutory Audit Leads:** {len(leads)} lead(s) identified")
            for l in leads[:3]:
                sec_lines.append(f"  - [{l.get('severity')}] {l.get('title')}: {l.get('detail')}")
            if has_skipped:
                sec_lines.append("  - ⚠️ Statutory disclosures contain SKIPPED_UNINGESTED filings under statewide core tier.")

        sections.append("\n".join(sec_lines))

    for mf in market_findings:
        if mf.get("status") == "error":
            sections.append(f"## Market Screening Summary\n- Market screening unavailable: {mf.get('error')}")
            continue
        mdata = mf.get("data", {})
        aggs = mdata.get("aggregates", {})
        dist = mdata.get("district") or "All Gujarat"
        ptype = mdata.get("project_type") or "All Asset Types"
        m_lines = [f"## Market Screening Summary: {dist} ({ptype})"]
        if aggs:
            sc = (aggs.get("screen_count") or {}).get("value")
            mp = (aggs.get("district_median_price") or {}).get("value")
            ab = (aggs.get("avg_absorption_pct") or {}).get("value")
            ms = (aggs.get("markup_spread_pct") or {}).get("value")
            zc = (aggs.get("zombie_count") or {}).get("value")
            m_lines.append(f"- **Matched Projects:** {sc} `[agg:screen_count]`")
            if mp is not None:
                m_lines.append(f"- **District Median Booked Rate:** ₹{mp:,.2f}/sqft `[agg:district_median_price]`")
            if ab is not None:
                m_lines.append(f"- **Average Absorption:** {ab}% `[agg:avg_absorption_pct]`")
            if ms is not None:
                m_lines.append(f"- **Unbooked Markup Spread:** {ms}% `[agg:markup_spread_pct]`")
            m_lines.append(f"- **Expired Without BU Schemes:** {zc} `[agg:zombie_count]`")
        for row in (mdata.get("screened_projects") or [])[:5]:
            rpid = row.get("project_id")
            rname = row.get("name")
            rpx = row.get("avg_price_sqft")
            rabs = row.get("absorption_pct")
            px_str = f"₹{rpx:,.0f}/sqft" if rpx is not None else "N/A"
            abs_str = f"{rabs}%" if rabs is not None else "N/A"
            m_lines.append(f"  - [pid:{rpid}] {rname}: avg {px_str}, absorption {abs_str}")
        sections.append("\n".join(m_lines))

    for pf in promoter_findings:
        p_data = pf.get("data", {})
        portfolio = p_data.get("portfolio") or {}
        clusters = portfolio.get("clusters", [])
        resolved_projects = portfolio.get("resolved_projects") or portfolio.get("projects") or []
        p_name = pf.get("promoter_name") or portfolio.get("promoter_name") or "Promoter"
        contagion_leads = p_data.get("contagion_leads") or []

        if p_data.get("is_multi_cluster") or len(clusters) > 1:
            p_lines = [f"### Developer Portfolio Multi-Cluster Notice: {p_name}"]
            p_lines.append(f"Developer operates across {len(clusters)} distinct geographic cluster(s):")
            for c in clusters:
                dists = ", ".join(c.get("districts") or ([c.get("district")] if c.get("district") else ["Unknown"]))
                cnt = c.get("portfolio_count") or c.get("schemes_count") or len(c.get("project_ids", []))
                p_lines.append(f"- **{dists}**: {cnt} scheme(s) ({', '.join(f'[pid:{p}]' for p in c.get('project_ids', []))})")
            sections.append("\n".join(p_lines))
        else:
            p_lines = [f"### Developer Portfolio Summary: {p_name}"]
            p_lines.append(
                f"- **Portfolio Schemes:** {portfolio.get('portfolio_count') or len(resolved_projects)} "
                f"(Linkage confidence: {portfolio.get('linkage_confidence', 'MEDIUM')}, "
                f"Contagion leads: {len(contagion_leads)})"
            )
            for proj in resolved_projects[:10]:
                if isinstance(proj, dict) and proj.get("project_id") is not None:
                    p_lines.append(
                        f"  - [pid:{proj['project_id']}]: {proj.get('name') or proj.get('project_name')} "
                        f"({proj.get('district') or 'Gujarat'})"
                    )
            sections.append("\n".join(p_lines))

    return "\n\n---\n\n".join(sections)
