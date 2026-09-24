"""Typed request/result schemas for secure vector and hybrid retrieval."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.ai.core.context.models import AIExecutionContext


class RetrievalRequest(BaseModel):
    """Retrieval input — identity/auth comes only from AIExecutionContext."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    query_embedding: list[float] = Field(min_length=1)
    context: AIExecutionContext
    top_k: int | None = None


class RetrievalHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: int
    company_document_id: int
    content: str
    similarity: float
    page_start: int
    page_end: int
    chunk_index: int
    content_hash: str
    metadata: dict[str, Any]


class HybridRequest(BaseModel):
    """Hybrid retrieval — caller supplies query text and embedding (no Gemini here)."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    query_text: str
    query_embedding: list[float] = Field(min_length=1)
    context: AIExecutionContext
    top_k: int | None = None


class HybridRetrievalHit(BaseModel):
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
