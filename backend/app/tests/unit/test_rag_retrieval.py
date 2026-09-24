"""Unit tests for retrieval filters and service validation (no Gemini / no PG)."""

from unittest.mock import MagicMock

import pytest

from app.ai.core.context.models import AIExecutionContext
from app.ai.rag.retrieval import RetrievalService
from app.ai.rag.retrieval.exceptions import (
    RetrievalAuthorizationError,
    RetrievalValidationError,
)
from app.ai.rag.retrieval.filters import (
    COMPANY_DOCUMENTS_READ,
    company_document_eligibility_clause,
    is_hr_staff,
    require_company_documents_read,
)
from app.ai.rag.retrieval.schemas import RetrievalRequest
from app.modules.identity.hr_access import HR_STAFF_ROLE_NAMES


def _context(
    *,
    roles: set[str],
    permissions: set[str],
    user_id: int = 1,
) -> AIExecutionContext:
    return AIExecutionContext(
        user_id=user_id,
        role_names=frozenset(roles),
        permission_names=frozenset(permissions),
        employee_id=10,
        candidate_id=None,
    )


def test_is_hr_staff_matches_core_hr_set():
    assert is_hr_staff(_context(roles={"admin"}, permissions={COMPANY_DOCUMENTS_READ}))
    assert is_hr_staff(_context(roles={"hr"}, permissions={COMPANY_DOCUMENTS_READ}))
    assert not is_hr_staff(
        _context(roles={"employee"}, permissions={COMPANY_DOCUMENTS_READ})
    )
    assert not is_hr_staff(
        _context(roles={"manager"}, permissions={COMPANY_DOCUMENTS_READ})
    )
    assert HR_STAFF_ROLE_NAMES == frozenset({"admin", "hr"})


def test_require_company_documents_read():
    require_company_documents_read(
        _context(roles={"employee"}, permissions={COMPANY_DOCUMENTS_READ})
    )
    with pytest.raises(RetrievalAuthorizationError, match="company_documents:read"):
        require_company_documents_read(
            _context(roles={"candidate"}, permissions=set())
        )


def test_eligibility_clause_active_only_for_non_hr():
    clause = company_document_eligibility_clause(
        _context(roles={"employee"}, permissions={COMPANY_DOCUMENTS_READ})
    )
    assert clause is not None
    compiled = str(clause.compile(compile_kwargs={"literal_binds": True}))
    assert "active" in compiled.lower()


def test_eligibility_clause_none_for_hr():
    assert (
        company_document_eligibility_clause(
            _context(roles={"hr"}, permissions={COMPANY_DOCUMENTS_READ})
        )
        is None
    )


def test_dimension_mismatch():
    service = RetrievalService(
        MagicMock(),
        repository=MagicMock(),
        expected_dimensions=768,
        default_top_k=5,
        max_top_k=20,
    )
    with pytest.raises(RetrievalValidationError, match="dimension mismatch"):
        service.retrieve(
            RetrievalRequest(
                query_embedding=[0.1, 0.2],
                context=_context(
                    roles={"employee"}, permissions={COMPANY_DOCUMENTS_READ}
                ),
            )
        )


def test_top_k_bounds():
    repo = MagicMock()
    repo.search.return_value = []
    service = RetrievalService(
        MagicMock(),
        repository=repo,
        expected_dimensions=3,
        default_top_k=5,
        max_top_k=10,
    )
    ctx = _context(roles={"employee"}, permissions={COMPANY_DOCUMENTS_READ})

    with pytest.raises(RetrievalValidationError, match=">= 1"):
        service.retrieve(
            RetrievalRequest(query_embedding=[0.0, 0.0, 1.0], context=ctx, top_k=0)
        )
    with pytest.raises(RetrievalValidationError, match="<= 10"):
        service.retrieve(
            RetrievalRequest(query_embedding=[0.0, 0.0, 1.0], context=ctx, top_k=11)
        )

    service.retrieve(
        RetrievalRequest(query_embedding=[0.0, 0.0, 1.0], context=ctx, top_k=None)
    )
    assert repo.search.call_args.kwargs["top_k"] == 5


def test_missing_permission_before_repository():
    repo = MagicMock()
    service = RetrievalService(
        MagicMock(),
        repository=repo,
        expected_dimensions=2,
        default_top_k=5,
        max_top_k=20,
    )
    with pytest.raises(RetrievalAuthorizationError):
        service.retrieve(
            RetrievalRequest(
                query_embedding=[0.1, 0.2],
                context=_context(roles={"candidate"}, permissions=set()),
            )
        )
    repo.search.assert_not_called()


def test_knowledge_chunk_join_target_is_company_documents_only():
    from app.ai.rag.models import KnowledgeChunk

    fks = list(KnowledgeChunk.__table__.c.company_document_id.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column.table.name == "company_documents"
