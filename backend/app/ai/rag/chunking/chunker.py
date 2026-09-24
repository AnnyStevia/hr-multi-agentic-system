"""Deterministic page-aware document chunker (no LLM, no embeddings).

Chunk size and overlap are whitespace-separated word counts — a deterministic
approximation that avoids a tokenizer dependency.
"""

from __future__ import annotations

import re

from app.ai.rag.chunking.hasher import sha256_hex
from app.ai.rag.chunking.schemas import ChunkDraft
from app.ai.rag.config import rag_settings
from app.ai.rag.ingestion.schemas import IngestedPage, IngestionResult

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")


def _join_words(words: list[str]) -> str:
    return " ".join(words)


def _split_paragraphs(page_text: str) -> list[str]:
    parts = [p.strip() for p in _PARAGRAPH_SPLIT.split(page_text)]
    return [p for p in parts if p]


class DocumentChunker:
    """Split page-aware ingestion results into ordered, overlapping chunks.

    Strategy:
    - Prefer paragraph and page boundaries.
    - Accumulate until the next block would exceed ``chunk_size``.
    - Flush at page end to preserve page provenance.
    - Hard-split oversized paragraphs by words with overlap.
    - Never emit empty chunks; empty documents yield ``[]``.
    """

    def __init__(
        self,
        chunk_size: int | None = None,
        overlap: int | None = None,
    ) -> None:
        size = rag_settings.rag_chunk_size if chunk_size is None else chunk_size
        ov = rag_settings.rag_chunk_overlap if overlap is None else overlap
        if size < 1:
            raise ValueError("chunk_size must be >= 1")
        if ov < 0:
            raise ValueError("overlap must be >= 0")
        if ov >= size:
            raise ValueError("overlap must be < chunk_size")
        self.chunk_size = size
        self.overlap = ov

    def chunk(
        self,
        result: IngestionResult,
        *,
        document_version: int,
    ) -> list[ChunkDraft]:
        drafts: list[ChunkDraft] = []
        buffer_words: list[str] = []
        page_start: int | None = None
        page_end: int | None = None

        def emit(words: list[str], start: int, end: int) -> None:
            content = _join_words(words).strip()
            if not content:
                return
            drafts.append(
                self._make_draft(
                    chunk_index=len(drafts),
                    page_start=start,
                    page_end=end,
                    content=content,
                    company_document_id=result.company_document_id,
                    document_version=document_version,
                )
            )

        def flush(*, carry_overlap: bool) -> list[str]:
            nonlocal buffer_words, page_start, page_end
            if not buffer_words or page_start is None or page_end is None:
                buffer_words = []
                page_start = None
                page_end = None
                return []
            emit(buffer_words, page_start, page_end)
            if carry_overlap and self.overlap > 0:
                overlap_words = buffer_words[-self.overlap :]
                buffer_words = []
                page_start = None
                page_end = None
                return list(overlap_words)
            buffer_words = []
            page_start = None
            page_end = None
            return []

        def ensure_capacity(extra_words: int, page_number: int) -> None:
            nonlocal buffer_words, page_start, page_end
            if buffer_words and len(buffer_words) + extra_words > self.chunk_size:
                overlap_seed = flush(carry_overlap=True)
                if overlap_seed:
                    buffer_words = overlap_seed
                    page_start = page_number
                    page_end = page_number

        def add_block(words: list[str], page_number: int) -> None:
            nonlocal buffer_words, page_start, page_end
            if not words:
                return
            ensure_capacity(len(words), page_number)
            if page_start is None:
                page_start = page_number
            page_end = page_number
            buffer_words.extend(words)
            # Safety: if somehow oversize (shouldn't for normal paragraphs), flush.
            while len(buffer_words) > self.chunk_size:
                piece = buffer_words[: self.chunk_size]
                emit(piece, page_start or page_number, page_end or page_number)
                if self.overlap > 0:
                    buffer_words = piece[-self.overlap :] + buffer_words[self.chunk_size :]
                else:
                    buffer_words = buffer_words[self.chunk_size :]
                page_start = page_number
                page_end = page_number

        for page in result.pages:
            page_text = (page.text or "").strip()
            if not page_text:
                continue

            # Preserve page boundaries: close any buffered content from a prior page.
            if buffer_words and page_end is not None and page_end != page.page_number:
                flush(carry_overlap=False)

            paragraphs = _split_paragraphs(page_text) or [page_text]
            for paragraph in paragraphs:
                words = paragraph.split()
                if not words:
                    continue
                if len(words) > self.chunk_size:
                    if buffer_words:
                        flush(carry_overlap=False)
                    self._emit_hard_split(
                        words=words,
                        page_number=page.page_number,
                        drafts=drafts,
                        company_document_id=result.company_document_id,
                        document_version=document_version,
                    )
                    continue
                add_block(words, page.page_number)

            # End of page: flush remaining page content (no cross-page overlap).
            if buffer_words:
                flush(carry_overlap=False)

        if buffer_words:
            flush(carry_overlap=False)

        return drafts

    def _emit_hard_split(
        self,
        *,
        words: list[str],
        page_number: int,
        drafts: list[ChunkDraft],
        company_document_id: int,
        document_version: int,
    ) -> None:
        start = 0
        while start < len(words):
            end = min(start + self.chunk_size, len(words))
            piece = words[start:end]
            content = _join_words(piece).strip()
            if content:
                drafts.append(
                    self._make_draft(
                        chunk_index=len(drafts),
                        page_start=page_number,
                        page_end=page_number,
                        content=content,
                        company_document_id=company_document_id,
                        document_version=document_version,
                    )
                )
            if end >= len(words):
                break
            next_start = end - self.overlap
            start = next_start if next_start > start else start + 1

    def _make_draft(
        self,
        *,
        chunk_index: int,
        page_start: int,
        page_end: int,
        content: str,
        company_document_id: int,
        document_version: int,
    ) -> ChunkDraft:
        content_hash = sha256_hex(content)
        metadata = {
            "company_document_id": company_document_id,
            "page_start": page_start,
            "page_end": page_end,
            "chunk_index": chunk_index,
            "document_version": document_version,
            "content_hash": content_hash,
        }
        return ChunkDraft(
            chunk_index=chunk_index,
            page_start=page_start,
            page_end=page_end,
            content=content,
            content_hash=content_hash,
            metadata=metadata,
        )


def pages_to_ingestion_result(
    pages: list[IngestedPage],
    *,
    company_document_id: int,
    filename: str = "document.pdf",
    content_type: str = "application/pdf",
) -> IngestionResult:
    """Helper for tests: build an IngestionResult from pages."""
    extracted = "\n\n".join(p.text for p in pages if p.text).strip()
    return IngestionResult(
        company_document_id=company_document_id,
        filename=filename,
        content_type=content_type,
        total_pages=len(pages),
        extracted_text=extracted,
        pages=pages,
    )
