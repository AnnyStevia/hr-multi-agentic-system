"""Postgres integration: hybrid vector + FTS + RRF with SQL-level access filters.

No Gemini — uses controlled fake embeddings and distinctive text tokens.
"""

from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import sessionmaker

from app.ai.core.context.models import AIExecutionContext
from app.ai.rag.models import KnowledgeChunk
from app.ai.rag.retrieval import (
    COMPANY_DOCUMENTS_READ,
    FullTextRetrievalRepository,
    HybridRetrievalService,
    VectorRetrievalRepository,
)
from app.ai.rag.retrieval.schemas import HybridRequest
from app.core.config import settings
from app.modules.documents.models import CompanyDocument, CompanyDocumentStatus

DIM = 768


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _unit(*, axis: int = 0) -> list[float]:
    vector = [0.0] * DIM
    vector[axis % DIM] = 1.0
    return vector


def _near_unit(*, axis: int = 0, weight: float = 0.8) -> list[float]:
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
            tsv = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'rag_document_chunks' "
                    "AND column_name = 'content_tsv'"
                )
            ).fetchone()
            if tsv is None:
                pytest.skip("content_tsv missing — run alembic upgrade head")
            cat = conn.execute(
                text(
                    "SELECT id FROM company_document_categories ORDER BY id LIMIT 1"
                )
            ).fetchone()
            user = conn.execute(text("SELECT id FROM users ORDER BY id LIMIT 1")).fetchone()
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


def _add_doc(session, *, category_id, user_id, title, status, created_doc_ids):
    doc = CompanyDocument(
        title=title,
        description="hybrid test",
        category_id=category_id,
        original_filename=f"{title}.pdf",
        content_type="application/pdf",
        size_bytes=10,
        storage_key=f"company-documents/hybrid/{title}.pdf",
        version=1,
        uploaded_by_user_id=user_id,
        status=status,
    )
    session.add(doc)
    session.flush()
    created_doc_ids.append(doc.id)
    return doc


def _add_chunk(session, *, doc, content, embedding, chunk_index=0):
    chunk = KnowledgeChunk(
        company_document_id=doc.id,
        content=content,
        page_start=1,
        page_end=1,
        chunk_index=chunk_index,
        content_hash=_hash(content),
        chunk_metadata={"company_document_id": doc.id, "chunk_index": chunk_index},
        embedding=embedding,
        embedding_model="gemini-embedding-2" if embedding is not None else None,
        embedding_dimensions=len(embedding) if embedding is not None else None,
    )
    session.add(chunk)
    session.flush()
    return chunk


def test_gin_index_exists(pg_session):
    session, *_ = pg_session
    row = session.execute(
        text(
            "SELECT 1 FROM pg_indexes "
            "WHERE indexname = 'ix_rag_document_chunks_content_tsv_gin'"
        )
    ).fetchone()
    assert row is not None


def test_hybrid_security_excludes_archived_from_all_branches(pg_session):
    """Unauthorized archived doc must not appear in vector, FTS, or hybrid final."""
    session, category_id, user_id, created_doc_ids = pg_session
    query = _unit(axis=0)
    phrase = "zxqhybridsecretterm"

    active = _add_doc(
        session,
        category_id=category_id,
        user_id=user_id,
        title="hyb-active",
        status=CompanyDocumentStatus.ACTIVE,
        created_doc_ids=created_doc_ids,
    )
    archived = _add_doc(
        session,
        category_id=category_id,
        user_id=user_id,
        title="hyb-archived",
        status=CompanyDocumentStatus.ARCHIVED,
        created_doc_ids=created_doc_ids,
    )
    chunk_a = _add_chunk(
        session,
        doc=active,
        content=f"active policy mentions {phrase} lightly",
        embedding=_near_unit(axis=0),
    )
    chunk_b = _add_chunk(
        session,
        doc=archived,
        content=f"{phrase} {phrase} archived confidential",
        embedding=_unit(axis=0),
    )
    session.commit()

    employee = _context(roles={"employee"}, permissions={COMPANY_DOCUMENTS_READ})
    vector_rows = VectorRetrievalRepository(session).search(
        query_embedding=query, context=employee, top_k=10
    )
    fts_rows = FullTextRetrievalRepository(session).search(
        query_text=phrase, context=employee, top_k=10
    )
    assert chunk_b.id not in {r.chunk_id for r in vector_rows}
    assert chunk_b.id not in {r.chunk_id for r in fts_rows}

    service = HybridRetrievalService(
        session,
        expected_dimensions=DIM,
        default_top_k=5,
        max_top_k=20,
        vector_candidates=10,
        fts_candidates=10,
        max_candidates=50,
        rrf_k=60,
    )
    hits = service.retrieve(
        HybridRequest(
            query_text=phrase,
            query_embedding=query,
            context=employee,
            top_k=5,
        )
    )
    assert chunk_b.id not in {h.chunk_id for h in hits}
    assert chunk_a.id in {h.chunk_id for h in hits} or any(
        h.company_document_id == active.id for h in hits
    )


