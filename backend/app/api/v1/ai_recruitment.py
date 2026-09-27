"""HTTP API for the Recruitment Agent (read + confirmation-gated writes)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.ai.agents.recruitment import (
    RecruitmentAgent,
    RecruitmentAgentError,
    RecruitmentAgentRequest,
    RecruitmentAgentValidationError,
)
from app.ai.agents.recruitment.schemas import PendingConfirmationInfo
from app.ai.core.context.dependencies import get_ai_execution_context
from app.ai.core.context.models import AIExecutionContext
from app.ai.core.llm import get_llm_provider
from app.core.database import get_db
from app.modules.employees.dependencies import get_employee_service
from app.modules.employees.service import EmployeeService
from app.modules.identity.dependencies import require_permissions
from app.modules.identity.models import User
from app.modules.interviews.dependencies import (
    get_interview_meeting_service,
    get_interview_service,
)
from app.modules.interviews.meeting_service import InterviewMeetingService
from app.modules.interviews.service import InterviewService
from app.modules.recruitment.dependencies import get_application_service, get_job_service
from app.modules.recruitment.application_service import ApplicationService
from app.modules.recruitment.service import JobService

router = APIRouter(prefix="/ai/recruitment", tags=["AI Recruitment"])


class RecruitmentAskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=4000)


class RecruitmentConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation_token: str = Field(min_length=10, max_length=8000)


class RecruitmentUsageResponse(BaseModel):
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


class RecruitmentAskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    model: str
    tool_names_called: list[str] = Field(default_factory=list)
    usage: RecruitmentUsageResponse | None = None
    pending_confirmation: PendingConfirmationResponse | None = None


def get_recruitment_agent(
    db: Session = Depends(get_db),
    job_service: JobService = Depends(get_job_service),
    application_service: ApplicationService = Depends(get_application_service),
    interview_service: InterviewService = Depends(get_interview_service),
    meeting_service: InterviewMeetingService = Depends(get_interview_meeting_service),
    employee_service: EmployeeService = Depends(get_employee_service),
) -> RecruitmentAgent:
    """Build RecruitmentAgent from Core HR services + LLM (overridable in tests)."""

    def _get_user(user_id: int) -> User | None:
        return db.query(User).filter(User.id == user_id).first()

    return RecruitmentAgent(
        llm_provider=get_llm_provider(),
        job_service=job_service,
        application_service=application_service,
        interview_service=interview_service,
        meeting_service=meeting_service,
        employee_service=employee_service,
        get_user=_get_user,
        db=db,
    )


def _to_response(result) -> RecruitmentAskResponse:
    usage = None
    if result.usage is not None:
        usage = RecruitmentUsageResponse(
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
    return RecruitmentAskResponse(
        answer=result.answer,
        model=result.model,
        tool_names_called=result.tool_names_called,
        usage=usage,
        pending_confirmation=pending,
    )


@router.post("/ask", response_model=RecruitmentAskResponse)
def ask_recruitment(
    payload: RecruitmentAskRequest,
    _: User = Depends(require_permissions("recruitment:read")),
    context: AIExecutionContext = Depends(get_ai_execution_context),
    agent: RecruitmentAgent = Depends(get_recruitment_agent),
) -> RecruitmentAskResponse:
    try:
        result = agent.ask(
            RecruitmentAgentRequest(question=payload.question, context=context)
        )
    except RecruitmentAgentValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc
    except RecruitmentAgentError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to answer the recruitment question right now.",
        ) from exc
    return _to_response(result)


@router.post("/confirm", response_model=RecruitmentAskResponse)
def confirm_recruitment(
    payload: RecruitmentConfirmRequest,
    _: User = Depends(require_permissions("recruitment:write")),
    context: AIExecutionContext = Depends(get_ai_execution_context),
    agent: RecruitmentAgent = Depends(get_recruitment_agent),
) -> RecruitmentAskResponse:
    try:
        result = agent.confirm(token=payload.confirmation_token, context=context)
    except RecruitmentAgentValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        ) from exc
    except RecruitmentAgentError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=exc.message if getattr(exc, "message", None) else str(exc),
        ) from exc
    return _to_response(result)
