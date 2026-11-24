"""Input & Evidentiary Output Guardrails for Sovereign Forensic Agent.

Enforces:
1. Input Guardrail: Per-turn state resets via Overwrite, prompt-injection/scope screening, PII scrubbing.
2. Indirect Prompt Injection Sanitization: Fences untrusted database strings before LLM synthesis.
3. Evidentiary Citation Verification:
   - Validates [pid:<id>] and [bu:<numeric_doc_id>@<pid>] citations strictly against current turn tool_evidence.
   - Rejects cross-project certs, fabricated certs, and placeholder strings.
   - Rejects compliance claims when SKIPPED_UNINGESTED statutory filings exist.
   - Scrubs prose via _scrub_text and payloads via redact_payload without touching protocol envelope IDs.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.types import Overwrite

from ..db.redaction import _scrub_text as _base_scrub_text, redact_payload


# Strict citation markers
PID_CITATION_REGEX = re.compile(r"\[pid:(\d+)\]")
BU_CITATION_REGEX = re.compile(r"\[bu:([^@\]]+)@(\d+)\]")
AGG_CITATION_REGEX = re.compile(r"\[agg:([A-Za-z0-9_:-]+)\]")

# Phone pattern for Indian mobile numbers
PHONE_REGEX = re.compile(r"(?:\+91[\-\s]?)?[6-9]\d{9}\b")


def _scrub_text(text: str) -> str:
    """Scrub PAN, Aadhaar, email, phone, and account numbers from text."""
    if not text:
        return text
    base_scrubbed = _base_scrub_text(text)
    return PHONE_REGEX.sub("[REDACTED-PHONE]", base_scrubbed)


# Compliance claim patterns requiring full ingestion proof
COMPLIANCE_CLAIM_REGEX = re.compile(
    r"\b(fully compliant|no discrepancies|clean audit|zero issues|zero discrepancies|statutorily compliant|completely clean)\b",
    re.IGNORECASE,
)

# Escrow / fund-diversion assurance patterns forbidden without qualification on statewide_core / uningested schemes
ESCROW_ASSURANCE_REGEX = re.compile(
    r"\b(no evidence of fund diversion|no fund diversion|no escrow issues|financially clean)\b",
    re.IGNORECASE,
)

# Explicit uningested / uncertainty qualifications that permit discussing skipped disclosures
UNINGESTED_QUALIFICATION_REGEX = re.compile(
    r"\b(SKIPPED_UNINGESTED|uningested|not audited|cannot confirm|unable to verify)\b",
    re.IGNORECASE,
)

# Potential prompt injection / out-of-scope directives in user input
INJECTION_REGEX = re.compile(
    r"(ignore (all )?previous instructions|system prompt|bypass (guardrails|safety)|drop table|delete from|update projects set)",
    re.IGNORECASE,
)

# Indirect prompt injection indicators inside untrusted database strings
INDIRECT_INJECTION_REGEX = re.compile(
    r"(ignore\s+(all\s+)?previous\s+instructions|system\s+prompt|bypass\s+(guardrails|safety)|you\s+are\s+now|override\s+system|<\|im_start\|>|<\|im_end\|>|<script|javascript:)",
    re.IGNORECASE,
)


def sanitize_tool_prose(text: str) -> str:
    """Sanitize and fence external/database text before feeding into LLM synthesis.

    Protects against indirect prompt injection embedded inside developer remarks,
    promoter notes, or scraped document texts.
    """
    if not text:
        return text
    cleaned = INDIRECT_INJECTION_REGEX.sub("[FILTERED-POTENTIAL-INJECTION]", text)
    return _scrub_text(cleaned)


def run_input_guardrail(
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute turn initialization, per-turn state resets, and input screening.

    Resets deliberation and per-turn counters while preserving active_project_id,
    canvas_mode, and conversation message history.
    """
    updates: Dict[str, Any] = {
        "draft_answer": "",
        "retry_feedback": "",
        "tool_evidence": {},
        "findings": Overwrite([]),
        "tool_call_count": Overwrite(0),
        "retry_count": 0,
        "guardrail_flags": [],
        "verification_passed": False,
        "active_specialists": [],
        "planned_tasks": [],
        "hop_count": 0,
        "dispatched_keys": [],
        "intent": None,
        "active_playbook": None,
        "a2ui_surfaces": Overwrite([]),
    }

    # Screen and scrub the latest user message
    messages: List[BaseMessage] = state.get("messages", [])
    if messages:
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            raw_text = str(last_msg.content or "")
            flags: List[str] = list(state.get("guardrail_flags", []))

            # Prompt injection screening
            if INJECTION_REGEX.search(raw_text):
                flags.append("PROMPT_INJECTION_DETECTED")
                updates["guardrail_flags"] = flags

            # Scrub PII in user text without mutating in place
            scrubbed_content = _scrub_text(raw_text)
            if scrubbed_content != raw_text:
                msg_id = getattr(last_msg, "id", None)
                updates["messages"] = [HumanMessage(id=msg_id, content=scrubbed_content)]

    return updates


