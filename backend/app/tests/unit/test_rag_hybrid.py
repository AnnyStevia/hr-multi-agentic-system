"""Unit tests for RRF fusion and hybrid validation (no Gemini / no PG)."""

from unittest.mock import MagicMock

import pytest

from app.ai.core.context.models import AIExecutionContext
from app.ai.rag.retrieval import COMPANY_DOCUMENTS_READ, HybridRetrievalService
from app.ai.rag.retrieval.exceptions import (
    RetrievalAuthorizationError,
    RetrievalValidationError,
)
from app.ai.rag.retrieval.repository import RetrievalRow
from app.ai.rag.retrieval.fts_repository import FtsRetrievalRow
from app.ai.rag.retrieval.rrf import fuse_rankings
from app.ai.rag.retrieval.schemas import HybridRequest


def test_rrf_boosts_intersection():
    # Both lists: id 1 rank1; vector-only 2; fts-only 3
    fused = fuse_rankings([1, 2], [1, 3], k=60)
    assert fused[0][0] == 1
    score_1 = 1 / 61 + 1 / 61
    score_2 = 1 / 62
    score_3 = 1 / 62
    by_id = dict(fused)
    assert by_id[1] == pytest.approx(score_1)
    assert by_id[2] == pytest.approx(score_2)
    assert by_id[3] == pytest.approx(score_3)


def test_rrf_one_sided_and_empty():
    only_vector = fuse_rankings([10, 20], [], k=60)
    assert [cid for cid, _ in only_vector] == [10, 20]
    assert only_vector[0][1] == pytest.approx(1 / 61)
    assert fuse_rankings([], [], k=60) == []
    only_fts = fuse_rankings([], [5], k=60)
    assert only_fts[0][0] == 5


def test_rrf_tie_break_by_chunk_id():
    # Equal scores: each appears once as rank 1 in its own list
    fused = fuse_rankings([2], [1], k=60)
    assert fused[0][1] == fused[1][1]
    assert [cid for cid, _ in fused] == [1, 2]


def test_rrf_dedupes_within_list():
    fused = fuse_rankings([1, 1, 2], k=60)
    assert [cid for cid, _ in fused] == [1, 2]


def test_rrf_rejects_invalid_k():
    with pytest.raises(ValueError):
        fuse_rankings([1], k=0)


def _ctx(permissions: set[str] | None = None) -> AIExecutionContext:
    perms = {COMPANY_DOCUMENTS_READ} if permissions is None else permissions
    return AIExecutionContext(
        user_id=1,
        role_names=frozenset({"employee"}),
        permission_names=frozenset(perms),
        employee_id=1,
        candidate_id=None,
    )


def test_hybrid_requires_permission():
    service = HybridRetrievalService(
        MagicMock(),
        vector_repository=MagicMock(),
        fts_repository=MagicMock(),
        expected_dimensions=2,
    )
    with pytest.raises(RetrievalAuthorizationError):
        service.retrieve(
            HybridRequest(
                query_text="leave",
                query_embedding=[0.0, 1.0],
                context=_ctx(permissions=set()),
            )
        )


def test_hybrid_validates_dims_and_candidates():
    service = HybridRetrievalService(
        MagicMock(),
        vector_repository=MagicMock(),
        fts_repository=MagicMock(),
        expected_dimensions=3,
        max_candidates=5,
        vector_candidates=10,
        fts_candidates=2,
    )
    with pytest.raises(RetrievalValidationError, match="dimension"):
        service.retrieve(
            HybridRequest(
                query_text="x",
                query_embedding=[0.0, 1.0],
                context=_ctx(),
            )
        )

    service2 = HybridRetrievalService(
        MagicMock(),
        vector_repository=MagicMock(),
        fts_repository=MagicMock(),
        expected_dimensions=2,
        max_candidates=5,
        vector_candidates=10,
        fts_candidates=2,
    )
    with pytest.raises(RetrievalValidationError, match="vector candidates"):
        service2.retrieve(
            HybridRequest(
                query_text="x",
                query_embedding=[0.0, 1.0],
                context=_ctx(),
            )
        )


def test_hybrid_merges_vector_and_fts_payloads():
    vector = MagicMock()
    fts = MagicMock()
    vector.search.return_value = [
        RetrievalRow(
            chunk_id=1,
            company_document_id=10,
            content="both",
            similarity=0.9,
            page_start=1,
            page_end=1,
            chunk_index=0,
            content_hash="a" * 64,
            metadata={},
        )
    ]
    fts.search.return_value = [
        FtsRetrievalRow(
            chunk_id=1,
            company_document_id=10,
            content="both",
            fts_rank=0.5,
            page_start=1,
            page_end=1,
            chunk_index=0,
            content_hash="a" * 64,
            metadata={},
        ),
        FtsRetrievalRow(
            chunk_id=2,
            company_document_id=11,
            content="fts only",
            fts_rank=0.4,
            page_start=1,
            page_end=1,
            chunk_index=0,
            content_hash="b" * 64,
            metadata={},
        ),
    ]
    service = HybridRetrievalService(
        MagicMock(),
        vector_repository=vector,
        fts_repository=fts,
        expected_dimensions=2,
        default_top_k=5,
        max_top_k=20,
        vector_candidates=10,
        fts_candidates=10,
        max_candidates=20,
        rrf_k=60,
    )
    hits = service.retrieve(
        HybridRequest(
            query_text="policy",
            query_embedding=[0.0, 1.0],
            context=_ctx(),
            top_k=5,
        )
    )
    assert hits[0].chunk_id == 1
    assert hits[0].vector_similarity == 0.9
    assert hits[0].fts_rank == 0.5
    assert hits[0].rrf_score == pytest.approx(1 / 61 + 1 / 61)
    assert service.last_debug is not None
    assert service.last_debug.vector_candidate_count == 1
    assert service.last_debug.fts_candidate_count == 2
