"""Allowlisted multi-agent handoffs (Orc.4).

Default path remains single-specialist. Handoffs are never free-form tool sharing.
"""

from __future__ import annotations

# Explicit (source_agent_id, target_agent_id) pairs permitted for future sequential
# handoffs. Empty by default so MVP behaviour is unchanged.
ALLOWLISTED_HANDOFFS: frozenset[tuple[str, str]] = frozenset(
    {
        # Example (disabled until product enables): offboarding readiness Q that
        # also needs a handbook cite → Knowledge after Offboarding answers.
        # ("offboarding", "knowledge"),
    }
)


def is_handoff_allowed(*, source_agent_id: str, target_agent_id: str) -> bool:
    """True only for explicitly allowlisted specialist→specialist hops."""
    if not source_agent_id or not target_agent_id:
        return False
    if source_agent_id == target_agent_id:
        return False
    return (source_agent_id, target_agent_id) in ALLOWLISTED_HANDOFFS
