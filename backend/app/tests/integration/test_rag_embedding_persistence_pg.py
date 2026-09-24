"""Postgres integration: persist a fake 768-d embedding (no live Gemini)."""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import sessionmaker

from app.ai.rag.chunking.repository import KnowledgeChunkRepository
from app.ai.rag.embeddings.schemas import EmbeddingResult
from app.ai.rag.embeddings.service import EmbeddingService
from app.ai.rag.models import KnowledgeChunk
from app.core.config import settings


def _fake_vector(dim: int = 768) -> list[float]:
    return [((i % 97) / 97.0) - 0.5 for i in range(dim)]


class _IsolatedChunkRepository(KnowledgeChunkRepository):
    """List only the test chunk so we never touch other document rows."""

    def __init__(self, db, chunk: KnowledgeChunk) -> None:
        super().__init__(db)
        self._chunk = chunk

    def list_by_company_document_id(self, company_document_id: int) -> list[KnowledgeChunk]:
        if self._chunk.company_document_id != company_document_id:
            return []
        return [self._chunk]


class _FixedVectorProvider:
    def __init__(self, vector: list[float]) -> None:
        self._vector = vector

    def embed_text(self, text: str, *, task_type: str | None = None) -> EmbeddingResult:
        return self.embed_texts([text], task_type=task_type)[0]

    def embed_texts(self, texts, *, task_type: str | None = None):
        return [
            EmbeddingResult(
                vector=list(self._vector),
                model="gemini-embedding-2",
                dimensions=len(self._vector),
            )
            for _ in texts
        ]


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
            doc = conn.execute(
                text("SELECT id FROM company_documents ORDER BY id LIMIT 1")
            ).fetchone()
            if doc is None:
                pytest.skip("No company_documents row for integration test")
            doc_id = doc[0]
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL unreachable: {exc}")
    except ProgrammingError as exc:
        pytest.skip(f"PostgreSQL query failed: {exc}")

    Session = sessionmaker(bind=engine)
    session = Session()
    created_ids: list[int] = []
    try:
        yield session, doc_id, created_ids
    finally:
        session.rollback()
        for chunk_id in created_ids:
            session.query(KnowledgeChunk).filter(KnowledgeChunk.id == chunk_id).delete(
                synchronize_session=False
            )
        session.commit()
        session.close()


def test_postgres_persists_fake_768_embedding(pg_session):
    session, doc_id, created_ids = pg_session
    base_repo = KnowledgeChunkRepository(session)
    chunk = KnowledgeChunk(
        company_document_id=doc_id,
        content="Fake embedding persistence test chunk.",
        page_start=1,
        page_end=1,
        chunk_index=999_001,
        content_hash="0" * 64,
        chunk_metadata={"company_document_id": doc_id, "chunk_index": 999_001},
        embedding=None,
        embedding_model=None,
        embedding_dimensions=None,
    )
    # Remove any leftover from a previous interrupted run.
    session.query(KnowledgeChunk).filter(
        KnowledgeChunk.company_document_id == doc_id,
        KnowledgeChunk.chunk_index == 999_001,
    ).delete(synchronize_session=False)
    base_repo.add_many([chunk])
    session.commit()
    created_ids.append(chunk.id)

    vector = _fake_vector(768)
    repo = _IsolatedChunkRepository(session, chunk)
    service = EmbeddingService(
        session,
        _FixedVectorProvider(vector),
        repository=repo,
        embedding_model="gemini-embedding-2",
        embedding_dimensions=768,
    )
    result = service.embed_company_document_chunks(doc_id)

    assert result.embedded_count == 1
    assert result.skipped_count == 0

    session.refresh(chunk)
    assert chunk.embedding is not None
    assert len(list(chunk.embedding)) == 768
    assert chunk.embedding_model == "gemini-embedding-2"
    assert chunk.embedding_dimensions == 768
