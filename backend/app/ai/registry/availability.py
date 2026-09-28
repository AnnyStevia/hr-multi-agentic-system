"""Permission-based agent availability (not business authorization)."""

from __future__ import annotations

from app.ai.core.context.models import AIExecutionContext
from app.ai.registry.definitions import AgentDefinition
from app.ai.registry.registry import REGISTERED_AGENTS


def is_agent_available(definition: AgentDefinition, context: AIExecutionContext) -> bool:
    """True if the user may invoke this agent (HTTP-gate aligned).

    Does not decide what operations they may perform inside the agent.

    Onboarding is special: employees lack ``onboarding:read`` by design, so the
    agent is available when ``employee_id`` is present OR the user has
    ``onboarding:read`` (HR/Admin). Candidates with neither are unavailable.
    """
    if definition.id == "onboarding":
        if context.employee_id is not None:
            return True
        return "onboarding:read" in context.permission_names
    return bool(context.permission_names & definition.required_permissions_any)


def get_available_agents(context: AIExecutionContext) -> tuple[AgentDefinition, ...]:
    """Return registered agents the current user is allowed to invoke."""
    return tuple(
        agent for agent in REGISTERED_AGENTS if is_agent_available(agent, context)
    )
