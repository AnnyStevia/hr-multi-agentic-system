"""HTTP API for the Training Agent (reads + confirmation-gated writes)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.ai.agents.training import (
    TrainingAgent,
    TrainingAgentError,
    TrainingAgentRequest,
    TrainingAgentValidationError,
    build_training_agent,
)
from app.ai.agents.training.schemas import PendingConfirmationInfo
from app.ai.core.context.dependencies import get_ai_execution_context
from app.ai.core.context.models import AIExecutionContext
from app.ai.core.llm import get_llm_provider
from app.core.database import get_db
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User
from app.modules.training.dependencies import get_training_service
from app.modules.training.service import TrainingService

router = APIRouter(prefix="/ai/training", tags=["AI Training"])


class TrainingAskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=4000)


class TrainingConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation_token: str = Field(min_length=10, max_length=8000)


class TrainingUsageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int | None = None
    output_tokens: int | None = None
    thinking_tokens: int | None = None
    total_tokens: int | None = None


class PendingConfirmationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    tool_name: str
    summary: str
    expires_at: int


class TrainingAskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    model: str
    tool_names_called: list[str] = Field(default_factory=list)
    usage: TrainingUsageResponse | None = None
    pending_confirmation: PendingConfirmationResponse | None = None


def get_training_agent(
    db: Session = Depends(get_db),
    training_service: TrainingService = Depends(get_training_service),
) -> TrainingAgent:
    return build_training_agent(
        llm_provider=get_llm_provider(),
        training_service=training_service,
        db=db,
    )


def _to_response(result) -> TrainingAskResponse:
    usage = None
    if result.usage is not None:
        usage = TrainingUsageResponse(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            thinking_tokens=result.usage.thinking_tokens,
            total_tokens=result.usage.total_tokens,
        )
    pending = None
    if result.pending_confirmation is not None:
        pc: PendingConfirmationInfo = result.pending_confirmation
        pending = PendingConfirmationResponse(
            token=pc.token,
            tool_name=pc.tool_name,
            summary=pc.summary,
            expires_at=pc.expires_at,
        )
    return TrainingAskResponse(
        answer=result.answer,
        model=result.model,
        tool_names_called=result.tool_names_called,
        usage=usage,
        pending_confirmation=pending,
    )


@router.post("/ask", response_model=TrainingAskResponse)
def ask_training(
    payload: TrainingAskRequest,
    _: User = Depends(get_current_user),
    context: AIExecutionContext = Depends(get_ai_execution_context),
    agent: TrainingAgent = Depends(get_training_agent),
) -> TrainingAskResponse:
    try:
        result = agent.ask(
            TrainingAgentRequest(question=payload.question, context=context)
        )
    except TrainingAgentValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc
    except TrainingAgentError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to answer the training question right now.",
        ) from exc
    return _to_response(result)


@router.post("/confirm", response_model=TrainingAskResponse)
def confirm_training(
    payload: TrainingConfirmRequest,
    _: User = Depends(get_current_user),
    context: AIExecutionContext = Depends(get_ai_execution_context),
    agent: TrainingAgent = Depends(get_training_agent),
) -> TrainingAskResponse:
    """Authenticated confirm — tool metadata enforces self vs HR write gates."""
    try:
        result = agent.confirm(token=payload.confirmation_token, context=context)
    except TrainingAgentValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        ) from exc
    except TrainingAgentError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to complete the confirmed training action right now.",
        ) from exc
    return _to_response(result)
