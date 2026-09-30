"""LangGraph nodes: availability → route → optional LLM clarify → invoke one specialist."""

from __future__ import annotations

from typing import Any, Callable

from app.ai.agents.documents import DocumentsAgentRequest
from app.ai.agents.knowledge import KnowledgeAgentRequest
from app.ai.agents.leave import LeaveAgentRequest
from app.ai.agents.offboarding import OffboardingAgentRequest
from app.ai.agents.onboarding import OnboardingAgentRequest
from app.ai.agents.recruitment import RecruitmentAgentRequest
from app.ai.agents.training import TrainingAgentRequest
from app.ai.core.config import ai_settings
from app.ai.core.llm.base import LLMProvider
from app.ai.orchestration.graph.agents import SpecialistAgents
from app.ai.orchestration.graph.llm_clarify import try_llm_select_agent
from app.ai.orchestration.graph.messages import (
    CLARIFY_ANSWER,
    NO_AGENTS_ANSWER,
    UNAVAILABLE_ANSWER,
)
from app.ai.orchestration.graph.state import OrchestratorState
from app.ai.orchestration.handoffs import is_handoff_allowed
from app.ai.registry import get_available_agents
from app.ai.routing import route_message


def _append_path(state: OrchestratorState, node: str) -> list[str]:
    path = list(state.get("node_path") or [])
    path.append(node)
    return path


def _pending_dict(pending: Any) -> dict[str, Any] | None:
    if pending is None:
        return None
    return {
        "token": pending.token,
        "tool_name": pending.tool_name,
        "summary": pending.summary,
        "expires_at": pending.expires_at,
    }


def _usage_dict(usage: Any) -> dict[str, Any] | None:
    if usage is None:
        return None
    return {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "thinking_tokens": usage.thinking_tokens,
        "total_tokens": usage.total_tokens,
    }


def filter_available(state: OrchestratorState) -> dict[str, Any]:
    context = state["context"]
    available = list(get_available_agents(context))
    return {
        "available": available,
        "available_ids": [a.id for a in available],
        "node_path": _append_path(state, "filter_available"),
    }


def select_agent(state: OrchestratorState) -> dict[str, Any]:
    available = state.get("available") or []
    if not available:
        return {
            "route_kind": "unavailable",
            "route_reason": "no_available_agents",
            "agent_id": None,
            "status": "unavailable",
            "answer": NO_AGENTS_ANSWER,
            "citations": [],
            "pending_confirmation": None,
            "model": None,
            "tool_names_called": [],
            "usage": None,
            "node_path": _append_path(state, "select_agent"),
        }

    decision = route_message(state["message"], available)
    updates: dict[str, Any] = {
        "route_kind": decision.kind,
        "route_reason": decision.reason,
        "agent_id": decision.agent_id,
        "node_path": _append_path(state, "select_agent"),
    }
    if decision.kind == "clarify":
        updates.update(
            {
                "status": "clarification_required",
                "answer": CLARIFY_ANSWER,
                "citations": [],
                "pending_confirmation": None,
                "model": None,
                "tool_names_called": [],
                "usage": None,
            }
        )
    elif decision.kind == "unavailable":
        updates.update(
            {
                "status": "unavailable",
                "answer": UNAVAILABLE_ANSWER,
                "citations": [],
                "pending_confirmation": None,
                "model": None,
                "tool_names_called": [],
                "usage": None,
            }
        )
    elif decision.agent_id is None or decision.agent_id not in {
        a.id for a in available
    }:
        updates.update(
            {
                "route_kind": "unavailable",
                "route_reason": "defensive_unavailable",
                "agent_id": None,
                "status": "unavailable",
                "answer": UNAVAILABLE_ANSWER,
                "citations": [],
                "pending_confirmation": None,
                "model": None,
                "tool_names_called": [],
                "usage": None,
            }
        )
    return updates


def maybe_llm_clarify(
    state: OrchestratorState,
    *,
    llm_provider: LLMProvider | None,
    enabled: bool,
) -> dict[str, Any]:
    """Orc.3: only when router clarified and flag enabled."""
    path = _append_path(state, "maybe_llm_clarify")
    if not enabled or llm_provider is None:
        return {"llm_clarify_attempted": False, "node_path": path}
    if state.get("route_kind") != "clarify":
        return {"llm_clarify_attempted": False, "node_path": path}

    chosen = try_llm_select_agent(
        provider=llm_provider,
        message=state["message"],
        available=list(state.get("available") or []),
    )
    if chosen is None:
        return {"llm_clarify_attempted": True, "node_path": path}

    return {
        "llm_clarify_attempted": True,
        "route_kind": "agent",
        "route_reason": "llm_clarify_selection",
        "agent_id": chosen,
        "status": None,
        "answer": None,
        "node_path": path,
    }


