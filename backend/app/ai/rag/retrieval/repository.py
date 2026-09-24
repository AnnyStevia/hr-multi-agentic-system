"""PostgreSQL/pgvector cosine retrieval with SQL-level access filters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import literal, select
from sqlalchemy.orm import Session

from app.ai.core.context.models import AIExecutionContext
from app.ai.rag.models import KnowledgeChunk
from app.ai.rag.retrieval.filters import company_document_eligibility_clause
from app.modules.documents.models import CompanyDocument


@dataclass(frozen=True)
class RetrievalRow:
    chunk_id: int
    company_document_id: int
    content: str
    similarity: float
    page_start: int
    page_end: int
    chunk_index: int
    content_hash: str
    metadata: dict[str, Any]


class VectorRetrievalRepository:
    """Runs authorization + eligibility + cosine distance + LIMIT inside PostgreSQL."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def search(
        self,
        *,
        query_embedding: list[float],
        context: AIExecutionContext,
        top_k: int,
        min_similarity: float | None = None,
    ) -> list[RetrievalRow]:
        distance = KnowledgeChunk.embedding.cosine_distance(query_embedding)
        similarity = (literal(1.0) - distance).label("similarity")

        stmt = (
            select(
                KnowledgeChunk.id.label("chunk_id"),
                KnowledgeChunk.company_document_id,
                KnowledgeChunk.content,
                similarity,
                KnowledgeChunk.page_start,
                KnowledgeChunk.page_end,
                KnowledgeChunk.chunk_index,
                KnowledgeChunk.content_hash,
                KnowledgeChunk.chunk_metadata,
            )
            .join(
                CompanyDocument,
                CompanyDocument.id == KnowledgeChunk.company_document_id,
            )
            .where(KnowledgeChunk.embedding.is_not(None))
        )

        eligibility = company_document_eligibility_clause(context)
        if eligibility is not None:
            stmt = stmt.where(eligibility)

        if min_similarity is not None:
            stmt = stmt.where(similarity >= min_similarity)

        stmt = stmt.order_by(distance.asc(), KnowledgeChunk.id.asc()).limit(top_k)

        rows = self.db.execute(stmt).all()
        results: list[RetrievalRow] = []
        for row in rows:
            meta = row.chunk_metadata if isinstance(row.chunk_metadata, dict) else {}
            results.append(
                RetrievalRow(
                    chunk_id=int(row.chunk_id),
                    company_document_id=int(row.company_document_id),
                    content=str(row.content),
                    similarity=float(row.similarity),
                    page_start=int(row.page_start),
                    page_end=int(row.page_end),
                    chunk_index=int(row.chunk_index),
                    content_hash=str(row.content_hash),
                    metadata=dict(meta),
                )
            )
        return results
