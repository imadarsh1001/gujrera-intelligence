"""Forensic Agent State Definition.

Defines the plain-JSON state schema for the sovereign GujRERA forensic agent.
Enforces strict messagepack/JSON serializability with zero non-serializable objects.
Uses additive reducers for parallel specialist findings and tool call counting.
"""

import operator
from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class PublicInputState(TypedDict, total=False):
    """External client input schema: allows ONLY messages and optional active_project_id.
    
    Prevents browsers or API callers from injecting internal flags like offline_mode,
    tool_evidence, findings, or active_cluster.
    """

    messages: Annotated[List[BaseMessage], add_messages]
    active_project_id: Optional[int]


class PublicAgentState(TypedDict):
    """Public client output schema: contains only sanitized, public-facing workbench state.
    
    Guarantees STATE_SNAPSHOT never leaks internal deliberative fields (draft_answer,
    retry_feedback, tool_evidence, raw findings, etc.).
    """

    messages: Annotated[List[BaseMessage], add_messages]
    active_project_id: Optional[int]
    canvas_mode: Optional[str]
    highlight_pins: List[str]
    active_cluster: Optional[str]
    active_specialists: List[str]
    a2ui_surfaces: List[Dict[str, Any]]
    verification_passed: bool


class ForensicAgentState(TypedDict):
    """Sovereign forensic agent conversation and deliberation state."""

    # Conversational messages managed via add_messages reducer
    messages: Annotated[List[BaseMessage], add_messages]

    # Deliberation & verification channels (hidden from messages until verified)
    draft_answer: str
    retry_feedback: str

    # Conversation context and UI view state
    active_project_id: Optional[int]
    canvas_mode: Optional[str]
    highlight_pins: List[str]
    active_cluster: Optional[str]
    active_specialists: List[str]
    a2ui_surfaces: List[Dict[str, Any]]

    # Evidentiary store and additive parallel execution channels
    tool_evidence: Dict[str, Any]
    findings: Annotated[List[Dict[str, Any]], operator.add]
    tool_call_count: Annotated[int, operator.add]
    retry_count: int

    # Coordinator planning & map-reduce tracking
    planned_tasks: List[Dict[str, Any]]
    hop_count: int
    dispatched_keys: List[str]
    intent: Optional[str]
    active_playbook: Optional[str]

    # Safety, verification, and offline indicators
    guardrail_flags: List[str]
    verification_passed: bool
    offline_mode: bool
