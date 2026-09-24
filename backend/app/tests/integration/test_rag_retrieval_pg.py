"""Postgres integration: secure cosine retrieval with SQL-level access filters.

No Gemini — uses controlled fake embeddings.
"""

from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import sessionmaker

from app.ai.core.context.models import AIExecutionContext
from app.ai.rag.models import KnowledgeChunk
from app.ai.rag.retrieval import RetrievalService
from app.ai.rag.retrieval.exceptions import RetrievalAuthorizationError
from app.ai.rag.retrieval.filters import COMPANY_DOCUMENTS_READ
from app.ai.rag.retrieval.schemas import RetrievalRequest
from app.core.config import settings
from app.modules.documents.models import (
    CompanyDocument,
    CompanyDocumentStatus,
)


DIM = 768


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _unit(*, axis: int = 0) -> list[float]:
    vector = [0.0] * DIM
    vector[axis % DIM] = 1.0
    return vector


def _near_unit(*, axis: int = 0, weight: float = 0.8) -> list[float]:
    """Unit-ish vector slightly off the axis (lower cosine similarity than exact)."""
    vector = [0.0] * DIM
    other = (axis + 1) % DIM
    vector[axis] = weight
    vector[other] = (1.0 - weight**2) ** 0.5
    return vector


def _context(*, roles: set[str], permissions: set[str]) -> AIExecutionContext:
    return AIExecutionContext(
        user_id=1,
        role_names=frozenset(roles),
        permission_names=frozenset(permissions),
        employee_id=1,
        candidate_id=None,
    )


@pytest.fixture
def pg_session():
    url = settings.database_url
    if not url.startswith("postgresql"):
        pytest.skip("DATABASE_URL is not PostgreSQL")

    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            table = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'rag_document_chunks'"
                )
            ).fetchone()
            if table is None:
                pytest.skip("rag_document_chunks missing — run alembic upgrade head")
            cat = conn.execute(
                text(
                    "SELECT id FROM company_document_categories "
                    "ORDER BY id LIMIT 1"
                )
            ).fetchone()
            user = conn.execute(
                text("SELECT id FROM users ORDER BY id LIMIT 1")
            ).fetchone()
            if cat is None or user is None:
                pytest.skip("Need company_document_categories and users rows")
            category_id, user_id = cat[0], user[0]
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL unreachable: {exc}")
    except ProgrammingError as exc:
        pytest.skip(f"PostgreSQL query failed: {exc}")

    Session = sessionmaker(bind=engine)
    session = Session()
    created_doc_ids: list[int] = []
    try:
        yield session, category_id, user_id, created_doc_ids
    finally:
        session.rollback()
        for doc_id in created_doc_ids:
            session.query(KnowledgeChunk).filter(
                KnowledgeChunk.company_document_id == doc_id
            ).delete(synchronize_session=False)
            session.query(CompanyDocument).filter(CompanyDocument.id == doc_id).delete(
                synchronize_session=False
            )
        session.commit()
        session.close()


def _add_doc(
    session,
    *,
    category_id: int,
    user_id: int,
    title: str,
    status: CompanyDocumentStatus,
    created_doc_ids: list[int],
) -> CompanyDocument:
    doc = CompanyDocument(
        title=title,
        description="retrieval test",
        category_id=category_id,
        original_filename=f"{title}.pdf",
        content_type="application/pdf",
        size_bytes=10,
        storage_key=f"company-documents/test/{title}.pdf",
        version=1,
        uploaded_by_user_id=user_id,
        status=status,
    )
    session.add(doc)
    session.flush()
    created_doc_ids.append(doc.id)
    return doc


def _add_chunk(
    session,
    *,
    doc: CompanyDocument,
    content: str,
    embedding: list[float] | None,
    chunk_index: int = 0,
) -> KnowledgeChunk:
    chunk = KnowledgeChunk(
        company_document_id=doc.id,
        content=content,
        page_start=1,
        page_end=1,
        chunk_index=chunk_index,
        content_hash=_hash(content),
        chunk_metadata={
            "company_document_id": doc.id,
            "chunk_index": chunk_index,
            "content_hash": _hash(content),
        },
        embedding=embedding,
        embedding_model="gemini-embedding-2" if embedding is not None else None,
        embedding_dimensions=len(embedding) if embedding is not None else None,
    )
    session.add(chunk)
    session.flush()
    return chunk


