"""Hybrid retrieval: secure vector + FTS fused with Reciprocal Rank Fusion."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.rag.config import rag_settings
from app.ai.rag.retrieval.exceptions import RetrievalValidationError
from app.ai.rag.retrieval.filters import require_company_documents_read
from app.ai.rag.retrieval.fts_repository import (
    FtsRetrievalRow,
    FullTextRetrievalRepository,
)
from app.ai.rag.retrieval.repository import RetrievalRow, VectorRetrievalRepository
from app.ai.rag.retrieval.rrf import fuse_rankings
from app.ai.rag.retrieval.schemas import HybridRequest, HybridRetrievalHit


@dataclass(frozen=True)
class HybridRetrieveDebug:
    vector_candidate_count: int
    fts_candidate_count: int


class HybridRetrievalService:
    """Run authorized vector + FTS branches, then RRF to a final top-k."""

    def __init__(
        self,
        db: Session,
        *,
        vector_repository: VectorRetrievalRepository | None = None,
        fts_repository: FullTextRetrievalRepository | None = None,
        expected_dimensions: int | None = None,
        default_top_k: int | None = None,
        max_top_k: int | None = None,
        vector_candidates: int | None = None,
        fts_candidates: int | None = None,
        max_candidates: int | None = None,
        rrf_k: int | None = None,
        min_similarity: float | None = None,
    ) -> None:
        self.db = db
        self._vector = vector_repository or VectorRetrievalRepository(db)
        self._fts = fts_repository or FullTextRetrievalRepository(db)
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
        self._vector_candidates = (
            vector_candidates
            if vector_candidates is not None
            else rag_settings.rag_hybrid_vector_candidates
        )
        self._fts_candidates = (
            fts_candidates
            if fts_candidates is not None
            else rag_settings.rag_hybrid_fts_candidates
        )
        self._max_candidates = (
            max_candidates
            if max_candidates is not None
            else rag_settings.rag_hybrid_max_candidates
        )
        self._rrf_k = rag_settings.rag_rrf_k if rrf_k is None else rrf_k
        self._min_similarity = (
            min_similarity
            if min_similarity is not None
            else rag_settings.rag_retrieval_min_similarity
        )
        self.last_debug: HybridRetrieveDebug | None = None

    def retrieve(self, request: HybridRequest) -> list[HybridRetrievalHit]:
        require_company_documents_read(request.context)
        top_k = self._resolve_top_k(request.top_k)
        self._validate_embedding(request.query_embedding)
        vector_n = self._resolve_candidates(self._vector_candidates, label="vector")
        fts_n = self._resolve_candidates(self._fts_candidates, label="fts")
        if self._rrf_k < 1:
            raise RetrievalValidationError("rag_rrf_k must be >= 1")

        vector_rows = self._vector.search(
            query_embedding=list(request.query_embedding),
            context=request.context,
            top_k=vector_n,
            min_similarity=self._min_similarity,
        )
        fts_rows = self._fts.search(
            query_text=request.query_text,
            context=request.context,
            top_k=fts_n,
        )
        self.last_debug = HybridRetrieveDebug(
            vector_candidate_count=len(vector_rows),
            fts_candidate_count=len(fts_rows),
        )

        fused = fuse_rankings(
            [row.chunk_id for row in vector_rows],
            [row.chunk_id for row in fts_rows],
            k=self._rrf_k,
        )
        by_id = self._merge_payloads(vector_rows, fts_rows)

        hits: list[HybridRetrievalHit] = []
        for chunk_id, rrf_score in fused[:top_k]:
            payload = by_id[chunk_id]
            hits.append(
                HybridRetrievalHit(
                    chunk_id=chunk_id,
                    company_document_id=payload["company_document_id"],
                    content=payload["content"],
                    page_start=payload["page_start"],
                    page_end=payload["page_end"],
                    chunk_index=payload["chunk_index"],
                    content_hash=payload["content_hash"],
                    metadata=payload["metadata"],
                    vector_similarity=payload.get("vector_similarity"),
                    fts_rank=payload.get("fts_rank"),
                    rrf_score=rrf_score,
                )
            )
        return hits

    def _merge_payloads(
        self,
        vector_rows: list[RetrievalRow],
        fts_rows: list[FtsRetrievalRow],
    ) -> dict[int, dict]:
        merged: dict[int, dict] = {}
        for row in vector_rows:
            merged[row.chunk_id] = {
                "company_document_id": row.company_document_id,
                "content": row.content,
                "page_start": row.page_start,
                "page_end": row.page_end,
                "chunk_index": row.chunk_index,
                "content_hash": row.content_hash,
                "metadata": dict(row.metadata),
                "vector_similarity": row.similarity,
                "fts_rank": None,
            }
        for row in fts_rows:
            if row.chunk_id in merged:
                merged[row.chunk_id]["fts_rank"] = row.fts_rank
            else:
                merged[row.chunk_id] = {
                    "company_document_id": row.company_document_id,
                    "content": row.content,
                    "page_start": row.page_start,
                    "page_end": row.page_end,
                    "chunk_index": row.chunk_index,
                    "content_hash": row.content_hash,
                    "metadata": dict(row.metadata),
                    "vector_similarity": None,
                    "fts_rank": row.fts_rank,
                }
        return merged

    def _resolve_top_k(self, top_k: int | None) -> int:
        value = self._default_top_k if top_k is None else top_k
        if value < 1:
            raise RetrievalValidationError("top_k must be >= 1")
        if value > self._max_top_k:
            raise RetrievalValidationError(
                f"top_k must be <= {self._max_top_k} (got {value})"
            )
        return value

    def _resolve_candidates(self, value: int, *, label: str) -> int:
        if value < 1:
            raise RetrievalValidationError(f"{label} candidates must be >= 1")
        if value > self._max_candidates:
            raise RetrievalValidationError(
                f"{label} candidates must be <= {self._max_candidates} (got {value})"
            )
        return value

    def _validate_embedding(self, embedding: list[float]) -> None:
        if len(embedding) != self._expected_dimensions:
            raise RetrievalValidationError(
                f"query_embedding dimension mismatch: expected "
                f"{self._expected_dimensions}, got {len(embedding)}"
            )
