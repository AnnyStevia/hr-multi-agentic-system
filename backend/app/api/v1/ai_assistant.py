"""Unified HR Assistant ask gateway — LangGraph orchestrator → specialist agents."""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

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
from app.ai.history.service import ChatHistoryService, ConversationNotFoundError
from app.ai.orchestration.graph import SpecialistAgents, run_assistant_orchestration
from app.api.v1.ai_documents import get_documents_agent
from app.api.v1.ai_knowledge import get_knowledge_agent
from app.api.v1.ai_leave import get_leave_agent
from app.api.v1.ai_offboarding import get_offboarding_agent
from app.api.v1.ai_onboarding import get_onboarding_agent
from app.api.v1.ai_recruitment import get_recruitment_agent
from app.api.v1.ai_training import get_training_agent
from app.core.database import get_db
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User

router = APIRouter(prefix="/ai/assistant", tags=["AI Assistant"])
logger = logging.getLogger(__name__)

AssistantStatus = Literal["completed", "clarification_required", "unavailable"]


class AssistantAskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None


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
    conversation_id: int | None = None
    message_id: int | None = None


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


def _persist_error_stub(
    history: ChatHistoryService,
    conversation,
    content: str,
) -> None:
    try:
        history.append_error_assistant(conversation=conversation, content=content)
        history.commit_quietly()
    except Exception:
        logger.exception("Chat history error stub persistence failed")


@router.post("/ask", response_model=AssistantAskResponse)
def ask_assistant(
    payload: AssistantAskRequest,
    _: User = Depends(get_current_user),
    context: AIExecutionContext = Depends(get_ai_execution_context),
    db: Session = Depends(get_db),
    knowledge_agent: KnowledgeAgent = Depends(get_knowledge_agent),
    leave_agent: LeaveAgent = Depends(get_leave_agent),
    recruitment_agent: RecruitmentAgent = Depends(get_recruitment_agent),
    onboarding_agent: OnboardingAgent = Depends(get_onboarding_agent),
    training_agent: TrainingAgent = Depends(get_training_agent),
    documents_agent: DocumentsAgent = Depends(get_documents_agent),
    offboarding_agent: OffboardingAgent = Depends(get_offboarding_agent),
) -> AssistantAskResponse:
    """Unified ask via LangGraph: availability → route → one specialist (no confirm writes)."""
    history = ChatHistoryService(db)
    conversation = None
    try:
        conversation, _user_msg = history.begin_turn(
            context=context,
            message=payload.message,
            conversation_id=payload.conversation_id,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        ) from exc
    except Exception:
        logger.exception("Chat history begin_turn failed; continuing without persistence")
        conversation = None

    agents = SpecialistAgents(
        knowledge=knowledge_agent,
        leave=leave_agent,
        recruitment=recruitment_agent,
        onboarding=onboarding_agent,
        training=training_agent,
        documents=documents_agent,
        offboarding=offboarding_agent,
    )

    def _on_hard_failure(user_message: str) -> None:
        if conversation is not None:
            _persist_error_stub(history, conversation, user_message)

    try:
        result = run_assistant_orchestration(
            message=payload.message,
            context=context,
            agents=agents,
            llm_provider=get_llm_provider(),
        )
    except KnowledgeAgentValidationError as exc:
        _on_hard_failure("Unable to process that knowledge request.")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc
    except KnowledgeAgentError as exc:
        _on_hard_failure("Unable to answer from company knowledge right now.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to answer from company knowledge right now.",
        ) from exc
    except LeaveAgentValidationError as exc:
        _on_hard_failure("Unable to process that leave request.")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc
    except LeaveAgentError as exc:
        _on_hard_failure("Unable to answer the leave question right now.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to answer the leave question right now.",
        ) from exc
    except RecruitmentAgentValidationError as exc:
        _on_hard_failure("Unable to process that recruitment request.")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc
    except RecruitmentAgentError as exc:
        _on_hard_failure("Unable to answer the recruitment question right now.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to answer the recruitment question right now.",
        ) from exc
    except OnboardingAgentValidationError as exc:
        _on_hard_failure("Unable to process that onboarding request.")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc
    except OnboardingAgentError as exc:
        _on_hard_failure("Unable to answer the onboarding question right now.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to answer the onboarding question right now.",
        ) from exc
    except TrainingAgentValidationError as exc:
        _on_hard_failure("Unable to process that training request.")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc
    except TrainingAgentError as exc:
        _on_hard_failure("Unable to answer the training question right now.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to answer the training question right now.",
        ) from exc
    except DocumentsAgentAuthorizationError as exc:
        _on_hard_failure("You are not allowed to access this document.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exc.message or "You are not allowed to access this document.",
        ) from exc
    except DocumentsAgentValidationError as exc:
        _on_hard_failure("Unable to process that documents request.")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc
    except DocumentsAgentError as exc:
        _on_hard_failure("Unable to answer the documents question right now.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to answer the documents question right now.",
        ) from exc
    except OffboardingAgentAuthorizationError as exc:
        _on_hard_failure("You are not allowed to perform this offboarding action.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except OffboardingAgentValidationError as exc:
        _on_hard_failure("Unable to process that offboarding request.")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except OffboardingAgentError as exc:
        _on_hard_failure("Unable to answer the offboarding question right now.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to answer the offboarding question right now.",
        ) from exc

    conversation_id: int | None = conversation.id if conversation is not None else None
    message_id: int | None = None
    if conversation is not None:
        try:
            assistant_row = history.append_assistant_from_result(
                conversation=conversation,
                result=result,
            )
            history.commit_quietly()
            conversation_id = conversation.id
            message_id = assistant_row.id
        except Exception:
            logger.exception(
                "Chat history assistant persistence failed after successful ask; "
                "returning ask response without message_id"
            )

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
        conversation_id=conversation_id,
        message_id=message_id,
    )
