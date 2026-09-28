"""Routing decision schemas (no tools, no auth)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RouteKind = Literal["agent", "clarify", "unavailable"]


@dataclass(frozen=True)
class RouteDecision:
    """Outcome of lightweight intent routing over available agents only."""

    kind: RouteKind
    agent_id: str | None
    reason: str
