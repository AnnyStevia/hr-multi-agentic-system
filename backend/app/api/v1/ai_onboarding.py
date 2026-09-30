"""HTTP API for the Onboarding Agent (reads + confirmation-gated writes)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.ai.agents.onboarding import (
    OnboardingAgent,
    OnboardingAgentError,
    OnboardingAgentRequest,
    OnboardingAgentValidationError,
)
from app.ai.agents.onboarding.schemas import PendingConfirmationInfo
from app.ai.core.context.dependencies import get_ai_execution_context
from app.ai.core.context.models import AIExecutionContext
from app.ai.core.llm import get_llm_provider
from app.ai.history.hooks import resolve_pending_best_effort
from app.core.database import get_db
from app.modules.employees.dependencies import get_employee_service
from app.modules.employees.service import EmployeeService
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User
from app.modules.onboarding.dependencies import get_onboarding_service
from app.modules.onboarding.service import OnboardingService

router = APIRouter(prefix="/ai/onboarding", tags=["AI Onboarding"])


class OnboardingAskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=4000)


class OnboardingConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation_token: str = Field(min_length=10, max_length=8000)


class OnboardingUsageResponse(BaseModel):
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


class OnboardingAskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    model: str
    tool_names_called: list[str] = Field(default_factory=list)
    usage: OnboardingUsageResponse | None = None
    pending_confirmation: PendingConfirmationResponse | None = None


def get_onboarding_agent(
    db: Session = Depends(get_db),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
    employee_service: EmployeeService = Depends(get_employee_service),
) -> OnboardingAgent:
    return OnboardingAgent(
        llm_provider=get_llm_provider(),
        onboarding_service=onboarding_service,
        employee_service=employee_service,
        db=db,
    )


def _to_response(result) -> OnboardingAskResponse:
    usage = None
    if result.usage is not None:
        usage = OnboardingUsageResponse(
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
    return OnboardingAskResponse(
        answer=result.answer,
        model=result.model,
        tool_names_called=result.tool_names_called,
        usage=usage,
        pending_confirmation=pending,
    )


@router.post("/ask", response_model=OnboardingAskResponse)
def ask_onboarding(
    payload: OnboardingAskRequest,
    _: User = Depends(get_current_user),
    context: AIExecutionContext = Depends(get_ai_execution_context),
    agent: OnboardingAgent = Depends(get_onboarding_agent),
) -> OnboardingAskResponse:
    try:
        result = agent.ask(
            OnboardingAgentRequest(question=payload.question, context=context)
        )
    except OnboardingAgentValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc
    except OnboardingAgentError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to answer the onboarding question right now.",
        ) from exc
    return _to_response(result)


@router.post("/confirm", response_model=OnboardingAskResponse)
def confirm_onboarding(
    payload: OnboardingConfirmRequest,
    _: User = Depends(get_current_user),
    context: AIExecutionContext = Depends(get_ai_execution_context),
    db: Session = Depends(get_db),
    agent: OnboardingAgent = Depends(get_onboarding_agent),
) -> OnboardingAskResponse:
    """Authenticated confirm — tool metadata enforces ACK vs HR write gates."""
    try:
        result = agent.confirm(token=payload.confirmation_token, context=context)
    except OnboardingAgentValidationError as exc:
        resolve_pending_best_effort(
            db,
            user_id=context.user_id,
            token=payload.confirmation_token,
            resolved=True,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        ) from exc
    except OnboardingAgentError as exc:
        resolve_pending_best_effort(
            db,
            user_id=context.user_id,
            token=payload.confirmation_token,
            resolved=True,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to complete the confirmed onboarding action right now.",
        ) from exc
    resolve_pending_best_effort(
        db,
        user_id=context.user_id,
        token=payload.confirmation_token,
        resolved=True,
    )
    return _to_response(result)