def verify_evidentiary_output(
    draft_text: str,
    tool_evidence: Dict[str, Any],
) -> Tuple[bool, str, str]:
    """Synchronously verify citations, evidentiary backing, and statutory compliance claims.

    Args:
        draft_text: Raw prose generated by the model.
        tool_evidence: Map of project_id (str) -> gathered evidence dict from current turn.
                       Supports both flat dicts and {"projects": {pid: evidence}}.

    Returns:
        (is_valid, failure_reason, sanitized_text)
    """
    if not draft_text:
        return True, "", ""

    # Ensure tool_evidence keys are strings and handle both flat and nested 'projects' structure
    evidence_by_pid: Dict[str, Dict[str, Any]] = {}
    agg_map: Dict[str, Any] = {}
    if isinstance(tool_evidence, dict):
        if "projects" in tool_evidence and isinstance(tool_evidence["projects"], dict):
            for k, v in tool_evidence["projects"].items():
                if isinstance(v, dict):
                    evidence_by_pid[str(k)] = v
        if "aggregates" in tool_evidence and isinstance(tool_evidence["aggregates"], dict):
            agg_map = tool_evidence["aggregates"]
        for k, v in tool_evidence.items():
            if k not in ("projects", "promoters", "aggregates") and isinstance(v, dict):
                evidence_by_pid[str(k)] = v

    # 1. Validate [pid:<id>] markers
    cited_pids = PID_CITATION_REGEX.findall(draft_text)
    for pid_str in cited_pids:
        if pid_str not in evidence_by_pid:
            return (
                False,
                f"Unverified project citation [pid:{pid_str}] was not queried or returned by any tool in this turn.",
                _sanitize_failed_draft(draft_text, f"Unverified citation [pid:{pid_str}]", agg_map=agg_map),
            )

    # 2. Validate [bu:<doc_id>@<pid>] markers
    cited_bus = BU_CITATION_REGEX.findall(draft_text)
    for doc_id, pid_str in cited_bus:
        if pid_str not in evidence_by_pid:
            return (
                False,
                f"Project {pid_str} in BU citation [bu:{doc_id}@{pid_str}] has no evidence in this turn.",
                _sanitize_failed_draft(draft_text, f"Unverified BU citation [bu:{doc_id}@{pid_str}]", agg_map=agg_map),
            )

        p_evidence = evidence_by_pid[pid_str]
        tf = p_evidence.get("truth_flags") or p_evidence
        actual_cert = str(tf.get("bu_certificate_no") or "").strip()
        bu_ev = str(tf.get("bu_evidence") or "").strip()

        # Must have numeric doc_id evidence matching the cited cert
        if bu_ev != "doc_id" or not actual_cert.isdigit() or actual_cert != doc_id:
            return (
                False,
                f"Invalid or cross-project BU citation [bu:{doc_id}@{pid_str}]. Ground truth cert is {actual_cert!r} with evidence tier {bu_ev!r}.",
                _sanitize_failed_draft(draft_text, f"Invalid BU citation [bu:{doc_id}@{pid_str}]", agg_map=agg_map),
            )

    # 3. Validate [agg:<id>] markers strictly against tool_evidence["aggregates"]
    cited_aggs = AGG_CITATION_REGEX.findall(draft_text)
    for agg_id in cited_aggs:
        if agg_id not in agg_map:
            return (
                False,
                f"Unverified aggregate citation [agg:{agg_id}] was not computed in this turn.",
                _sanitize_failed_draft(draft_text, f"Unverified aggregate citation '{agg_id}'", agg_map=agg_map),
            )

    # 4. Reject unqualified compliance & escrow/fund-diversion assurances on uningested / statewide_core schemes
    uningested_pids = set()
    for pid_str, p_evidence in evidence_by_pid.items():
        tf = p_evidence.get("truth_flags") or p_evidence
        tier = str(tf.get("data_tier") or "").strip().lower()
        if p_evidence.get("has_skipped_uningested") or tier == "statewide_core":
            uningested_pids.add(pid_str)

    if uningested_pids:
        sentences = [s for s in re.split(r"(?<=[.!?])\s+|\n+", draft_text) if s.strip()]
        for sent in sentences:
            has_compliance = bool(COMPLIANCE_CLAIM_REGEX.search(sent))
            has_escrow_assurance = bool(ESCROW_ASSURANCE_REGEX.search(sent))
            if not (has_compliance or has_escrow_assurance):
                continue

            # Allow if the same sentence/clause explicitly qualifies uningested / unverified scope
            if UNINGESTED_QUALIFICATION_REGEX.search(sent):
                continue

            sent_pids = PID_CITATION_REGEX.findall(sent)
            if sent_pids:
                # Reject if ANY cited project in this sentence is statewide_core / uningested
                offending = [p for p in sent_pids if p in uningested_pids]
                if not offending:
                    continue
                target_label = f"Project {offending[0]}"
            else:
                target_label = f"Project {next(iter(sorted(uningested_pids)))}"

            reason_tag = "Escrow/fund-diversion assurance on uningested disclosures" if has_escrow_assurance else "Compliance claim on uningested disclosures"
            return (
                False,
                f"{target_label} has uningested Form 3 / Form 5 / escrow disclosures (statewide_core / SKIPPED_UNINGESTED); unqualified assurances are forbidden.",
                _sanitize_failed_draft(draft_text, reason_tag, agg_map=agg_map),
            )

    # 5. Final PII scrub on prose
    sanitized = _scrub_text(draft_text)
    return True, "", sanitized


def _sanitize_failed_draft(draft_text: str, reason: str, agg_map: Optional[Dict[str, Any]] = None) -> str:
    """Strip or flag unverified claims and append a deterministic compliance notice."""
    scrubbed = _scrub_text(draft_text)
    if agg_map is not None:
        scrubbed = AGG_CITATION_REGEX.sub(
            lambda m: m.group(0) if m.group(1) in agg_map else "[UNVERIFIED-AGG-REMOVED]",
            scrubbed,
        )
    notice = f"\n\n[Notice: Verifier Redaction — {reason} was withheld for evidentiary compliance.]"
    return scrubbed + notice
