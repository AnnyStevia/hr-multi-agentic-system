"""Code-based agent definition (not persisted)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentDefinition:
    """Static catalog entry for an implemented AI agent.

    Availability is decided separately via ``required_permissions_any`` against
    ``AIExecutionContext.permission_names``. This does not encode business
    authorization (approve leave, reject candidates, etc.).
    """

    id: str
    display_name: str
    description: str
    intents: tuple[str, ...]
    required_permissions_any: frozenset[str]
    supports_confirmation: bool
