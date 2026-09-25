"""Orchestrate company-library PDF → chunks → embeddings for RAG (Phase 5.11).

Only CompanyDocument rows may be indexed. Private/employee/CV documents are rejected.

Future file-replace flows that bump storage_key / version must call
index_document after the new object is persisted so chunks are replaced.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.ai.rag.chunking.service import KnowledgeChunkService
from app.ai.rag.embeddings.base import EmbeddingProvider
from app.ai.rag.embeddings.exceptions import EmbeddingException
from app.ai.rag.embeddings.service import EmbeddingService
from app.ai.rag.exceptions import (
    DocumentIngestionError,
    DocumentParseError,
    UnsupportedDocumentError,
)
from app.ai.rag.ingestion.parsers.pdf import PDF_MIME
from app.modules.documents.models import (
    CompanyDocument,
    CompanyDocumentRagIndexStatus,
)
from app.shared.storage.base import StorageService

logger = logging.getLogger(__name__)

ERROR_UNSUPPORTED = "Unsupported file type for AI indexing"
ERROR_PARSE = "Document text extraction failed"
ERROR_STORAGE = "Document storage could not be read for indexing"
ERROR_EMBED = "Document embedding failed"
ERROR_GENERIC = "Document indexing failed"


def sanitize_indexing_error(exc: BaseException) -> str:
    """Map failures to short operational messages (no content / secrets)."""
    if isinstance(exc, UnsupportedDocumentError):
        return ERROR_UNSUPPORTED
    if isinstance(exc, DocumentParseError):
        return ERROR_PARSE
    if isinstance(exc, DocumentIngestionError):
        return ERROR_STORAGE
    if isinstance(exc, EmbeddingException):
        return ERROR_EMBED
    message = str(exc).strip().lower()
    if "unsupported" in message or "file type" in message:
        return ERROR_UNSUPPORTED
    if "parse" in message or "extract" in message or "pdf" in message:
        return ERROR_PARSE
    if "storage" in message or "download" in message:
        return ERROR_STORAGE
    if "embed" in message:
        return ERROR_EMBED
    return ERROR_GENERIC


def _is_pdf_document(document: CompanyDocument) -> bool:
    content_type = (document.content_type or "").split(";")[0].strip().lower()
    if content_type == PDF_MIME:
        return True
    extension = Path(document.original_filename or "").suffix.lower()
    return extension == ".pdf"


class CompanyDocumentIndexingService:
    """Ingest + chunk + embed a single company library document."""

    def __init__(
        self,
        db: Session,
        storage: StorageService,
        *,
        embedding_provider: EmbeddingProvider,
        chunk_service: KnowledgeChunkService | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.db = db
        self._storage = storage
        self._chunks = chunk_service or KnowledgeChunkService(db, storage)
        self._embeddings = embedding_service or EmbeddingService(
            db, embedding_provider
        )

    def index_document(self, company_document_id: int) -> CompanyDocument | None:
        document = (
            self.db.query(CompanyDocument)
            .filter(CompanyDocument.id == company_document_id)
            .first()
        )
        if document is None:
            return None
        if not isinstance(document, CompanyDocument):
            raise UnsupportedDocumentError(
                "Only Company Document Library documents can be indexed"
            )

        self._set_status(
            document,
            CompanyDocumentRagIndexStatus.PROCESSING,
            error=None,
            indexed_at=None,
        )

        try:
            if not _is_pdf_document(document):
                raise UnsupportedDocumentError(ERROR_UNSUPPORTED)

            self._chunks.ingest_and_replace_chunks(document)
            # reload after chunk commit
            document = (
                self.db.query(CompanyDocument)
                .filter(CompanyDocument.id == company_document_id)
                .one()
            )
            result = self._embeddings.embed_company_document_chunks(
                company_document_id
            )
            if result.chunk_count == 0:
                raise DocumentParseError("No extractable text for indexing")

            document = (
                self.db.query(CompanyDocument)
                .filter(CompanyDocument.id == company_document_id)
                .one()
            )
            self._set_status(
                document,
                CompanyDocumentRagIndexStatus.READY,
                error=None,
                indexed_at=datetime.now(timezone.utc),
            )
            return document
        except Exception as exc:
            logger.exception(
                "Company document RAG indexing failed for id=%s",
                company_document_id,
            )
            document = (
                self.db.query(CompanyDocument)
                .filter(CompanyDocument.id == company_document_id)
                .first()
            )
            if document is not None:
                self._set_status(
                    document,
                    CompanyDocumentRagIndexStatus.FAILED,
                    error=sanitize_indexing_error(exc),
                    indexed_at=None,
                )
            return document

    def retry_document(self, company_document_id: int) -> CompanyDocument | None:
        """Safe re-run (FAILED or READY); uses replace-chunks + embed skip rules."""
        return self.index_document(company_document_id)

    def _set_status(
        self,
        document: CompanyDocument,
        status: CompanyDocumentRagIndexStatus,
        *,
        error: str | None,
        indexed_at: datetime | None,
    ) -> None:
        document.rag_index_status = status
        document.rag_indexing_error = (error[:500] if error else None)
        if status == CompanyDocumentRagIndexStatus.READY:
            document.rag_indexed_at = indexed_at
        elif status in {
            CompanyDocumentRagIndexStatus.PENDING,
            CompanyDocumentRagIndexStatus.PROCESSING,
            CompanyDocumentRagIndexStatus.FAILED,
        }:
            if status != CompanyDocumentRagIndexStatus.READY:
                # Keep prior indexed_at only on READY; clear otherwise when failing/processing
                if status == CompanyDocumentRagIndexStatus.FAILED:
                    pass  # leave previous indexed_at if any, or clear — plan: clear on fail
                    document.rag_indexed_at = None
                elif status == CompanyDocumentRagIndexStatus.PROCESSING:
                    document.rag_indexed_at = None
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)


def run_company_document_indexing(company_document_id: int) -> None:
    """BackgroundTasks entrypoint: fresh DB session + storage + embedding provider."""
    from app.ai.rag.embeddings import get_embedding_provider
    from app.core.database import SessionLocal
    from app.shared.storage import get_storage_service

    db = SessionLocal()
    try:
        service = CompanyDocumentIndexingService(
            db,
            get_storage_service(),
            embedding_provider=get_embedding_provider(),
        )
        service.index_document(company_document_id)
    except Exception:
        logger.exception(
            "Unhandled error in background RAG indexing for id=%s",
            company_document_id,
        )
    finally:
        db.close()
