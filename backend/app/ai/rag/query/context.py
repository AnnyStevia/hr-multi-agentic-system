"""Assemble ranked hybrid hits into a bounded structured context."""

from __future__ import annotations

from app.ai.rag.config import rag_settings
from app.ai.rag.query.schemas import RAGContextItem
from app.ai.rag.retrieval.schemas import HybridRetrievalHit


class ContextAssembler:
    """Preserve RRF order; never partially truncate a chunk."""

    def __init__(
        self,
        *,
        max_chunks: int | None = None,
        max_characters: int | None = None,
    ) -> None:
        self._max_chunks = (
            rag_settings.rag_context_max_chunks if max_chunks is None else max_chunks
        )
        self._max_characters = (
            rag_settings.rag_context_max_characters
            if max_characters is None
            else max_characters
        )

    def assemble(self, hits: list[HybridRetrievalHit]) -> list[RAGContextItem]:
        if self._max_chunks < 1:
            return []
        selected: list[RAGContextItem] = []
        seen: set[int] = set()
        used_chars = 0

        for hit in hits:
            if hit.chunk_id in seen:
                continue
            if len(selected) >= self._max_chunks:
                break
            content = hit.content or ""
            next_len = len(content)
            if used_chars + next_len > self._max_characters:
                # Do not partially include this chunk.
                break
            seen.add(hit.chunk_id)
            used_chars += next_len
            selected.append(
                RAGContextItem(
                    chunk_id=hit.chunk_id,
                    company_document_id=hit.company_document_id,
                    content=content,
                    page_start=hit.page_start,
                    page_end=hit.page_end,
                    chunk_index=hit.chunk_index,
                    content_hash=hit.content_hash,
                    metadata=dict(hit.metadata),
                    vector_similarity=hit.vector_similarity,
                    fts_rank=hit.fts_rank,
                    rrf_score=hit.rrf_score,
                )
            )
        return selected
