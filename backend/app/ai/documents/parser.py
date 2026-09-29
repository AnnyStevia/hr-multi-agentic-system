"""PDF parsing + bounds for Document Understanding."""

from __future__ import annotations

from app.ai.documents.exceptions import (
    DocumentUnderstandingParseError,
    DocumentUnderstandingUnsupportedError,
)
from app.ai.documents.schemas import DocumentPage
from app.ai.documents.settings import (
    DocumentUnderstandingSettings,
    document_understanding_settings,
)
from app.ai.rag.exceptions import DocumentParseError, UnsupportedDocumentError
from app.ai.rag.ingestion.parsers.pdf import PDF_MIME, PdfDocumentParser
from app.modules.documents.content_payload import AuthorizedDocumentBytes


class DocumentUnderstandingParser:
    """Reuse PdfDocumentParser and apply deterministic page/character caps."""

    def __init__(
        self,
        *,
        pdf_parser: PdfDocumentParser | None = None,
        settings: DocumentUnderstandingSettings | None = None,
    ) -> None:
        self._parser = pdf_parser or PdfDocumentParser()
        self._settings = settings or document_understanding_settings

    def parse_authorized(
        self, payload: AuthorizedDocumentBytes
    ) -> tuple[list[DocumentPage], int, bool]:
        """Return (bounded pages, total_page_count_before_cap, truncated)."""
        if not self._parser.supports(payload.content_type, payload.filename):
            raise DocumentUnderstandingUnsupportedError(
                "Document Understanding currently supports PDF files only"
            )
        try:
            ingested = self._parser.parse(payload.file_bytes)
        except UnsupportedDocumentError as exc:
            raise DocumentUnderstandingUnsupportedError(str(exc)) from exc
        except DocumentParseError as exc:
            raise DocumentUnderstandingParseError(exc.message) from exc

        total_pages = len(ingested)
        max_pages = self._settings.doc_understanding_max_pages
        max_chars = self._settings.doc_understanding_max_characters

        pages: list[DocumentPage] = []
        used_chars = 0
        truncated = False

        for page in ingested:
            if len(pages) >= max_pages:
                truncated = True
                break
            text = page.text or ""
            remaining = max_chars - used_chars
            if remaining <= 0:
                truncated = True
                break
            if len(text) > remaining:
                text = text[:remaining]
                truncated = True
            pages.append(DocumentPage(page_number=page.page_number, text=text))
            used_chars += len(text)
            if truncated and len(text) < len(page.text or ""):
                break

        if total_pages > len(pages):
            truncated = True

        if not pages:
            raise DocumentUnderstandingParseError(
                "No readable text was found in the document"
            )

        return pages, total_pages, truncated
