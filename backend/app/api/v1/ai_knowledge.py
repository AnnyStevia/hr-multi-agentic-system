"""HTTP API for the Knowledge Agent (company document RAG)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.ai.agents.knowledge import (
    KnowledgeAgent,
    KnowledgeAgentError,
    KnowledgeAgentRequest,
    KnowledgeAgentValidationError,
)
from app.ai.core.context.dependencies import get_ai_execution_context
from app.ai.core.context.models import AIExecutionContext
from app.ai.core.llm import get_llm_provider
from app.ai.rag.embeddings import EmbeddingService, get_embedding_provider
from app.ai.rag.generation import GroundedGenerationService
from app.ai.rag.query import RAGQueryService
from app.ai.rag.retrieval import HybridRetrievalService
from app.core.database import get_db
from app.modules.identity.dependencies import require_permissions
from app.modules.identity.models import User

router = APIRouter(prefix="/ai/knowledge", tags=["AI Knowledge"])


class KnowledgeAskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=20)


class KnowledgeCitationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    citation_id: int
    document_name: str | None = None
    page_start: int
    page_end: int
    company_document_id: int


class KnowledgeUsageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int | None = None
    output_tokens: int | None = None
    thinking_tokens: int | None = None
    total_tokens: int | None = None


class KnowledgeAskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    answer: str
    citations: list[KnowledgeCitationResponse]
    has_context: bool
    retrieval_count: int
    selected_context_count: int
    model: str
    usage: KnowledgeUsageResponse | None = None


def get_knowledge_agent(db: Session = Depends(get_db)) -> KnowledgeAgent:
    """Build KnowledgeAgent from DB + configured providers (overridable in tests)."""
    embedding_service = EmbeddingService(db, get_embedding_provider())
    query_service = RAGQueryService(
        embedding_service=embedding_service,
        hybrid_service=HybridRetrievalService(db),
        db=db,
    )
    generation_service = GroundedGenerationService(
        llm_provider=get_llm_provider(),
        db=db,
    )
    return KnowledgeAgent(
        query_service=query_service,
        generation_service=generation_service,
    )


@router.post("/ask", response_model=KnowledgeAskResponse)
def ask_knowledge(
    payload: KnowledgeAskRequest,
    _: User = Depends(require_permissions("company_documents:read")),
    context: AIExecutionContext = Depends(get_ai_execution_context),
    agent: KnowledgeAgent = Depends(get_knowledge_agent),
) -> KnowledgeAskResponse:
    try:
        result = agent.ask(
            KnowledgeAgentRequest(
                question=payload.question,
                context=context,
                top_k=payload.top_k,
            )
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

    usage = None
    if result.usage is not None:
        usage = KnowledgeUsageResponse(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            thinking_tokens=result.usage.thinking_tokens,
            total_tokens=result.usage.total_tokens,
        )

    return KnowledgeAskResponse(
        query=result.query,
        answer=result.answer,
        citations=[
            KnowledgeCitationResponse(
                citation_id=c.citation_id,
                document_name=c.document_name,
                page_start=c.page_start,
                page_end=c.page_end,
                company_document_id=c.company_document_id,
            )
            for c in result.citations
        ],
        has_context=result.has_context,
        retrieval_count=result.retrieval_count,
        selected_context_count=result.selected_context_count,
        model=result.model,
        usage=usage,
    )
