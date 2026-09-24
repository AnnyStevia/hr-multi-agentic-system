"""Unit tests for KnowledgeChunk persistence (mocked DB, no Gemini)."""

from unittest.mock import MagicMock

import pytest

from app.ai.rag.chunking import DocumentChunker, KnowledgeChunkService
from app.ai.rag.chunking.chunker import pages_to_ingestion_result
from app.ai.rag.chunking.repository import KnowledgeChunkRepository
from app.ai.rag.exceptions import UnsupportedDocumentError
from app.ai.rag.ingestion.schemas import IngestedPage
from app.ai.rag.models import KnowledgeChunk
from app.modules.documents.models import CompanyDocument, CompanyDocumentStatus, PrivateDocument


def _company_document(**overrides) -> CompanyDocument:
    values = {
        "id": 42,
        "title": "Handbook",
        "description": None,
        "category_id": 1,
        "original_filename": "handbook.pdf",
        "content_type": "application/pdf",
        "size_bytes": 100,
        "storage_key": "company-documents/42/handbook.pdf",
        "version": 2,
        "uploaded_by_user_id": 1,
        "status": CompanyDocumentStatus.ACTIVE,
    }
    values.update(overrides)
    document = MagicMock(spec=CompanyDocument)
    for key, value in values.items():
        setattr(document, key, value)
    return document


def test_replace_chunks_creates_rows_with_null_embeddings():
    db = MagicMock()
    repo = MagicMock(spec=KnowledgeChunkRepository)
    repo.delete_by_company_document_id.return_value = 0
    repo.add_many.side_effect = lambda rows: rows

    service = KnowledgeChunkService(
        db,
        chunker=DocumentChunker(chunk_size=800, overlap=100),
        repository=repo,
    )
    document = _company_document()
    ingestion = pages_to_ingestion_result(
        [IngestedPage(page_number=1, text="Leave policy text.")],
        company_document_id=document.id,
    )

    rows = service.replace_chunks_from_ingestion(document, ingestion)

    repo.delete_by_company_document_id.assert_called_once_with(42)
    repo.add_many.assert_called_once()
    db.commit.assert_called_once()
    assert len(rows) == 1
    row = rows[0]
    assert isinstance(row, KnowledgeChunk)
    assert row.company_document_id == 42
    assert row.chunk_index == 0
    assert row.page_start == 1
    assert row.embedding is None
    assert row.embedding_model is None
    assert row.embedding_dimensions is None
    assert row.content_hash
    assert row.chunk_metadata["document_version"] == 2


def test_repeated_ingestion_deletes_before_insert_no_append():
    db = MagicMock()
    repo = MagicMock(spec=KnowledgeChunkRepository)
    repo.delete_by_company_document_id.return_value = 3
    repo.add_many.side_effect = lambda rows: rows
    service = KnowledgeChunkService(
        db,
        chunker=DocumentChunker(chunk_size=800, overlap=100),
        repository=repo,
    )
    document = _company_document()
    ingestion = pages_to_ingestion_result(
        [IngestedPage(page_number=1, text="Same content.")],
        company_document_id=42,
    )

    first = service.replace_chunks_from_ingestion(document, ingestion)
    second = service.replace_chunks_from_ingestion(document, ingestion)

    assert repo.delete_by_company_document_id.call_count == 2
    assert len(first) == len(second) == 1
    assert first[0].content_hash == second[0].content_hash


def test_rollback_on_failure_leaves_no_partial_commit():
    db = MagicMock()
    repo = MagicMock(spec=KnowledgeChunkRepository)
    repo.delete_by_company_document_id.return_value = 0
    repo.add_many.side_effect = RuntimeError("db write failed")

    service = KnowledgeChunkService(
        db,
        chunker=DocumentChunker(chunk_size=800, overlap=100),
        repository=repo,
    )
    document = _company_document()
    ingestion = pages_to_ingestion_result(
        [IngestedPage(page_number=1, text="Content")],
        company_document_id=42,
    )

    with pytest.raises(RuntimeError, match="db write failed"):
        service.replace_chunks_from_ingestion(document, ingestion)

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_empty_ingestion_deletes_existing_and_inserts_nothing():
    db = MagicMock()
    repo = MagicMock(spec=KnowledgeChunkRepository)
    repo.delete_by_company_document_id.return_value = 2
    service = KnowledgeChunkService(
        db,
        chunker=DocumentChunker(chunk_size=50, overlap=5),
        repository=repo,
    )
    document = _company_document()
    ingestion = pages_to_ingestion_result([], company_document_id=42)

    rows = service.replace_chunks_from_ingestion(document, ingestion)

    assert rows == []
    repo.delete_by_company_document_id.assert_called_once_with(42)
    repo.add_many.assert_not_called()
    db.commit.assert_called_once()


def test_rejects_private_document():
    db = MagicMock()
    service = KnowledgeChunkService(db, chunker=DocumentChunker())
    private = MagicMock(spec=PrivateDocument)
    ingestion = pages_to_ingestion_result(
        [IngestedPage(page_number=1, text="secret")],
        company_document_id=1,
    )
    with pytest.raises(UnsupportedDocumentError):
        service.replace_chunks_from_ingestion(private, ingestion)  # type: ignore[arg-type]


def test_rejects_plain_object_not_company_document():
    db = MagicMock()
    service = KnowledgeChunkService(db, chunker=DocumentChunker())
    ingestion = pages_to_ingestion_result(
        [IngestedPage(page_number=1, text="x")],
        company_document_id=1,
    )
    with pytest.raises(UnsupportedDocumentError):
        service.replace_chunks_from_ingestion(object(), ingestion)  # type: ignore[arg-type]
