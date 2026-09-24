"""Unit tests for KnowledgeChunk SQLAlchemy foundation (no Gemini / no DB writes)."""

from pgvector.sqlalchemy import Vector
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects.postgresql import JSONB

from app.ai.rag.config import rag_settings
from app.ai.rag.models import RAG_EMBEDDING_DIMENSIONS, KnowledgeChunk


def test_knowledge_chunk_embedding_is_vector_768():
    assert RAG_EMBEDDING_DIMENSIONS == 768
    assert rag_settings.rag_embedding_dimensions == 768

    embedding_col = KnowledgeChunk.__table__.c.embedding
    assert isinstance(embedding_col.type, Vector)
    assert embedding_col.type.dim == 768
    assert embedding_col.nullable is True


def test_knowledge_chunk_fk_to_company_documents():
    mapper = sa_inspect(KnowledgeChunk)
    fk_targets = {
        fk.column.table.name
        for column in mapper.columns
        for fk in column.foreign_keys
    }
    assert "company_documents" in fk_targets

    company_doc_col = KnowledgeChunk.__table__.c.company_document_id
    assert company_doc_col.nullable is False
    fks = list(company_doc_col.foreign_keys)
    assert len(fks) == 1
    assert fks[0].ondelete == "CASCADE"


def test_knowledge_chunk_has_content_and_embedding_metadata_columns():
    columns = KnowledgeChunk.__table__.c
    assert "content" in columns
    assert "embedding_model" in columns
    assert "embedding_dimensions" in columns
    assert "created_at" in columns
    assert "updated_at" in columns
    assert columns.embedding_model.nullable is True
    assert columns.embedding_dimensions.nullable is True


def test_knowledge_chunk_has_provenance_columns():
    columns = KnowledgeChunk.__table__.c
    assert columns.page_start.nullable is False
    assert columns.page_end.nullable is False
    assert columns.chunk_index.nullable is False
    assert columns.content_hash.nullable is False
    assert columns.content_hash.type.length == 64
    assert "metadata" in columns
    assert isinstance(columns.metadata.type, JSONB)
    assert columns.metadata.nullable is False


def test_knowledge_chunk_unique_document_chunk_index():
    names = {c.name for c in KnowledgeChunk.__table__.constraints}
    assert "uq_rag_document_chunks_document_chunk_index" in names


def test_knowledge_chunk_content_hash_indexed():
    index_names = {idx.name for idx in KnowledgeChunk.__table__.indexes}
    assert "ix_rag_document_chunks_content_hash" in index_names or any(
        list(idx.columns.keys()) == ["content_hash"]
        for idx in KnowledgeChunk.__table__.indexes
    )
