"""Ingest Company Document Library files into page-aware text (no chunking)."""

from __future__ import annotations

from pathlib import PurePosixPath

from app.ai.rag.exceptions import (
    DocumentIngestionError,
    DocumentParseError,
    UnsupportedDocumentError,
)
from app.ai.rag.ingestion.parsers.base import DocumentParser
from app.ai.rag.ingestion.parsers.pdf import PDF_MIME, PdfDocumentParser
from app.ai.rag.ingestion.schemas import IngestionResult
from app.modules.documents.models import CompanyDocument
from app.shared.storage.base import StorageService
from app.shared.storage.exceptions import StorageException


class DocumentIngestionService:
    """Extract normalized text from an authorized CompanyDocument via StorageService."""

    def __init__(
        self,
        storage: StorageService,
        *,
        parsers: list[DocumentParser] | None = None,
    ):
        self._storage = storage
        self._parsers = parsers if parsers is not None else [PdfDocumentParser()]

    def ingest_company_document(self, document: CompanyDocument) -> IngestionResult:
        if not isinstance(document, CompanyDocument):
            raise UnsupportedDocumentError(
                "Only Company Document Library documents can be ingested"
            )

        parser = self._resolve_parser(document.content_type, document.original_filename)
        storage_key = (document.storage_key or "").strip()
        if not storage_key or storage_key == "pending":
            raise DocumentIngestionError("Document has no stored object to ingest")

        try:
            file_bytes = self._storage.download_file(storage_key)
        except StorageException as exc:
            raise DocumentIngestionError(exc.message) from exc
        except Exception as exc:
            raise DocumentIngestionError("Failed to download document for ingestion") from exc

        if not file_bytes:
            raise DocumentParseError("PDF file is empty")

        try:
            pages = parser.parse(file_bytes)
        except DocumentParseError:
            raise
        except Exception as exc:
            raise DocumentParseError("Failed to extract text from document") from exc

        extracted_text = "\n\n".join(page.text for page in pages if page.text).strip()
        return IngestionResult(
            company_document_id=document.id,
            filename=document.original_filename,
            content_type=document.content_type or PDF_MIME,
            total_pages=len(pages),
            extracted_text=extracted_text,
            pages=pages,
        )

    def _resolve_parser(
        self,
        content_type: str | None,
        filename: str | None,
    ) -> DocumentParser:
        for parser in self._parsers:
            if parser.supports(content_type, filename):
                return parser
        extension = PurePosixPath(filename or "").suffix.lower() or "unknown"
        raise UnsupportedDocumentError(
            f"Unsupported document type for ingestion: {content_type or extension}"
        )