def invoke_specialist(
    state: OrchestratorState,
    *,
    agents: SpecialistAgents,
) -> dict[str, Any]:
    """Call exactly one specialist.ask — never aggregates tools."""
    agent_id = state.get("agent_id")
    context = state["context"]
    question = (state["message"] or "").strip()
    path = _append_path(state, "invoke_specialist")

    if not agent_id:
        return {
            "status": "clarification_required",
            "answer": CLARIFY_ANSWER,
            "citations": [],
            "pending_confirmation": None,
            "model": None,
            "tool_names_called": [],
            "usage": None,
            "node_path": path,
        }

    agent = agents.get(agent_id)
    if agent is None:
        return {
            "agent_id": None,
            "status": "unavailable",
            "answer": UNAVAILABLE_ANSWER,
            "citations": [],
            "pending_confirmation": None,
            "model": None,
            "tool_names_called": [],
            "usage": None,
            "node_path": path,
        }

    if agent_id == "knowledge":
        result = agent.ask(KnowledgeAgentRequest(question=question, context=context))
        return {
            "agent_id": "knowledge",
            "status": "completed",
            "answer": result.answer,
            "citations": [
                {
                    "citation_id": c.citation_id,
                    "document_name": c.document_name,
                    "page_start": c.page_start,
                    "page_end": c.page_end,
                    "company_document_id": c.company_document_id,
                }
                for c in result.citations
            ],
            "pending_confirmation": None,
            "model": result.model,
            "tool_names_called": [],
            "usage": _usage_dict(result.usage),
            "node_path": path,
        }

    if agent_id == "leave":
        result = agent.ask(LeaveAgentRequest(question=question, context=context))
    elif agent_id == "recruitment":
        result = agent.ask(RecruitmentAgentRequest(question=question, context=context))
    elif agent_id == "onboarding":
        result = agent.ask(OnboardingAgentRequest(question=question, context=context))
    elif agent_id == "training":
        result = agent.ask(TrainingAgentRequest(question=question, context=context))
    elif agent_id == "documents":
        result = agent.ask(DocumentsAgentRequest(question=question, context=context))
    elif agent_id == "offboarding":
        result = agent.ask(OffboardingAgentRequest(question=question, context=context))
    else:
        return {
            "agent_id": None,
            "status": "clarification_required",
            "answer": CLARIFY_ANSWER,
            "citations": [],
            "pending_confirmation": None,
            "model": None,
            "tool_names_called": [],
            "usage": None,
            "node_path": path,
        }

    pending = _pending_dict(getattr(result, "pending_confirmation", None))
    return {
        "agent_id": agent_id,
        "status": "completed",
        "answer": result.answer,
        "citations": [],
        "pending_confirmation": pending,
        "model": result.model,
        "tool_names_called": list(getattr(result, "tool_names_called", []) or []),
        "usage": _usage_dict(getattr(result, "usage", None)),
        "node_path": path,
    }


def maybe_allowlisted_handoff(state: OrchestratorState) -> dict[str, Any]:
    """Orc.4 hook: only records allowlisted handoff intent; default allowlist empty."""
    path = _append_path(state, "maybe_allowlisted_handoff")
    source = state.get("agent_id")
    target = state.get("handoff_target")
    if (
        source
        and target
        and is_handoff_allowed(source_agent_id=source, target_agent_id=target)
    ):
        return {
            "handoff_from": source,
            "node_path": path,
        }
    return {
        "handoff_target": None,
        "handoff_from": None,
        "node_path": path,
    }


def normalize_envelope(state: OrchestratorState) -> dict[str, Any]:
    """Ensure soft outcomes have required fields for the HTTP envelope."""
    path = _append_path(state, "normalize_envelope")
    status = state.get("status")
    if status in {"clarification_required", "unavailable"}:
        return {
            "agent_id": None,
            "citations": state.get("citations") or [],
            "pending_confirmation": None,
            "tool_names_called": [],
            "node_path": path,
        }
    return {
        "citations": state.get("citations") or [],
        "tool_names_called": state.get("tool_names_called") or [],
        "node_path": path,
    }


def route_after_select(state: OrchestratorState) -> str:
    if state.get("route_kind") == "agent" and state.get("agent_id"):
        return "invoke"
    return "soft_outcome"


def route_after_clarify(state: OrchestratorState) -> str:
    if state.get("route_kind") == "agent" and state.get("agent_id"):
        return "invoke"
    return "soft_outcome"


def build_node_fns(
    *,
    agents: SpecialistAgents,
    llm_provider: LLMProvider | None = None,
    llm_clarify_enabled: bool | None = None,
) -> dict[str, Callable[[OrchestratorState], dict[str, Any]]]:
    enabled = (
        ai_settings.ai_orchestrator_llm_clarify
        if llm_clarify_enabled is None
        else llm_clarify_enabled
    )

    def _clarify(state: OrchestratorState) -> dict[str, Any]:
        return maybe_llm_clarify(
            state, llm_provider=llm_provider, enabled=enabled
        )

    def _invoke(state: OrchestratorState) -> dict[str, Any]:
        return invoke_specialist(state, agents=agents)

    return {
        "filter_available": filter_available,
        "select_agent": select_agent,
        "maybe_llm_clarify": _clarify,
        "invoke_specialist": _invoke,
        "maybe_allowlisted_handoff": maybe_allowlisted_handoff,
        "normalize_envelope": normalize_envelope,
    }
