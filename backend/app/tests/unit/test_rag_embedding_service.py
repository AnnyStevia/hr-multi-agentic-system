"""Unit tests for EmbeddingService (mocked provider, no live Gemini)."""

from unittest.mock import MagicMock

import pytest

from app.ai.rag.chunking.repository import KnowledgeChunkRepository
from app.ai.rag.embeddings.exceptions import EmbeddingValidationError
from app.ai.rag.embeddings.schemas import EmbeddingResult, EmbeddingUsage
from app.ai.rag.embeddings.service import EmbeddingService
from app.ai.rag.models import KnowledgeChunk


def _chunk(**overrides) -> KnowledgeChunk:
    values = {
        "id": 1,
        "company_document_id": 42,
        "content": "Leave policy text.",
        "page_start": 1,
        "page_end": 1,
        "chunk_index": 0,
        "content_hash": "abc",
        "chunk_metadata": {},
        "embedding": None,
        "embedding_model": None,
        "embedding_dimensions": None,
    }
    values.update(overrides)
    chunk = MagicMock(spec=KnowledgeChunk)
    for key, value in values.items():
        setattr(chunk, key, value)
    return chunk


def _vector(n: int = 3, fill: float = 0.5) -> list[float]:
    return [fill] * n


def test_skips_already_embedded_matching_model_and_dims():
    db = MagicMock()
    repo = MagicMock(spec=KnowledgeChunkRepository)
    existing = _chunk(
        embedding=_vector(),
        embedding_model="gemini-embedding-2",
        embedding_dimensions=3,
    )
    repo.list_by_company_document_id.return_value = [existing]
    provider = MagicMock()

    service = EmbeddingService(
        db,
        provider,
        repository=repo,
        embedding_model="gemini-embedding-2",
        embedding_dimensions=3,
    )
    result = service.embed_company_document_chunks(42)

    assert result.embedded_count == 0
    assert result.skipped_count == 1
    provider.embed_texts.assert_not_called()
    db.commit.assert_not_called()


def test_re_embeds_when_model_changes():
    db = MagicMock()
    repo = MagicMock(spec=KnowledgeChunkRepository)
    chunk = _chunk(
        embedding=_vector(),
        embedding_model="old-model",
        embedding_dimensions=3,
    )
    repo.list_by_company_document_id.return_value = [chunk]
    repo.save_embeddings.side_effect = lambda rows: rows
    provider = MagicMock()
    provider.embed_texts.return_value = [
        EmbeddingResult(vector=_vector(fill=0.9), model="gemini-embedding-2", dimensions=3)
    ]

    service = EmbeddingService(
        db,
        provider,
        repository=repo,
        embedding_model="gemini-embedding-2",
        embedding_dimensions=3,
    )
    result = service.embed_company_document_chunks(42)

    assert result.embedded_count == 1
    assert result.skipped_count == 0
    assert chunk.embedding == _vector(fill=0.9)
    assert chunk.embedding_model == "gemini-embedding-2"
    assert chunk.embedding_dimensions == 3
    db.commit.assert_called_once()


def test_re_embeds_when_dimensions_change():
    db = MagicMock()
    repo = MagicMock(spec=KnowledgeChunkRepository)
    chunk = _chunk(
        embedding=[0.1, 0.2],
        embedding_model="gemini-embedding-2",
        embedding_dimensions=2,
    )
    repo.list_by_company_document_id.return_value = [chunk]
    repo.save_embeddings.side_effect = lambda rows: rows
    provider = MagicMock()
    provider.embed_texts.return_value = [
        EmbeddingResult(vector=_vector(3), model="gemini-embedding-2", dimensions=3)
    ]

    service = EmbeddingService(
        db,
        provider,
        repository=repo,
        embedding_model="gemini-embedding-2",
        embedding_dimensions=3,
    )
    result = service.embed_company_document_chunks(42)
    assert result.embedded_count == 1
    assert chunk.embedding_dimensions == 3


def test_persists_embedding_metadata_and_usage():
    db = MagicMock()
    repo = MagicMock(spec=KnowledgeChunkRepository)
    chunk = _chunk()
    repo.list_by_company_document_id.return_value = [chunk]
    repo.save_embeddings.side_effect = lambda rows: rows
    provider = MagicMock()
    provider.embed_texts.return_value = [
        EmbeddingResult(
            vector=_vector(),
            model="gemini-embedding-2",
            dimensions=3,
            usage=EmbeddingUsage(input_tokens=11, total_tokens=11),
        )
    ]

    service = EmbeddingService(
        db,
        provider,
        repository=repo,
        embedding_model="gemini-embedding-2",
        embedding_dimensions=3,
    )
    result = service.embed_company_document_chunks(42)

    assert result.usage_input_tokens == 11
    assert result.usage_total_tokens == 11
    assert chunk.embedding_model == "gemini-embedding-2"
    assert chunk.embedding_dimensions == 3
    repo.save_embeddings.assert_called_once()


def test_validation_failure_rolls_back_without_commit():
    db = MagicMock()
    repo = MagicMock(spec=KnowledgeChunkRepository)
    chunk = _chunk()
    repo.list_by_company_document_id.return_value = [chunk]
    provider = MagicMock()
    provider.embed_texts.return_value = [
        EmbeddingResult(vector=[1.0], model="gemini-embedding-2", dimensions=3)
    ]

    service = EmbeddingService(
        db,
        provider,
        repository=repo,
        embedding_model="gemini-embedding-2",
        embedding_dimensions=3,
    )
    with pytest.raises(EmbeddingValidationError, match="dimension mismatch"):
        service.embed_company_document_chunks(42)

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_provider_count_mismatch_rolls_back():
    db = MagicMock()
    repo = MagicMock(spec=KnowledgeChunkRepository)
    chunks = [_chunk(id=1, chunk_index=0), _chunk(id=2, chunk_index=1, content="b")]
    repo.list_by_company_document_id.return_value = chunks
    provider = MagicMock()
    provider.embed_texts.return_value = [
        EmbeddingResult(vector=_vector(), model="gemini-embedding-2", dimensions=3)
    ]

    service = EmbeddingService(
        db,
        provider,
        repository=repo,
        embedding_model="gemini-embedding-2",
        embedding_dimensions=3,
        max_batch_size=32,
    )
    with pytest.raises(EmbeddingValidationError, match="returned 1 embeddings"):
        service.embed_company_document_chunks(42)
    db.rollback.assert_called_once()
