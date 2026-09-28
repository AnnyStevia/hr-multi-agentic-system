"""Lightweight assistant routing (deterministic)."""

from __future__ import annotations

from app.ai.routing.router import route_message
from app.ai.routing.schemas import RouteDecision, RouteKind

__all__ = [
    "RouteDecision",
    "RouteKind",
    "route_message",
]
