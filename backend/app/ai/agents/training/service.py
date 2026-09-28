"""Training Agent factory helpers (DI stays in the HTTP layer)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.agents.training.agent import TrainingAgent
from app.ai.core.llm.base import LLMProvider
from app.modules.training.service import TrainingService


def build_training_agent(
    *,
    llm_provider: LLMProvider,
    training_service: TrainingService,
    db: Session | None = None,
) -> TrainingAgent:
    """Construct TrainingAgent with reads + confirmation-gated writes."""
    return TrainingAgent(
        llm_provider=llm_provider,
        training_service=training_service,
        db=db,
    )
