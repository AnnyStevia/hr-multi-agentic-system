"""LangGraph state for the unified assistant orchestrator."""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict

from app.ai.core.context.models import AIExecutionContext
from app.ai.registry.definitions import AgentDefinition

AssistantStatus = Literal["completed", "clarification_required", "unavailable"]


class OrchestratorState(TypedDict):
    """In-process graph state. Never mutate AIExecutionContext fields."""

    message: str
    context: AIExecutionContext
    available: list[AgentDefinition]
    available_ids: list[str]
    route_kind: NotRequired[str]
    route_reason: NotRequired[str]
    agent_id: NotRequired[str | None]
    status: NotRequired[AssistantStatus]
    answer: NotRequired[str]
    citations: NotRequired[list[dict[str, Any]]]
    pending_confirmation: NotRequired[dict[str, Any] | None]
    model: NotRequired[str | None]
    tool_names_called: NotRequired[list[str]]
    usage: NotRequired[dict[str, Any] | None]
    node_path: NotRequired[list[str]]
    llm_clarify_attempted: NotRequired[bool]
    # Reserved for Orc.4 allowlisted handoffs (unused when allowlist empty).
    handoff_target: NotRequired[str | None]
    handoff_from: NotRequired[str | None]
