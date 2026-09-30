"""Public entry: run the unified assistant LangGraph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.ai.core.context.models import AIExecutionContext
from app.ai.core.llm.base import LLMProvider
from app.ai.orchestration.graph.agents import SpecialistAgents
from app.ai.orchestration.graph.builder import build_assistant_graph

AssistantStatus = Literal["completed", "clarification_required", "unavailable"]


@dataclass(frozen=True)
class OrchestratorResult:
    agent_id: str | None
    answer: str
    status: AssistantStatus
    citations: list[dict[str, Any]]
    pending_confirmation: dict[str, Any] | None
    model: str | None
    tool_names_called: list[str]
    usage: dict[str, Any] | None
    route_reason: str | None
    node_path: list[str]


def run_assistant_orchestration(
    *,
    message: str,
    context: AIExecutionContext,
    agents: SpecialistAgents,
    llm_provider: LLMProvider | None = None,
    llm_clarify_enabled: bool | None = None,
) -> OrchestratorResult:
    """Invoke the compiled graph once. Raises specialist agent exceptions unchanged."""
    graph = build_assistant_graph(
        agents=agents,
        llm_provider=llm_provider,
        llm_clarify_enabled=llm_clarify_enabled,
    )
    final = graph.invoke(
        {
            "message": message,
            "context": context,
            "available": [],
            "available_ids": [],
            "node_path": [],
        }
    )
    status = final.get("status") or "clarification_required"
    if status not in ("completed", "clarification_required", "unavailable"):
        status = "clarification_required"
    return OrchestratorResult(
        agent_id=final.get("agent_id"),
        answer=final.get("answer") or "",
        status=status,
        citations=list(final.get("citations") or []),
        pending_confirmation=final.get("pending_confirmation"),
        model=final.get("model"),
        tool_names_called=list(final.get("tool_names_called") or []),
        usage=final.get("usage"),
        route_reason=final.get("route_reason"),
        node_path=list(final.get("node_path") or []),
    )
