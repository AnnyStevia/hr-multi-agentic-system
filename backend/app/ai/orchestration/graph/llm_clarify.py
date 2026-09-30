"""Optional constrained LLM disambiguation among available agents (Orc.3)."""

from __future__ import annotations

import re

from app.ai.core.llm.base import LLMMessage, LLMProvider
from app.ai.registry.definitions import AgentDefinition

_CLARIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "agent_id": {
            "type": ["string", "null"],
            "description": "One of the allowed agent ids, or null if still ambiguous.",
        },
        "confidence": {
            "type": "string",
            "enum": ["high", "low"],
        },
    },
    "required": ["agent_id", "confidence"],
    "additionalProperties": False,
}


def try_llm_select_agent(
    *,
    provider: LLMProvider,
    message: str,
    available: list[AgentDefinition],
) -> str | None:
    """Ask LLMProvider to pick one available agent id, or None if unclear.

    Never invents agents outside ``available``. Low confidence / null → None.
    """
    if not available or not (message or "").strip():
        return None
    allowed = {a.id for a in available}
    catalog = "\n".join(
        f"- {a.id}: {a.display_name} — {a.description[:160]}" for a in available
    )
    system = (
        "You route a single HR assistant question to exactly one specialist. "
        "You may ONLY choose an agent_id from the Allowed list. "
        "If the question is ambiguous, multi-intent, or a general prepare/everything "
        "request spanning domains, return agent_id null and confidence low. "
        "Do not invent tools or claim writes."
    )
    user = (
        f"Allowed agents:\n{catalog}\n\n"
        f"User message:\n{message.strip()}\n\n"
        "Return JSON with agent_id (allowed id or null) and confidence."
    )
    try:
        result = provider.generate_structured(
            [
                LLMMessage(role="system", content=system),
                LLMMessage(role="user", content=user),
            ],
            schema=_CLARIFY_SCHEMA,
            temperature=0.0,
            max_tokens=200,
        )
    except Exception:
        return None

    data = result.data or {}
    agent_id = data.get("agent_id")
    confidence = str(data.get("confidence") or "").lower()
    if confidence != "high":
        return None
    if not isinstance(agent_id, str):
        return None
    agent_id = agent_id.strip().lower()
    # Defensive: strip accidental quotes/punctuation from model output.
    agent_id = re.sub(r"[^a-z_]", "", agent_id)
    if agent_id not in allowed:
        return None
    return agent_id
