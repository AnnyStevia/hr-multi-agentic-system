"""Schemas for the RAG query pipeline (no answer generation)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.ai.core.context.models import AIExecutionContext
from app.ai.rag.retrieval.schemas import HybridRetrievalHit


class RAGQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    query: str
    context: AIExecutionContext
    top_k: int | None = None


class RAGContextItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: int
    company_document_id: int
    content: str
    page_start: int
    page_end: int
    chunk_index: int
    content_hash: str
    metadata: dict[str, Any]
    vector_similarity: float | None = None
    fts_rank: float | None = None
    rrf_score: float


class RAGQueryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    retrieval_count: int = Field(ge=0)
    selected_context_count: int = Field(ge=0)
    has_context: bool
    results: list[HybridRetrievalHit]
    context: list[RAGContextItem]
    embedding_model: str
    embedding_dimensions: int
