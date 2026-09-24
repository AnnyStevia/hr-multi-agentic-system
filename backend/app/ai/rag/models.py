"""Minimal RAG knowledge-chunk storage (Phase 5.1 + 5.3 provenance)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Must match RAGSettings.rag_embedding_dimensions default.
RAG_EMBEDDING_DIMENSIONS = 768


class KnowledgeChunk(Base):
    """Chunk of a company library document pending/holding an embedding.

    Embedding population is deferred to Phase 5.4+.
    """

    __tablename__ = "rag_document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "company_document_id",
            "chunk_index",
            name="uq_rag_document_chunks_document_chunk_index",
        ),
        Index("ix_rag_document_chunks_content_hash", "content_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_document_id: Mapped[int] = mapped_column(
        ForeignKey("company_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Column name "metadata" collides with Declarative API; map via chunk_metadata.
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(RAG_EMBEDDING_DIMENSIONS),
        nullable=True,
    )
    embedding_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
