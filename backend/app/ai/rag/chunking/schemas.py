"""Schemas for deterministic document chunk drafts (Phase 5.3)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChunkDraft(BaseModel):
    """In-memory chunk ready to persist as a KnowledgeChunk row."""

    model_config = {"extra": "forbid"}

    chunk_index: int = Field(ge=0)
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    content: str = Field(min_length=1)
    content_hash: str = Field(min_length=64, max_length=64)
    metadata: dict[str, Any]
