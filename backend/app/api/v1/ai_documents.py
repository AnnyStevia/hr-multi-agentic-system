"""HTTP API for the Documents Agent (read-only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.ai.agents.documents import (
    DOCUMENTS_AGENT_ID,
    DocumentsAgent,
    DocumentsAgentError,
    DocumentsAgentRequest,
    DocumentsAgentValidationError,
    build_documents_agent,
)
from app.ai.agents.documents.exceptions import DocumentsAgentAuthorizationError
from app.ai.agents.documents.schemas import (
    DocumentsAgentDocumentAnswer,
    DocumentsAgentDocumentSummary,
)
from app.ai.core.context.dependencies import get_ai_execution_context
from app.ai.core.context.models import AIExecutionContext
from app.ai.core.llm import get_llm_provider
from app.modules.documents.dependencies import (
    get_company_document_service,
    get_document_service,
    get_private_document_service,
)
from app.modules.documents.library_service import (
    CompanyDocumentService,
    PrivateDocumentService,
)
from app.modules.documents.service import DocumentService
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User

router = APIRouter(prefix="/ai/documents", tags=["AI Documents"])


class DocumentsAskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)


class DocumentsUsageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int | None = None
    output_tokens: int | None = None
    thinking_tokens: int | None = None
    total_tokens: int | None = None


class DocumentsCitationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_number: int
    excerpt: str | None = None


class DocumentsSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = ""
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    important_dates: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    document_id: int | None = None
    document_type: str | None = None
    truncated: bool = False


class DocumentsAnswerPayloadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    citations: list[DocumentsCitationResponse] = Field(default_factory=list)
    document_id: int | None = None
    document_type: str | None = None
    truncated: bool = False


class DocumentsAskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    agent_id: str = DOCUMENTS_AGENT_ID
    model: str
    tool_names_called: list[str] = Field(default_factory=list)
    usage: DocumentsUsageResponse | None = None
    pending_confirmation: None = None
    document_summary: DocumentsSummaryResponse | None = None
    document_answer: DocumentsAnswerPayloadResponse | None = None


def get_documents_agent(
    company_documents: CompanyDocumentService = Depends(get_company_document_service),
    employee_documents: DocumentService = Depends(get_document_service),
    private_documents: PrivateDocumentService = Depends(get_private_document_service),
) -> DocumentsAgent:
    return build_documents_agent(
        llm_provider=get_llm_provider(),
        company_documents=company_documents,
        employee_documents=employee_documents,
        private_documents=private_documents,
    )


def _summary_response(
    summary: DocumentsAgentDocumentSummary | None,
) -> DocumentsSummaryResponse | None:
    if summary is None:
        return None
    return DocumentsSummaryResponse(
        title=summary.title,
        summary=summary.summary,
        key_points=list(summary.key_points),
        important_dates=list(summary.important_dates),
        action_items=list(summary.action_items),
        document_id=summary.document_id,
        document_type=summary.document_type,
        truncated=summary.truncated,
    )


def _answer_response(
    payload: DocumentsAgentDocumentAnswer | None,
) -> DocumentsAnswerPayloadResponse | None:
    if payload is None:
        return None
    return DocumentsAnswerPayloadResponse(
        answer=payload.answer,
        citations=[
            DocumentsCitationResponse(
                page_number=c.page_number, excerpt=c.excerpt
            )
            for c in payload.citations
        ],
        document_id=payload.document_id,
        document_type=payload.document_type,
        truncated=payload.truncated,
    )


def _to_response(result) -> DocumentsAskResponse:
    usage = None
    if result.usage is not None:
        usage = DocumentsUsageResponse(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            thinking_tokens=result.usage.thinking_tokens,
            total_tokens=result.usage.total_tokens,
        )
    return DocumentsAskResponse(
        answer=result.answer,
        agent_id=result.agent_id,
        model=result.model,
        tool_names_called=result.tool_names_called,
        usage=usage,
        pending_confirmation=None,
        document_summary=_summary_response(result.document_summary),
        document_answer=_answer_response(result.document_answer),
    )


@router.post("/ask", response_model=DocumentsAskResponse)
def ask_documents(
    payload: DocumentsAskRequest,
    _: User = Depends(get_current_user),
    context: AIExecutionContext = Depends(get_ai_execution_context),
    agent: DocumentsAgent = Depends(get_documents_agent),
) -> DocumentsAskResponse:
    try:
        result = agent.ask(
            DocumentsAgentRequest(question=payload.message, context=context)
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
    return _to_response(result)
