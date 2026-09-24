"""PostgreSQL full-text retrieval with the same SQL access filters as vector search.

Uses text-search configuration 'simple' (language-neutral) for mixed EN/FR HR content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.core.context.models import AIExecutionContext
from app.ai.rag.models import KnowledgeChunk
from app.ai.rag.retrieval.filters import company_document_eligibility_clause
from app.modules.documents.models import CompanyDocument

FTS_CONFIG = "simple"


@dataclass(frozen=True)
class FtsRetrievalRow:
    chunk_id: int
    company_document_id: int
    content: str
    fts_rank: float
    page_start: int
    page_end: int
    chunk_index: int
    content_hash: str
    metadata: dict[str, Any]


class FullTextRetrievalRepository:
    """Secure FTS over KnowledgeChunk.content_tsv (authorization in SQL)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def search(
        self,
        *,
        query_text: str,
        context: AIExecutionContext,
        top_k: int,
    ) -> list[FtsRetrievalRow]:
        cleaned = (query_text or "").strip()
        if not cleaned or top_k < 1:
            return []

        ts_query = func.websearch_to_tsquery(FTS_CONFIG, cleaned)
        rank = func.ts_rank_cd(KnowledgeChunk.content_tsv, ts_query).label("fts_rank")

        stmt = (
            select(
                KnowledgeChunk.id.label("chunk_id"),
                KnowledgeChunk.company_document_id,
                KnowledgeChunk.content,
                rank,
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
            .where(KnowledgeChunk.content_tsv.op("@@")(ts_query))
        )

        eligibility = company_document_eligibility_clause(context)
        if eligibility is not None:
            stmt = stmt.where(eligibility)

        stmt = stmt.order_by(rank.desc(), KnowledgeChunk.id.asc()).limit(top_k)

        rows = self.db.execute(stmt).all()
        results: list[FtsRetrievalRow] = []
        for row in rows:
            meta = row.chunk_metadata if isinstance(row.chunk_metadata, dict) else {}
            results.append(
                FtsRetrievalRow(
                    chunk_id=int(row.chunk_id),
                    company_document_id=int(row.company_document_id),
                    content=str(row.content),
                    fts_rank=float(row.fts_rank),
                    page_start=int(row.page_start),
                    page_end=int(row.page_end),
                    chunk_index=int(row.chunk_index),
                    content_hash=str(row.content_hash),
                    metadata=dict(meta),
                )
            )
        return results
