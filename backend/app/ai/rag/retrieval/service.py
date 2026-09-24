"""Secure vector retrieval service (no Gemini / no RAG generation)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.rag.config import rag_settings
from app.ai.rag.retrieval.exceptions import RetrievalValidationError
from app.ai.rag.retrieval.filters import require_company_documents_read
from app.ai.rag.retrieval.repository import VectorRetrievalRepository
from app.ai.rag.retrieval.schemas import RetrievalHit, RetrievalRequest


class RetrievalService:
    """Validate request, enforce library auth, run SQL cosine top-k search."""

    def __init__(
        self,
        db: Session,
        *,
        repository: VectorRetrievalRepository | None = None,
        expected_dimensions: int | None = None,
        default_top_k: int | None = None,
        max_top_k: int | None = None,
        min_similarity: float | None = None,
    ) -> None:
        self.db = db
        self._repository = repository or VectorRetrievalRepository(db)
        self._expected_dimensions = (
            expected_dimensions
            if expected_dimensions is not None
            else rag_settings.rag_embedding_dimensions
        )
        self._default_top_k = (
            default_top_k
            if default_top_k is not None
            else rag_settings.rag_retrieval_top_k
        )
        self._max_top_k = (
            max_top_k if max_top_k is not None else rag_settings.rag_retrieval_max_top_k
        )
        self._min_similarity = (
            min_similarity
            if min_similarity is not None
            else rag_settings.rag_retrieval_min_similarity
        )

    def retrieve(self, request: RetrievalRequest) -> list[RetrievalHit]:
        require_company_documents_read(request.context)
        top_k = self._resolve_top_k(request.top_k)
        self._validate_embedding(request.query_embedding)

        rows = self._repository.search(
            query_embedding=list(request.query_embedding),
            context=request.context,
            top_k=top_k,
            min_similarity=self._min_similarity,
        )
        return [
            RetrievalHit(
                chunk_id=row.chunk_id,
                company_document_id=row.company_document_id,
                content=row.content,
                similarity=row.similarity,
                page_start=row.page_start,
                page_end=row.page_end,
                chunk_index=row.chunk_index,
                content_hash=row.content_hash,
                metadata=row.metadata,
            )
            for row in rows
        ]

    def _resolve_top_k(self, top_k: int | None) -> int:
        value = self._default_top_k if top_k is None else top_k
        if value < 1:
            raise RetrievalValidationError("top_k must be >= 1")
        if value > self._max_top_k:
            raise RetrievalValidationError(
                f"top_k must be <= {self._max_top_k} (got {value})"
            )
        return value

    def _validate_embedding(self, embedding: list[float]) -> None:
        if len(embedding) != self._expected_dimensions:
            raise RetrievalValidationError(
                f"query_embedding dimension mismatch: expected "
                f"{self._expected_dimensions}, got {len(embedding)}"
            )
