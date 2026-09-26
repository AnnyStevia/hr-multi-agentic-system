"""HTTP API for the Recruitment Agent (read-only HR recruitment Q&A)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.ai.agents.recruitment import (
    RecruitmentAgent,
    RecruitmentAgentError,
    RecruitmentAgentRequest,
    RecruitmentAgentValidationError,
)
from app.ai.core.context.dependencies import get_ai_execution_context
from app.ai.core.context.models import AIExecutionContext
from app.ai.core.llm import get_llm_provider
from app.modules.identity.dependencies import require_permissions
from app.modules.identity.models import User
from app.modules.interviews.dependencies import get_interview_service
from app.modules.interviews.service import InterviewService
from app.modules.recruitment.dependencies import get_application_service, get_job_service
from app.modules.recruitment.application_service import ApplicationService
from app.modules.recruitment.service import JobService

router = APIRouter(prefix="/ai/recruitment", tags=["AI Recruitment"])


class RecruitmentAskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=4000)


class RecruitmentUsageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int | None = None
    output_tokens: int | None = None
    thinking_tokens: int | None = None
    total_tokens: int | None = None


class RecruitmentAskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    model: str
    tool_names_called: list[str] = Field(default_factory=list)
    usage: RecruitmentUsageResponse | None = None


def get_recruitment_agent(
    job_service: JobService = Depends(get_job_service),
    application_service: ApplicationService = Depends(get_application_service),
    interview_service: InterviewService = Depends(get_interview_service),
) -> RecruitmentAgent:
    """Build RecruitmentAgent from Core HR services + LLM (overridable in tests)."""
    return RecruitmentAgent(
        llm_provider=get_llm_provider(),
        job_service=job_service,
        application_service=application_service,
        interview_service=interview_service,
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

    usage = None
    if result.usage is not None:
        usage = RecruitmentUsageResponse(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            thinking_tokens=result.usage.thinking_tokens,
            total_tokens=result.usage.total_tokens,
        )

    return RecruitmentAskResponse(
        answer=result.answer,
        model=result.model,
        tool_names_called=result.tool_names_called,
        usage=usage,
    )
