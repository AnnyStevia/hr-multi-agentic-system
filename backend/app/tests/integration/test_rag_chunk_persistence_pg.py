"""Optional Postgres integration: replace chunks without duplicates (no Gemini)."""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import sessionmaker

from app.ai.rag.chunking import DocumentChunker, KnowledgeChunkService
from app.ai.rag.chunking.chunker import pages_to_ingestion_result
from app.ai.rag.ingestion.schemas import IngestedPage
from app.ai.rag.models import KnowledgeChunk
from app.core.config import settings
from app.modules.documents.models import CompanyDocument


@pytest.fixture
def pg_session():
    url = settings.database_url
    if not url.startswith("postgresql"):
        pytest.skip("DATABASE_URL is not PostgreSQL")

    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'rag_document_chunks'"
                )
            ).fetchone()
            if row is None:
                pytest.skip("rag_document_chunks missing — run alembic upgrade head")
            # Provenance columns from Phase 5.3
            col = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'rag_document_chunks' "
                    "AND column_name = 'content_hash'"
                )
            ).fetchone()
            if col is None:
                pytest.skip("content_hash missing — run alembic upgrade head")
            doc_row = conn.execute(
                text("SELECT id, version FROM company_documents ORDER BY id LIMIT 1")
            ).fetchone()
            if doc_row is None:
                pytest.skip("No company_documents row available for integration test")
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL unreachable: {exc}")
    except ProgrammingError as exc:
        pytest.skip(f"PostgreSQL query failed: {exc}")

    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session, doc_row[0], doc_row[1]
    finally:
        session.rollback()
        session.close()


def test_replace_chunks_idempotent_on_postgres(pg_session):
    session, doc_id, version = pg_session
    document = session.get(CompanyDocument, doc_id)
    assert document is not None

    ingestion = pages_to_ingestion_result(
        [IngestedPage(page_number=1, text="Integration chunk content for phase 5.3.")],
        company_document_id=doc_id,
    )
    service = KnowledgeChunkService(
        session,
        chunker=DocumentChunker(chunk_size=800, overlap=100),
    )

    first = service.replace_chunks_from_ingestion(document, ingestion)
    first_hash = first[0].content_hash
    assert len(first) == 1
    assert first[0].embedding is None

    second = service.replace_chunks_from_ingestion(document, ingestion)

    assert len(second) == 1
    assert second[0].content_hash == first_hash
    assert second[0].embedding is None

    count = (
        session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.company_document_id == doc_id)
        .count()
    )
    assert count == 1
