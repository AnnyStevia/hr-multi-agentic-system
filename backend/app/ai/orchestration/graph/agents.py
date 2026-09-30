"""Specialist agent bundle injected into the orchestrator graph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SpecialistAgents:
    """Duck-typed specialists — orchestrator never aggregates their tools.

    Typed as Any to avoid import cycles with agent modules that depend on
    ``app.ai.orchestration.tool_roundtrip``.
    """

    knowledge: Any
    leave: Any
    recruitment: Any
    onboarding: Any
    training: Any
    documents: Any
    offboarding: Any

    def get(self, agent_id: str) -> Any:
        mapping = {
            "knowledge": self.knowledge,
            "leave": self.leave,
            "recruitment": self.recruitment,
            "onboarding": self.onboarding,
            "training": self.training,
            "documents": self.documents,
            "offboarding": self.offboarding,
        }
        return mapping.get(agent_id)
