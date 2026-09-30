"""Offboarding Agent — reads + confirmation-gated writes."""

from __future__ import annotations

from app.ai.agents.offboarding.agent import OffboardingAgent
from app.ai.agents.offboarding.exceptions import (
    OffboardingAgentAuthorizationError,
    OffboardingAgentError,
    OffboardingAgentValidationError,
)
from app.ai.agents.offboarding.schemas import (
    OFFBOARDING_AGENT_ID,
    OffboardingAgentAnswer,
    OffboardingAgentRequest,
    OffboardingAgentUsage,
    PendingConfirmationInfo,
)
from app.ai.agents.offboarding.service import build_offboarding_agent

__all__ = [
    "OFFBOARDING_AGENT_ID",
    "OffboardingAgent",
    "OffboardingAgentAnswer",
    "OffboardingAgentAuthorizationError",
    "OffboardingAgentError",
    "OffboardingAgentRequest",
    "OffboardingAgentUsage",
    "OffboardingAgentValidationError",
    "PendingConfirmationInfo",
    "build_offboarding_agent",
]
