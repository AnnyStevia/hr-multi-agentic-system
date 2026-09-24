"""Schemas for grounded RAG generation (Phase 5.8)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.ai.core.context.models import AIExecutionContext
from app.ai.rag.query.schemas import RAGQueryResult


class RAGGenerationRequest(BaseModel):
    """Generation input — context must come from an authorized RAGQueryResult."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    query_result: RAGQueryResult
    context: AIExecutionContext


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    citation_id: int
    chunk_id: int
    company_document_id: int
    page_start: int
    page_end: int
    document_name: str | None = None
    content_hash: str


class GenerationUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int | None = None
    output_tokens: int | None = None
    thinking_tokens: int | None = None
    total_tokens: int | None = None


class RAGAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    has_context: bool
    retrieval_count: int = Field(ge=0)
    selected_context_count: int = Field(ge=0)
    model: str
    usage: GenerationUsage | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
