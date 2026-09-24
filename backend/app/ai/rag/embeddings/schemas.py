"""Structured results for embedding operations (no SDK types)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EmbeddingUsage(BaseModel):
    model_config = {"extra": "forbid"}

    input_tokens: int | None = None
    total_tokens: int | None = None


class EmbeddingResult(BaseModel):
    model_config = {"extra": "forbid"}

    vector: list[float] = Field(min_length=1)
    model: str
    dimensions: int = Field(ge=1)
    usage: EmbeddingUsage | None = None


class EmbedChunksResult(BaseModel):
    model_config = {"extra": "forbid"}

    company_document_id: int
    chunk_count: int = Field(ge=0)
    embedded_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    embedding_model: str
    embedding_dimensions: int
    usage_input_tokens: int | None = None
    usage_total_tokens: int | None = None
