"""Unified HR Assistant ask gateway — registry + router + existing agents."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.ai.agents.documents import (
    DocumentsAgent,
    DocumentsAgentError,
    DocumentsAgentRequest,
    DocumentsAgentValidationError,
)
from app.ai.agents.documents.exceptions import DocumentsAgentAuthorizationError
from app.ai.agents.knowledge import (
    KnowledgeAgent,
    KnowledgeAgentError,
    KnowledgeAgentRequest,
    KnowledgeAgentValidationError,
)
from app.ai.agents.leave import (
    LeaveAgent,
    LeaveAgentError,
    LeaveAgentRequest,
    LeaveAgentValidationError,
)
from app.ai.agents.leave.schemas import PendingConfirmationInfo as LeavePendingConfirmation
from app.ai.agents.onboarding import (
    OnboardingAgent,
    OnboardingAgentError,
    OnboardingAgentRequest,
    OnboardingAgentValidationError,
)
from app.ai.agents.onboarding.schemas import (
    PendingConfirmationInfo as OnboardingPendingConfirmation,
)
from app.ai.agents.recruitment import (
    RecruitmentAgent,
    RecruitmentAgentError,
    RecruitmentAgentRequest,
    RecruitmentAgentValidationError,
)
from app.ai.agents.recruitment.schemas import (
    PendingConfirmationInfo as RecruitmentPendingConfirmation,
)
from app.ai.agents.training import (
    TrainingAgent,
    TrainingAgentError,
    TrainingAgentRequest,
    TrainingAgentValidationError,
)
from app.ai.agents.training.schemas import (
    PendingConfirmationInfo as TrainingPendingConfirmation,
)
from app.ai.core.context.dependencies import get_ai_execution_context
from app.ai.core.context.models import AIExecutionContext
from app.ai.registry import get_available_agents
from app.ai.routing import route_message
from app.api.v1.ai_documents import get_documents_agent
from app.api.v1.ai_knowledge import get_knowledge_agent
from app.api.v1.ai_leave import get_leave_agent
from app.api.v1.ai_onboarding import get_onboarding_agent
from app.api.v1.ai_recruitment import get_recruitment_agent
from app.api.v1.ai_training import get_training_agent
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User

router = APIRouter(prefix="/ai/assistant", tags=["AI Assistant"])

AssistantStatus = Literal["completed", "clarification_required", "unavailable"]

_CLARIFY_ANSWER = (
    "I am not sure which assistant should handle this. "
    "Please clarify whether you need company policy knowledge, a specific "
    "document summary or library help, leave help, onboarding support, "
    "training help, or recruitment help."
)

_UNAVAILABLE_ANSWER = (
    "This assistant cannot perform that request with your current access. "
    "If you need help with company knowledge, documents, leave, onboarding, "
    "or training, try rephrasing; recruitment actions require HR or Admin access."
)

_NO_AGENTS_ANSWER = (
    "No AI assistants are available for your account right now. "
    "Contact HR if you believe this is a mistake."
)


class AssistantAskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)


class AssistantCitationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    citation_id: int
    document_name: str | None = None
    page_start: int
    page_end: int
    company_document_id: int


class AssistantPendingConfirmationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    tool_name: str
    summary: str
    expires_at: int


class AssistantUsageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int | None = None
    output_tokens: int | None = None
    thinking_tokens: int | None = None
    total_tokens: int | None = None


class AssistantAskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str | None
    answer: str
    citations: list[AssistantCitationResponse] = Field(default_factory=list)
    pending_confirmation: AssistantPendingConfirmationResponse | None = None
    status: AssistantStatus
    model: str | None = None
    tool_names_called: list[str] = Field(default_factory=list)
    usage: AssistantUsageResponse | None = None


def _pending_from(
    pending: (
        LeavePendingConfirmation
        | RecruitmentPendingConfirmation
        | OnboardingPendingConfirmation
        | TrainingPendingConfirmation
        | None
    ),
) -> AssistantPendingConfirmationResponse | None:
    if pending is None:
        return None
    return AssistantPendingConfirmationResponse(
        token=pending.token,
        tool_name=pending.tool_name,
        summary=pending.summary,
        expires_at=pending.expires_at,
    )


def _usage_from(usage) -> AssistantUsageResponse | None:
    if usage is None:
        return None
    return AssistantUsageResponse(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        thinking_tokens=usage.thinking_tokens,
        total_tokens=usage.total_tokens,
    )


@router.post("/ask", response_model=AssistantAskResponse)
def ask_assistant(
    payload: AssistantAskRequest,
    _: User = Depends(get_current_user),
    context: AIExecutionContext = Depends(get_ai_execution_context),
    knowledge_agent: KnowledgeAgent = Depends(get_knowledge_agent),
    leave_agent: LeaveAgent = Depends(get_leave_agent),
    recruitment_agent: RecruitmentAgent = Depends(get_recruitment_agent),
    onboarding_agent: OnboardingAgent = Depends(get_onboarding_agent),
    training_agent: TrainingAgent = Depends(get_training_agent),
    documents_agent: DocumentsAgent = Depends(get_documents_agent),
) -> AssistantAskResponse:
    """Unified ask: availability → route → existing agent (no confirm writes)."""
    available = get_available_agents(context)
    if not available:
        return AssistantAskResponse(
            agent_id=None,
            answer=_NO_AGENTS_ANSWER,
            status="unavailable",
        )

    decision = route_message(payload.message, available)

    if decision.kind == "clarify":
        return AssistantAskResponse(
            agent_id=None,
            answer=_CLARIFY_ANSWER,
            status="clarification_required",
        )

    if decision.kind == "unavailable":
        return AssistantAskResponse(
            agent_id=None,
            answer=_UNAVAILABLE_ANSWER,
            status="unavailable",
        )

    agent_id = decision.agent_id
    if agent_id is None or agent_id not in {a.id for a in available}:
        # Defensive: never dispatch to an unavailable agent.
        return AssistantAskResponse(
            agent_id=None,
            answer=_UNAVAILABLE_ANSWER,
            status="unavailable",
        )

    question = payload.message.strip()

    if agent_id == "knowledge":
        try:
            result = knowledge_agent.ask(
                KnowledgeAgentRequest(question=question, context=context)
            )
        except KnowledgeAgentValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.message,
            ) from exc
        except KnowledgeAgentError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to answer from company knowledge right now.",
            ) from exc
        return AssistantAskResponse(
            agent_id="knowledge",
            answer=result.answer,
            citations=[
                AssistantCitationResponse(
                    citation_id=c.citation_id,
                    document_name=c.document_name,
                    page_start=c.page_start,
                    page_end=c.page_end,
                    company_document_id=c.company_document_id,
                )
                for c in result.citations
            ],
            pending_confirmation=None,
            status="completed",
            model=result.model,
            usage=_usage_from(result.usage),
        )

    if agent_id == "leave":
        try:
            result = leave_agent.ask(
                LeaveAgentRequest(question=question, context=context)
            )
        except LeaveAgentValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.message,
            ) from exc
        except LeaveAgentError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to answer the leave question right now.",
            ) from exc
        return AssistantAskResponse(
            agent_id="leave",
            answer=result.answer,
            citations=[],
            pending_confirmation=_pending_from(result.pending_confirmation),
            status="completed",
            model=result.model,
            tool_names_called=list(result.tool_names_called),
            usage=_usage_from(result.usage),
        )

    if agent_id == "recruitment":
        try:
            result = recruitment_agent.ask(
                RecruitmentAgentRequest(question=question, context=context)
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
        return AssistantAskResponse(
            agent_id="recruitment",
            answer=result.answer,
            citations=[],
            pending_confirmation=_pending_from(result.pending_confirmation),
            status="completed",
            model=result.model,
            tool_names_called=list(result.tool_names_called),
            usage=_usage_from(result.usage),
        )

    if agent_id == "onboarding":
        try:
            result = onboarding_agent.ask(
                OnboardingAgentRequest(question=question, context=context)
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
        return AssistantAskResponse(
            agent_id="onboarding",
            answer=result.answer,
            citations=[],
            pending_confirmation=_pending_from(result.pending_confirmation),
            status="completed",
            model=result.model,
            tool_names_called=list(result.tool_names_called),
            usage=_usage_from(result.usage),
        )

    if agent_id == "training":
        try:
            result = training_agent.ask(
                TrainingAgentRequest(question=question, context=context)
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
        return AssistantAskResponse(
            agent_id="training",
            answer=result.answer,
            citations=[],
            pending_confirmation=_pending_from(result.pending_confirmation),
            status="completed",
            model=result.model,
            tool_names_called=list(result.tool_names_called),
            usage=_usage_from(result.usage),
        )

    if agent_id == "documents":
        try:
            result = documents_agent.ask(
                DocumentsAgentRequest(question=question, context=context)
            )
        except DocumentsAgentAuthorizationError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=exc.message or "You are not allowed to access this document.",
            ) from exc
        except DocumentsAgentValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.message,
            ) from exc
        except DocumentsAgentError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to answer the documents question right now.",
            ) from exc
        return AssistantAskResponse(
            agent_id="documents",
            answer=result.answer,
            citations=[],
            pending_confirmation=None,
            status="completed",
            model=result.model,
            tool_names_called=list(result.tool_names_called),
            usage=_usage_from(result.usage),
        )

    return AssistantAskResponse(
        agent_id=None,
        answer=_CLARIFY_ANSWER,
        status="clarification_required",
    )
