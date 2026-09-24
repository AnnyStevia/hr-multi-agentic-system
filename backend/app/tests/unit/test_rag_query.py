"""Unit tests for RAG query pipeline (mocked embed + hybrid; no Gemini)."""

from unittest.mock import MagicMock

import pytest

from app.ai.core.context.models import AIExecutionContext
from app.ai.rag.embeddings.exceptions import EmbeddingProviderError
from app.ai.rag.embeddings.gemini import DEFAULT_QUERY_TASK_TYPE
from app.ai.rag.embeddings.schemas import EmbeddingResult
from app.ai.rag.embeddings.service import EmbeddingService
from app.ai.rag.query import (
    ContextAssembler,
    RAGQueryRequest,
    RAGQueryService,
    RAGQueryValidationError,
)
from app.ai.rag.query.exceptions import RAGQueryError
from app.ai.rag.retrieval.exceptions import RetrievalError
from app.ai.rag.retrieval.filters import COMPANY_DOCUMENTS_READ
from app.ai.rag.retrieval.schemas import HybridRetrievalHit


def _ctx() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=1,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({COMPANY_DOCUMENTS_READ}),
        employee_id=1,
        candidate_id=None,
    )


def _hit(chunk_id: int, content: str, *, rrf: float = 0.1) -> HybridRetrievalHit:
    return HybridRetrievalHit(
        chunk_id=chunk_id,
        company_document_id=2,
        content=content,
        page_start=1,
        page_end=1,
        chunk_index=chunk_id,
        content_hash="a" * 64,
        metadata={"chunk_index": chunk_id},
        vector_similarity=0.9,
        fts_rank=0.2,
        rrf_score=rrf,
    )


def test_context_assembler_preserves_order_dedupes_and_limits():
    hits = [
        _hit(1, "aaa", rrf=0.3),
        _hit(1, "dup", rrf=0.2),
        _hit(2, "bbbb", rrf=0.1),
        _hit(3, "ccccc", rrf=0.05),
    ]
    assembled = ContextAssembler(max_chunks=2, max_characters=100).assemble(hits)
    assert [c.chunk_id for c in assembled] == [1, 2]
    assert assembled[0].content == "aaa"
    assert assembled[0].rrf_score == 0.3


def test_context_assembler_stops_before_partial_chunk():
    hits = [_hit(1, "12345", rrf=0.2), _hit(2, "67890", rrf=0.1)]
    assembled = ContextAssembler(max_chunks=5, max_characters=7).assemble(hits)
    assert [c.chunk_id for c in assembled] == [1]
    assert len(assembled[0].content) == 5


def test_context_assembler_empty():
    assert ContextAssembler().assemble([]) == []


def test_query_validation():
    embedding = MagicMock()
    hybrid = MagicMock()
    service = RAGQueryService(
        embedding_service=embedding,
        hybrid_service=hybrid,
        query_max_characters=10,
    )
    with pytest.raises(RAGQueryValidationError, match="empty"):
        service.query(RAGQueryRequest(query="   ", context=_ctx()))
    with pytest.raises(RAGQueryValidationError, match="max length"):
        service.query(RAGQueryRequest(query="x" * 11, context=_ctx()))
    embedding.embed_query.assert_not_called()
    hybrid.retrieve.assert_not_called()


def test_pipeline_embeds_once_and_forwards_to_hybrid():
    embedding = MagicMock(spec=EmbeddingService)
    embedding.embed_query.return_value = EmbeddingResult(
        vector=[0.1, 0.2, 0.3],
        model="gemini-embedding-2",
        dimensions=3,
    )
    hybrid = MagicMock()
    hybrid.retrieve.return_value = [_hit(9, "Casablanca office")]
    service = RAGQueryService(
        embedding_service=embedding,
        hybrid_service=hybrid,
        assembler=ContextAssembler(max_chunks=5, max_characters=1000),
        embedding_dimensions=3,
        default_top_k=5,
        max_top_k=20,
    )
    ctx = _ctx()
    result = service.query(
        RAGQueryRequest(query="  Casablanca  ", context=ctx, top_k=3)
    )

    embedding.embed_query.assert_called_once_with("Casablanca")
    hybrid.retrieve.assert_called_once()
    hybrid_req = hybrid.retrieve.call_args.args[0]
    assert hybrid_req.query_text == "Casablanca"
    assert hybrid_req.query_embedding == [0.1, 0.2, 0.3]
    assert hybrid_req.context is ctx
    assert hybrid_req.top_k == 3

    assert result.has_context is True
    assert result.retrieval_count == 1
    assert result.selected_context_count == 1
    assert result.context[0].chunk_id == 9
    assert result.context[0].company_document_id == 2
    assert result.embedding_model == "gemini-embedding-2"
    assert result.embedding_dimensions == 3


def test_empty_retrieval_produces_empty_context():
    embedding = MagicMock()
    embedding.embed_query.return_value = EmbeddingResult(
        vector=[0.0] * 3, model="gemini-embedding-2", dimensions=3
    )
    hybrid = MagicMock()
    hybrid.retrieve.return_value = []
    service = RAGQueryService(
        embedding_service=embedding,
        hybrid_service=hybrid,
        embedding_dimensions=3,
    )
    result = service.query(RAGQueryRequest(query="nothing", context=_ctx()))
    assert result.has_context is False
    assert result.results == []
    assert result.context == []
    assert result.retrieval_count == 0


def test_embedding_failure_wrapped():
    embedding = MagicMock()
    embedding.embed_query.side_effect = EmbeddingProviderError("quota")
    hybrid = MagicMock()
    service = RAGQueryService(embedding_service=embedding, hybrid_service=hybrid)
    with pytest.raises(RAGQueryError, match="Query embedding failed"):
        service.query(RAGQueryRequest(query="hi", context=_ctx()))
    hybrid.retrieve.assert_not_called()


def test_retrieval_failure_wrapped():
    embedding = MagicMock()
    embedding.embed_query.return_value = EmbeddingResult(
        vector=[0.0, 1.0], model="m", dimensions=2
    )
    hybrid = MagicMock()
    hybrid.retrieve.side_effect = RetrievalError("db down")
    service = RAGQueryService(
        embedding_service=embedding,
        hybrid_service=hybrid,
        embedding_dimensions=2,
    )
    with pytest.raises(RAGQueryError, match="Hybrid retrieval failed"):
        service.query(RAGQueryRequest(query="hi", context=_ctx()))


def test_embed_query_uses_retrieval_query_task_type():
    provider = MagicMock()
    provider.embed_text.return_value = EmbeddingResult(
        vector=[0.5, 0.5], model="gemini-embedding-2", dimensions=2
    )
    service = EmbeddingService(None, provider, embedding_dimensions=2)
    result = service.embed_query("leave balance")
    provider.embed_text.assert_called_once_with(
        "leave balance", task_type=DEFAULT_QUERY_TASK_TYPE
    )
    assert result.vector == [0.5, 0.5]
