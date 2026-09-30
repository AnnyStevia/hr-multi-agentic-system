"""Compile the minimal unified-assistant LangGraph."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.ai.core.llm.base import LLMProvider
from app.ai.orchestration.graph.agents import SpecialistAgents
from app.ai.orchestration.graph.nodes import (
    build_node_fns,
    route_after_clarify,
    route_after_select,
)
from app.ai.orchestration.graph.state import OrchestratorState


def build_assistant_graph(
    *,
    agents: SpecialistAgents,
    llm_provider: LLMProvider | None = None,
    llm_clarify_enabled: bool | None = None,
):
    """Context → available → deterministic select → optional LLM clarify → one specialist.

    Does not register domain tools on the graph. Confirm writes stay on domain endpoints.
    """
    fns = build_node_fns(
        agents=agents,
        llm_provider=llm_provider,
        llm_clarify_enabled=llm_clarify_enabled,
    )
    graph = StateGraph(OrchestratorState)
    graph.add_node("filter_available", fns["filter_available"])
    graph.add_node("select_agent", fns["select_agent"])
    graph.add_node("maybe_llm_clarify", fns["maybe_llm_clarify"])
    graph.add_node("invoke_specialist", fns["invoke_specialist"])
    graph.add_node("maybe_allowlisted_handoff", fns["maybe_allowlisted_handoff"])
    graph.add_node("normalize_envelope", fns["normalize_envelope"])

    graph.add_edge(START, "filter_available")
    graph.add_edge("filter_available", "select_agent")
    graph.add_conditional_edges(
        "select_agent",
        route_after_select,
        {
            "invoke": "invoke_specialist",
            "soft_outcome": "maybe_llm_clarify",
        },
    )
    graph.add_conditional_edges(
        "maybe_llm_clarify",
        route_after_clarify,
        {
            "invoke": "invoke_specialist",
            "soft_outcome": "normalize_envelope",
        },
    )
    graph.add_edge("invoke_specialist", "maybe_allowlisted_handoff")
    graph.add_edge("maybe_allowlisted_handoff", "normalize_envelope")
    graph.add_edge("normalize_envelope", END)
    return graph.compile()
