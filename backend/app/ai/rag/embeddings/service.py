"""Embed existing KnowledgeChunk rows (Phase 5.4 — no retrieval)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.rag.chunking.repository import KnowledgeChunkRepository
from app.ai.rag.config import rag_settings
from app.ai.rag.embeddings.base import EmbeddingProvider
from app.ai.rag.embeddings.exceptions import EmbeddingValidationError
from app.ai.rag.embeddings.gemini import DEFAULT_QUERY_TASK_TYPE
from app.ai.rag.embeddings.schemas import EmbedChunksResult, EmbeddingResult
from app.ai.rag.embeddings.validation import validate_embedding_vector
from app.ai.rag.models import KnowledgeChunk


class EmbeddingService:
    """Embed company-document chunks and query texts (same model/space)."""

    def __init__(
        self,
        db: Session | None,
        provider: EmbeddingProvider,
        *,
        repository: KnowledgeChunkRepository | None = None,
        embedding_model: str | None = None,
        embedding_dimensions: int | None = None,
        max_batch_size: int | None = None,
    ) -> None:
        self.db = db
        self._provider = provider
        self._repository = repository
        if repository is None and db is not None:
            self._repository = KnowledgeChunkRepository(db)
        self._model = embedding_model or rag_settings.rag_embedding_model
        self._dimensions = (
            embedding_dimensions
            if embedding_dimensions is not None
            else rag_settings.rag_embedding_dimensions
        )
        self._max_batch_size = (
            max_batch_size
            if max_batch_size is not None
            else rag_settings.rag_embed_max_batch_size
        )

    def embed_query(self, text: str) -> EmbeddingResult:
        """Embed a retrieval query (does not persist)."""
        cleaned = (text or "").strip()
        if not cleaned:
            raise EmbeddingValidationError("Query text for embedding is empty")
        result = self._provider.embed_text(
            cleaned, task_type=DEFAULT_QUERY_TASK_TYPE
        )
        vector = validate_embedding_vector(
            result.vector, expected_dimensions=self._dimensions
        )
        return EmbeddingResult(
            vector=vector,
            model=result.model or self._model,
            dimensions=self._dimensions,
            usage=result.usage,
        )

    def embed_company_document_chunks(
        self, company_document_id: int
    ) -> EmbedChunksResult:
        if self.db is None or self._repository is None:
            raise RuntimeError(
                "EmbeddingService requires a database session to persist chunk embeddings"
            )
        chunks = self._repository.list_by_company_document_id(company_document_id)
        pending = [c for c in chunks if self._needs_embedding(c)]
        skipped = len(chunks) - len(pending)

        if not pending:
            return EmbedChunksResult(
                company_document_id=company_document_id,
                chunk_count=len(chunks),
                embedded_count=0,
                skipped_count=skipped,
                embedding_model=self._model,
                embedding_dimensions=self._dimensions,
            )

        try:
            results = self._embed_pending(pending)
            for chunk, result in zip(pending, results, strict=True):
                vector = validate_embedding_vector(
                    result.vector, expected_dimensions=self._dimensions
                )
                chunk.embedding = vector
                chunk.embedding_model = self._model
                chunk.embedding_dimensions = self._dimensions

            self._repository.save_embeddings(pending)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        usage_input = 0
        usage_total = 0
        saw_input = False
        saw_total = False
        for result in results:
            if result.usage and result.usage.input_tokens is not None:
                usage_input += result.usage.input_tokens
                saw_input = True
            if result.usage and result.usage.total_tokens is not None:
                usage_total += result.usage.total_tokens
                saw_total = True

        return EmbedChunksResult(
            company_document_id=company_document_id,
            chunk_count=len(chunks),
            embedded_count=len(pending),
            skipped_count=skipped,
            embedding_model=self._model,
            embedding_dimensions=self._dimensions,
            usage_input_tokens=usage_input if saw_input else None,
            usage_total_tokens=usage_total if saw_total else None,
        )

    def _needs_embedding(self, chunk: KnowledgeChunk) -> bool:
        if chunk.embedding is None:
            return True
        if chunk.embedding_model != self._model:
            return True
        if chunk.embedding_dimensions != self._dimensions:
            return True
        return False

    def _embed_pending(self, pending: list[KnowledgeChunk]) -> list[EmbeddingResult]:
        texts = [chunk.content for chunk in pending]
        if self._max_batch_size < 1:
            raise EmbeddingValidationError("rag_embed_max_batch_size must be >= 1")

        results: list[EmbeddingResult] = []
        for start in range(0, len(texts), self._max_batch_size):
            batch = texts[start : start + self._max_batch_size]
            batch_results = self._provider.embed_texts(batch)
            if len(batch_results) != len(batch):
                raise EmbeddingValidationError(
                    f"Provider returned {len(batch_results)} embeddings "
                    f"for {len(batch)} texts"
                )
            results.extend(batch_results)
        return results