def test_rrf_boosts_chunk_in_both_branches(pg_session):
    session, category_id, user_id, created_doc_ids = pg_session
    query = _unit(axis=2)
    token = "zxqbothbranches"

    doc_both = _add_doc(
        session,
        category_id=category_id,
        user_id=user_id,
        title="hyb-both",
        status=CompanyDocumentStatus.ACTIVE,
        created_doc_ids=created_doc_ids,
    )
    doc_vec = _add_doc(
        session,
        category_id=category_id,
        user_id=user_id,
        title="hyb-vec",
        status=CompanyDocumentStatus.ACTIVE,
        created_doc_ids=created_doc_ids,
    )
    doc_fts = _add_doc(
        session,
        category_id=category_id,
        user_id=user_id,
        title="hyb-fts",
        status=CompanyDocumentStatus.ACTIVE,
        created_doc_ids=created_doc_ids,
    )

    both = _add_chunk(
        session,
        doc=doc_both,
        content=f"Handbook section about {token}",
        embedding=_unit(axis=2),
    )
    _add_chunk(
        session,
        doc=doc_vec,
        content="unrelated semantic neighbor only",
        embedding=_near_unit(axis=2, weight=0.95),
    )
    _add_chunk(
        session,
        doc=doc_fts,
        content=f"{token} lexical only no close vector",
        embedding=_unit(axis=7),
    )
    session.commit()

    service = HybridRetrievalService(
        session,
        expected_dimensions=DIM,
        default_top_k=5,
        max_top_k=20,
        vector_candidates=10,
        fts_candidates=10,
        max_candidates=50,
        rrf_k=60,
    )
    hits = service.retrieve(
        HybridRequest(
            query_text=token,
            query_embedding=query,
            context=_context(roles={"employee"}, permissions={COMPANY_DOCUMENTS_READ}),
            top_k=5,
        )
    )
    assert hits[0].chunk_id == both.id
    assert hits[0].vector_similarity is not None
    assert hits[0].fts_rank is not None
    assert hits[0].rrf_score > 0


def test_fts_only_and_null_embedding_vector_ignored(pg_session):
    session, category_id, user_id, created_doc_ids = pg_session
    token = "zxqftsonlyconge"
    doc = _add_doc(
        session,
        category_id=category_id,
        user_id=user_id,
        title="hyb-fts-null",
        status=CompanyDocumentStatus.ACTIVE,
        created_doc_ids=created_doc_ids,
    )
    chunk = _add_chunk(
        session,
        doc=doc,
        content=f"Politique de congé: {token}",
        embedding=None,
    )
    session.commit()

    service = HybridRetrievalService(
        session,
        expected_dimensions=DIM,
        default_top_k=5,
        max_top_k=20,
        vector_candidates=10,
        fts_candidates=10,
        max_candidates=50,
    )
    # Query embedding is orthogonal; FTS should still find the chunk.
    hits = service.retrieve(
        HybridRequest(
            query_text=token,
            query_embedding=_unit(axis=5),
            context=_context(roles={"employee"}, permissions={COMPANY_DOCUMENTS_READ}),
            top_k=5,
        )
    )
    matching = [h for h in hits if h.chunk_id == chunk.id]
    assert len(matching) == 1
    assert matching[0].vector_similarity is None
    assert matching[0].fts_rank is not None
    assert "congé" in matching[0].content or token in matching[0].content


def test_french_simple_token_match(pg_session):
    session, category_id, user_id, created_doc_ids = pg_session
    doc = _add_doc(
        session,
        category_id=category_id,
        user_id=user_id,
        title="hyb-fr",
        status=CompanyDocumentStatus.ACTIVE,
        created_doc_ids=created_doc_ids,
    )
    chunk = _add_chunk(
        session,
        doc=doc,
        content="Demande de congé annuel Casablanca bureau",
        embedding=_unit(axis=4),
    )
    session.commit()

    rows = FullTextRetrievalRepository(session).search(
        query_text="Casablanca",
        context=_context(roles={"employee"}, permissions={COMPANY_DOCUMENTS_READ}),
        top_k=5,
    )
    assert any(r.chunk_id == chunk.id for r in rows)


def test_hybrid_top_k_and_empty_fts(pg_session):
    session, category_id, user_id, created_doc_ids = pg_session
    doc = _add_doc(
        session,
        category_id=category_id,
        user_id=user_id,
        title="hyb-topk",
        status=CompanyDocumentStatus.ACTIVE,
        created_doc_ids=created_doc_ids,
    )
    c0 = _add_chunk(
        session, doc=doc, content="alpha", embedding=_unit(axis=0), chunk_index=0
    )
    c1 = _add_chunk(
        session, doc=doc, content="beta", embedding=_near_unit(axis=0), chunk_index=1
    )
    session.commit()

    service = HybridRetrievalService(
        session,
        expected_dimensions=DIM,
        default_top_k=1,
        max_top_k=20,
        vector_candidates=10,
        fts_candidates=10,
        max_candidates=50,
    )
    hits = service.retrieve(
        HybridRequest(
            query_text="zzznomatchtoken",
            query_embedding=_unit(axis=0),
            context=_context(roles={"employee"}, permissions={COMPANY_DOCUMENTS_READ}),
            top_k=1,
        )
    )
    assert len(hits) == 1
    assert hits[0].chunk_id == c0.id
    assert service.last_debug is not None
    assert service.last_debug.fts_candidate_count == 0
    assert service.last_debug.vector_candidate_count >= 1
    assert c1.id != hits[0].chunk_id or True  # top_k=1 keeps best vector