def test_employee_cannot_retrieve_more_similar_archived_document(pg_session):
    """Critical: inaccessible archived doc closer to query must NOT appear for employee."""
    session, category_id, user_id, created_doc_ids = pg_session
    query = _unit(axis=0)

    active = _add_doc(
        session,
        category_id=category_id,
        user_id=user_id,
        title="ret-active-a",
        status=CompanyDocumentStatus.ACTIVE,
        created_doc_ids=created_doc_ids,
    )
    archived = _add_doc(
        session,
        category_id=category_id,
        user_id=user_id,
        title="ret-archived-b",
        status=CompanyDocumentStatus.ARCHIVED,
        created_doc_ids=created_doc_ids,
    )

    # Active: slightly off-axis (less similar). Archived: exact query axis (more similar).
    chunk_a = _add_chunk(
        session, doc=active, content="active policy text", embedding=_near_unit(axis=0)
    )
    chunk_b = _add_chunk(
        session,
        doc=archived,
        content="archived secret policy",
        embedding=_unit(axis=0),
    )
    session.commit()

    employee = _context(
        roles={"employee"}, permissions={COMPANY_DOCUMENTS_READ}
    )
    service = RetrievalService(
        session,
        expected_dimensions=DIM,
        default_top_k=5,
        max_top_k=20,
        min_similarity=None,
    )
    hits = service.retrieve(
        RetrievalRequest(query_embedding=query, context=employee, top_k=5)
    )
    hit_ids = {h.chunk_id for h in hits}
    assert chunk_a.id in hit_ids
    assert chunk_b.id not in hit_ids
    assert all(h.company_document_id != archived.id for h in hits)

    hr = _context(roles={"hr"}, permissions={COMPANY_DOCUMENTS_READ})
    hr_hits = service.retrieve(
        RetrievalRequest(query_embedding=query, context=hr, top_k=5)
    )
    hr_ids = {h.chunk_id for h in hr_hits}
    assert chunk_b.id in hr_ids
    assert hr_hits[0].chunk_id == chunk_b.id


def test_missing_permission_raises(pg_session):
    session, *_ = pg_session
    service = RetrievalService(
        session, expected_dimensions=DIM, default_top_k=5, max_top_k=20
    )
    with pytest.raises(RetrievalAuthorizationError):
        service.retrieve(
            RetrievalRequest(
                query_embedding=_unit(axis=0),
                context=_context(roles={"candidate"}, permissions=set()),
            )
        )


def test_null_embeddings_ignored_and_provenance_returned(pg_session):
    session, category_id, user_id, created_doc_ids = pg_session
    query = _unit(axis=1)
    doc = _add_doc(
        session,
        category_id=category_id,
        user_id=user_id,
        title="ret-null-emb",
        status=CompanyDocumentStatus.ACTIVE,
        created_doc_ids=created_doc_ids,
    )
    _add_chunk(session, doc=doc, content="no vector", embedding=None, chunk_index=0)
    with_vec = _add_chunk(
        session,
        doc=doc,
        content="has vector content",
        embedding=_unit(axis=1),
        chunk_index=1,
    )
    session.commit()

    service = RetrievalService(
        session, expected_dimensions=DIM, default_top_k=5, max_top_k=20
    )
    hits = service.retrieve(
        RetrievalRequest(
            query_embedding=query,
            context=_context(roles={"employee"}, permissions={COMPANY_DOCUMENTS_READ}),
            top_k=5,
        )
    )
    matching = [h for h in hits if h.company_document_id == doc.id]
    assert len(matching) == 1
    hit = matching[0]
    assert hit.chunk_id == with_vec.id
    assert hit.content == "has vector content"
    assert hit.page_start == 1
    assert hit.page_end == 1
    assert hit.chunk_index == 1
    assert hit.content_hash == _hash("has vector content")
    assert hit.similarity > 0.99


def test_top_k_and_min_similarity_and_tie_break(pg_session):
    session, category_id, user_id, created_doc_ids = pg_session
    query = _unit(axis=0)
    doc = _add_doc(
        session,
        category_id=category_id,
        user_id=user_id,
        title="ret-topk",
        status=CompanyDocumentStatus.ACTIVE,
        created_doc_ids=created_doc_ids,
    )
    # Identical embeddings → same distance; order by chunk id ascending.
    c0 = _add_chunk(
        session, doc=doc, content="c0", embedding=_unit(axis=0), chunk_index=0
    )
    c1 = _add_chunk(
        session, doc=doc, content="c1", embedding=_unit(axis=0), chunk_index=1
    )
    _add_chunk(
        session,
        doc=doc,
        content="far",
        embedding=_unit(axis=3),
        chunk_index=2,
    )
    session.commit()

    service = RetrievalService(
        session,
        expected_dimensions=DIM,
        default_top_k=5,
        max_top_k=20,
        min_similarity=0.99,
    )
    hits = service.retrieve(
        RetrievalRequest(
            query_embedding=query,
            context=_context(roles={"employee"}, permissions={COMPANY_DOCUMENTS_READ}),
            top_k=2,
        )
    )
    doc_hits = [h for h in hits if h.company_document_id == doc.id]
    assert len(doc_hits) == 2
    assert [h.chunk_id for h in doc_hits] == sorted([c0.id, c1.id])
    assert all(h.similarity >= 0.99 for h in doc_hits)


def test_hnsw_index_exists(pg_session):
    session, *_ = pg_session
    row = session.execute(
        text(
            "SELECT 1 FROM pg_indexes "
            "WHERE indexname = 'ix_rag_document_chunks_embedding_hnsw'"
        )
    ).fetchone()
    if row is None:
        pytest.skip("HNSW index not created yet — run alembic upgrade head")
    assert row[0] == 1
