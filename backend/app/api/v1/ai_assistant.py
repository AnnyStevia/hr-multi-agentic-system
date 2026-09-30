"""Unified HR Assistant ask gateway — LangGraph orchestrator → specialist agents."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.ai.agents.documents import (
    DocumentsAgent,
    DocumentsAgentError,
    DocumentsAgentValidationError,
)
from app.ai.agents.documents.exceptions import DocumentsAgentAuthorizationError
from app.ai.agents.knowledge import (
    KnowledgeAgent,
    KnowledgeAgentError,
    KnowledgeAgentValidationError,
)
from app.ai.agents.leave import LeaveAgent, LeaveAgentError, LeaveAgentValidationError
from app.ai.agents.offboarding import (
    OffboardingAgent,
    OffboardingAgentError,
    OffboardingAgentValidationError,
)
from app.ai.agents.offboarding.exceptions import OffboardingAgentAuthorizationError
from app.ai.agents.onboarding import (
    OnboardingAgent,
    OnboardingAgentError,
    OnboardingAgentValidationError,
)
from app.ai.agents.recruitment import (
    RecruitmentAgent,
    RecruitmentAgentError,
    RecruitmentAgentValidationError,
)
from app.ai.agents.training import (
    TrainingAgent,
    TrainingAgentError,
    TrainingAgentValidationError,
)
from app.ai.core.context.dependencies import get_ai_execution_context
from app.ai.core.context.models import AIExecutionContext
from app.ai.core.llm import get_llm_provider
from app.ai.orchestration.graph import SpecialistAgents, run_assistant_orchestration
from app.api.v1.ai_documents import get_documents_agent
from app.api.v1.ai_knowledge import get_knowledge_agent
from app.api.v1.ai_leave import get_leave_agent
from app.api.v1.ai_offboarding import get_offboarding_agent
from app.api.v1.ai_onboarding import get_onboarding_agent
from app.api.v1.ai_recruitment import get_recruitment_agent
from app.api.v1.ai_training import get_training_agent
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User

router = APIRouter(prefix="/ai/assistant", tags=["AI Assistant"])

AssistantStatus = Literal["completed", "clarification_required", "unavailable"]


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


def _pending_response(pending: dict | None) -> AssistantPendingConfirmationResponse | None:
    if not pending:
        return None
    return AssistantPendingConfirmationResponse(
        token=pending["token"],
        tool_name=pending["tool_name"],
        summary=pending["summary"],
        expires_at=pending["expires_at"],
    )


def _usage_response(usage: dict | None) -> AssistantUsageResponse | None:
    if not usage:
        return None
    return AssistantUsageResponse(
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        thinking_tokens=usage.get("thinking_tokens"),
        total_tokens=usage.get("total_tokens"),
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
    offboarding_agent: OffboardingAgent = Depends(get_offboarding_agent),
) -> AssistantAskResponse:
    """Unified ask via LangGraph: availability → route → one specialist (no confirm writes)."""
    agents = SpecialistAgents(
        knowledge=knowledge_agent,
        leave=leave_agent,
        recruitment=recruitment_agent,
        onboarding=onboarding_agent,
        training=training_agent,
        documents=documents_agent,
        offboarding=offboarding_agent,
    )
    try:
        result = run_assistant_orchestration(
            message=payload.message,
            context=context,
            agents=agents,
            llm_provider=get_llm_provider(),
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
    except OffboardingAgentAuthorizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except OffboardingAgentValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except OffboardingAgentError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to answer the offboarding question right now.",
        ) from exc

    return AssistantAskResponse(
        agent_id=result.agent_id,
        answer=result.answer,
        citations=[
            AssistantCitationResponse(
                citation_id=c["citation_id"],
                document_name=c.get("document_name"),
                page_start=c["page_start"],
                page_end=c["page_end"],
                company_document_id=c["company_document_id"],
            )
            for c in result.citations
        ],
        pending_confirmation=_pending_response(result.pending_confirmation),
        status=result.status,
        model=result.model,
        tool_names_called=list(result.tool_names_called),
        usage=_usage_response(result.usage),
    )
