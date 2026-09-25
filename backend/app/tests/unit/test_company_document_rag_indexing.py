"""Unit tests for Phase 5.11 company document RAG indexing (no Gemini)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.ai.rag.embeddings.exceptions import EmbeddingProviderError
from app.ai.rag.embeddings.schemas import EmbedChunksResult
from app.ai.rag.exceptions import DocumentParseError, UnsupportedDocumentError
from app.ai.rag.indexing.service import (
    ERROR_EMBED,
    ERROR_UNSUPPORTED,
    CompanyDocumentIndexingService,
    sanitize_indexing_error,
)
from app.ai.rag.models import KnowledgeChunk  # noqa: F401 — import for mapper side effects
from app.modules.documents.models import (
    CompanyDocument,
    CompanyDocumentRagIndexStatus,
    CompanyDocumentStatus,
    PrivateDocument,
)


def _doc(**overrides) -> MagicMock:
    values = {
        "id": 42,
        "title": "Handbook",
        "original_filename": "handbook.pdf",
        "content_type": "application/pdf",
        "storage_key": "company-documents/42/handbook.pdf",
        "version": 1,
        "status": CompanyDocumentStatus.ACTIVE,
        "rag_index_status": CompanyDocumentRagIndexStatus.PENDING,
        "rag_indexed_at": None,
        "rag_indexing_error": None,
    }
    values.update(overrides)
    document = MagicMock(spec=CompanyDocument)
    for key, value in values.items():
        setattr(document, key, value)
    return document


def _service_with_mocks():
    db = MagicMock()
    storage = MagicMock()
    provider = MagicMock()
    chunks = MagicMock()
    embeddings = MagicMock()
    service = CompanyDocumentIndexingService(
        db,
        storage,
        embedding_provider=provider,
        chunk_service=chunks,
        embedding_service=embeddings,
    )
    return service, db, chunks, embeddings


def test_sanitize_indexing_error_messages():
    assert sanitize_indexing_error(UnsupportedDocumentError("x")) == ERROR_UNSUPPORTED
    assert sanitize_indexing_error(DocumentParseError("x")).startswith("Document text")
    assert sanitize_indexing_error(EmbeddingProviderError("boom")) == ERROR_EMBED
    assert "API_KEY" not in sanitize_indexing_error(Exception("secret API_KEY xyz"))


def test_index_success_sets_ready():
    service, db, chunks, embeddings = _service_with_mocks()
    document = _doc()
    db.query.return_value.filter.return_value.first.return_value = document
    db.query.return_value.filter.return_value.one.return_value = document
    chunks.ingest_and_replace_chunks.return_value = [MagicMock()]
    embeddings.embed_company_document_chunks.return_value = EmbedChunksResult(
        company_document_id=42,
        chunk_count=1,
        embedded_count=1,
        skipped_count=0,
        embedding_model="gemini-embedding-2",
        embedding_dimensions=768,
    )

    result = service.index_document(42)

    assert result is document
    assert document.rag_index_status == CompanyDocumentRagIndexStatus.READY
    assert document.rag_indexing_error is None
    assert document.rag_indexed_at is not None
    chunks.ingest_and_replace_chunks.assert_called_once()
    embeddings.embed_company_document_chunks.assert_called_once_with(42)


def test_non_pdf_fails_without_chunking():
    service, db, chunks, embeddings = _service_with_mocks()
    document = _doc(
        original_filename="photo.png",
        content_type="image/png",
    )
    db.query.return_value.filter.return_value.first.return_value = document

    result = service.index_document(42)

    assert result is document
    assert document.rag_index_status == CompanyDocumentRagIndexStatus.FAILED
    assert document.rag_indexing_error == ERROR_UNSUPPORTED
    chunks.ingest_and_replace_chunks.assert_not_called()
    embeddings.embed_company_document_chunks.assert_not_called()


def test_embed_failure_sets_failed_sanitized():
    service, db, chunks, embeddings = _service_with_mocks()
    document = _doc()
    db.query.return_value.filter.return_value.first.return_value = document
    db.query.return_value.filter.return_value.one.return_value = document
    chunks.ingest_and_replace_chunks.return_value = [MagicMock()]
    embeddings.embed_company_document_chunks.side_effect = EmbeddingProviderError(
        "provider exploded with key sk-secret"
    )

    service.index_document(42)

    assert document.rag_index_status == CompanyDocumentRagIndexStatus.FAILED
    assert document.rag_indexing_error == ERROR_EMBED
    assert "sk-secret" not in (document.rag_indexing_error or "")


def test_retry_calls_index_again():
    service, db, chunks, embeddings = _service_with_mocks()
    document = _doc(rag_index_status=CompanyDocumentRagIndexStatus.FAILED)
    db.query.return_value.filter.return_value.first.return_value = document
    db.query.return_value.filter.return_value.one.return_value = document
    chunks.ingest_and_replace_chunks.return_value = [MagicMock()]
    embeddings.embed_company_document_chunks.return_value = EmbedChunksResult(
        company_document_id=42,
        chunk_count=1,
        embedded_count=1,
        skipped_count=0,
        embedding_model="m",
        embedding_dimensions=768,
    )

    service.retry_document(42)

    assert document.rag_index_status == CompanyDocumentRagIndexStatus.READY
    assert chunks.ingest_and_replace_chunks.call_count == 1


def test_idempotent_second_index_reuses_replace_path():
    service, db, chunks, embeddings = _service_with_mocks()
    document = _doc(rag_index_status=CompanyDocumentRagIndexStatus.READY)
    db.query.return_value.filter.return_value.first.return_value = document
    db.query.return_value.filter.return_value.one.return_value = document
    chunks.ingest_and_replace_chunks.return_value = [MagicMock(), MagicMock()]
    embeddings.embed_company_document_chunks.return_value = EmbedChunksResult(
        company_document_id=42,
        chunk_count=2,
        embedded_count=0,
        skipped_count=2,
        embedding_model="m",
        embedding_dimensions=768,
    )

    service.index_document(42)
    service.index_document(42)

    assert chunks.ingest_and_replace_chunks.call_count == 2
    assert document.rag_index_status == CompanyDocumentRagIndexStatus.READY


def test_missing_document_returns_none():
    service, db, chunks, embeddings = _service_with_mocks()
    db.query.return_value.filter.return_value.first.return_value = None
    assert service.index_document(999) is None
    chunks.ingest_and_replace_chunks.assert_not_called()


def test_private_document_not_indexed_by_chunk_service_contract():
    """Guard: indexing path only loads CompanyDocument rows from DB."""
    from app.ai.rag.chunking.service import KnowledgeChunkService

    service = KnowledgeChunkService(MagicMock())
    private = MagicMock(spec=PrivateDocument)
    with pytest.raises(UnsupportedDocumentError):
        service.replace_chunks_from_ingestion(private, MagicMock())  # type: ignore[arg-type]


def test_upload_endpoint_schedules_background_indexing():
    from fastapi import BackgroundTasks

    from app.api.v1 import library_documents as lib_api

    background = MagicMock(spec=BackgroundTasks)
    service = MagicMock()
    document = SimpleNamespace(
        id=7,
        title="T",
        description=None,
        category_id=1,
        category=SimpleNamespace(slug="policies", label="Policies"),
        original_filename="a.pdf",
        content_type="application/pdf",
        size_bytes=10,
        version=1,
        uploaded_by_user_id=1,
        uploaded_by=SimpleNamespace(first_name="A", last_name="B"),
        status=CompanyDocumentStatus.ACTIVE,
        rag_index_status=CompanyDocumentRagIndexStatus.PENDING,
        rag_indexed_at=None,
        rag_indexing_error=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    service.upload.return_value = document
    service._require_document.return_value = document

    import asyncio
    from unittest.mock import AsyncMock

    file = MagicMock()
    file.filename = "a.pdf"
    file.content_type = "application/pdf"
    file.read = AsyncMock(return_value=b"%PDF-1.4 fake")

    user = MagicMock()

    response = asyncio.run(
        lib_api.upload_company_document(
            background_tasks=background,
            title="T",
            category_id=1,
            description=None,
            file=file,
            current_user=user,
            service=service,
        )
    )
    assert response.id == 7
    background.add_task.assert_called_once()
    args = background.add_task.call_args[0]
    assert args[0].__name__ == "run_company_document_indexing"
    assert args[1] == 7


def test_archive_does_not_call_indexing():
    """Archive is metadata-only; indexing service is not invoked by update."""
    from app.modules.documents.library_service import CompanyDocumentService
    from app.modules.documents.schemas import CompanyDocumentUpdateRequest

    repo = MagicMock()
    document = _doc(status=CompanyDocumentStatus.ACTIVE)
    repo.get_by_id.return_value = document
    repo.save.side_effect = lambda d: d
    service = CompanyDocumentService(repo, MagicMock())
    with patch("app.ai.rag.indexing.service.CompanyDocumentIndexingService") as mock_idx:
        service.update(
            42,
            CompanyDocumentUpdateRequest(status=CompanyDocumentStatus.ARCHIVED),
        )
        mock_idx.assert_not_called()
    assert document.status == CompanyDocumentStatus.ARCHIVED
