"""Agent registry: definitions + permission-based availability."""

from __future__ import annotations

from app.ai.registry.availability import get_available_agents, is_agent_available
from app.ai.registry.definitions import AgentDefinition
from app.ai.registry.registry import (
    KNOWLEDGE_AGENT,
    LEAVE_AGENT,
    ONBOARDING_AGENT,
    RECRUITMENT_AGENT,
    REGISTERED_AGENTS,
    TRAINING_AGENT,
    get_agent_definition,
    list_registered_agents,
)

__all__ = [
    "AgentDefinition",
    "KNOWLEDGE_AGENT",
    "LEAVE_AGENT",
    "ONBOARDING_AGENT",
    "RECRUITMENT_AGENT",
    "TRAINING_AGENT",
    "REGISTERED_AGENTS",
    "get_agent_definition",
    "get_available_agents",
    "is_agent_available",
    "list_registered_agents",
]
