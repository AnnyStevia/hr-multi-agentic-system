"""Build DocumentContentContext for LLM prompts."""

from __future__ import annotations

from app.ai.documents.parser import DocumentUnderstandingParser
from app.ai.documents.schemas import DocumentContentContext, DocumentSourceType
from app.modules.documents.content_payload import AuthorizedDocumentBytes


def build_document_context(
    payload: AuthorizedDocumentBytes,
    source_type: DocumentSourceType,
    *,
    parser: DocumentUnderstandingParser | None = None,
) -> DocumentContentContext:
    active_parser = parser or DocumentUnderstandingParser()
    pages, total_pages, truncated = active_parser.parse_authorized(payload)
    character_count = sum(len(p.text) for p in pages)
    return DocumentContentContext(
        document_id=payload.document_id,
        source_type=source_type,
        title=payload.title,
        filename=payload.filename,
        content_type=payload.content_type,
        page_count=total_pages,
        pages=pages,
        truncated=truncated,
        character_count=character_count,
    )
