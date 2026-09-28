"""Training Agent — scoped reads + confirmation-gated writes over TrainingService."""

from __future__ import annotations

from app.ai.agents.training.agent import TrainingAgent
from app.ai.agents.training.exceptions import (
    TrainingAgentError,
    TrainingAgentValidationError,
)
from app.ai.agents.training.schemas import (
    PendingConfirmationInfo,
    TrainingAgentAnswer,
    TrainingAgentRequest,
    TrainingAgentUsage,
)
from app.ai.agents.training.service import build_training_agent

__all__ = [
    "PendingConfirmationInfo",
    "TrainingAgent",
    "TrainingAgentAnswer",
    "TrainingAgentError",
    "TrainingAgentRequest",
    "TrainingAgentUsage",
    "TrainingAgentValidationError",
    "build_training_agent",
]
