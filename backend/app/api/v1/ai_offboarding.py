"""HTTP API for the Offboarding Agent (reads + confirmation-gated writes)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.ai.agents.offboarding import (
    OFFBOARDING_AGENT_ID,
    OffboardingAgent,
    OffboardingAgentError,
    OffboardingAgentRequest,
    OffboardingAgentValidationError,
    build_offboarding_agent,
)
from app.ai.agents.offboarding.exceptions import OffboardingAgentAuthorizationError
from app.ai.agents.offboarding.schemas import PendingConfirmationInfo
from app.ai.core.context.dependencies import get_ai_execution_context
from app.ai.core.context.models import AIExecutionContext
from app.ai.core.llm import get_llm_provider
from app.ai.history.hooks import resolve_pending_best_effort
from app.core.database import get_db
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User

router = APIRouter(prefix="/ai/offboarding", tags=["AI Offboarding"])


class OffboardingAskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)


class OffboardingConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation_token: str = Field(min_length=10, max_length=8000)


class OffboardingUsageResponse(BaseModel):
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


class OffboardingAskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    agent_id: str = OFFBOARDING_AGENT_ID
    model: str
    tool_names_called: list[str] = Field(default_factory=list)
    usage: OffboardingUsageResponse | None = None
    pending_confirmation: PendingConfirmationResponse | None = None


def get_offboarding_agent(db: Session = Depends(get_db)) -> OffboardingAgent:
    return build_offboarding_agent(llm_provider=get_llm_provider(), db=db)


def _to_response(result) -> OffboardingAskResponse:
    usage = None
    if result.usage is not None:
        usage = OffboardingUsageResponse(
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
    return OffboardingAskResponse(
        answer=result.answer,
        agent_id=result.agent_id,
        model=result.model,
        tool_names_called=list(result.tool_names_called),
        usage=usage,
        pending_confirmation=pending,
    )


@router.post("/ask", response_model=OffboardingAskResponse)
def ask_offboarding(
    payload: OffboardingAskRequest,
    _: User = Depends(get_current_user),
    context: AIExecutionContext = Depends(get_ai_execution_context),
    agent: OffboardingAgent = Depends(get_offboarding_agent),
) -> OffboardingAskResponse:
    try:
        result = agent.ask(
            OffboardingAgentRequest(question=payload.message, context=context)
        )
    except OffboardingAgentAuthorizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except OffboardingAgentValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except OffboardingAgentError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    return _to_response(result)


@router.post("/confirm", response_model=OffboardingAskResponse)
def confirm_offboarding(
    payload: OffboardingConfirmRequest,
    _: User = Depends(get_current_user),
    context: AIExecutionContext = Depends(get_ai_execution_context),
    db: Session = Depends(get_db),
    agent: OffboardingAgent = Depends(get_offboarding_agent),
) -> OffboardingAskResponse:
    """Authenticated confirm — tool metadata enforces HR vs employee write gates."""
    try:
        result = agent.confirm(token=payload.confirmation_token, context=context)
    except OffboardingAgentAuthorizationError as exc:
        resolve_pending_best_effort(
            db,
            user_id=context.user_id,
            token=payload.confirmation_token,
            resolved=True,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except OffboardingAgentValidationError as exc:
        resolve_pending_best_effort(
            db,
            user_id=context.user_id,
            token=payload.confirmation_token,
            resolved=True,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=exc.message
        ) from exc
    except OffboardingAgentError as exc:
        resolve_pending_best_effort(
            db,
            user_id=context.user_id,
            token=payload.confirmation_token,
            resolved=True,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to complete the confirmed offboarding action right now.",
        ) from exc
    resolve_pending_best_effort(
        db,
        user_id=context.user_id,
        token=payload.confirmation_token,
        resolved=True,
    )
    return _to_response(result)
