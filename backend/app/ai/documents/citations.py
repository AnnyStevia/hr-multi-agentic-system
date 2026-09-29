"""Page citation sanitization for Document Understanding (not Company RAG)."""

from __future__ import annotations

from app.ai.documents.schemas import DocumentCitation, DocumentContentContext, DocumentPage
from app.ai.documents.settings import (
    DocumentUnderstandingSettings,
    document_understanding_settings,
)


def valid_page_numbers(pages: list[DocumentPage]) -> set[int]:
    return {page.page_number for page in pages}


def sanitize_citations(
    raw_citations: list[dict] | list[DocumentCitation] | None,
    context: DocumentContentContext,
    *,
    settings: DocumentUnderstandingSettings | None = None,
) -> list[DocumentCitation]:
    """Keep only citations whose page_number exists in the current document."""
    cfg = settings or document_understanding_settings
    allowed = valid_page_numbers(context.pages)
    if not raw_citations:
        return []

    cleaned: list[DocumentCitation] = []
    seen: set[int] = set()
    for item in raw_citations:
        if isinstance(item, DocumentCitation):
            page_number = item.page_number
            excerpt = item.excerpt
        elif isinstance(item, dict):
            page_number = item.get("page_number")
            excerpt = item.get("excerpt")
        else:
            continue
        if not isinstance(page_number, int) or page_number not in allowed:
            continue
        if page_number in seen:
            continue
        seen.add(page_number)
        safe_excerpt: str | None = None
        if isinstance(excerpt, str) and excerpt.strip():
            safe_excerpt = excerpt.strip()[: cfg.doc_understanding_max_excerpt_chars]
        cleaned.append(
            DocumentCitation(page_number=page_number, excerpt=safe_excerpt)
        )
    return cleaned
