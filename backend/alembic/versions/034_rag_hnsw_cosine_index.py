"""Add HNSW cosine index for rag_document_chunks.embedding (Phase 5.5).

Uses vector_cosine_ops to match cosine_distance (<=>) retrieval.
No IVFFlat; single vector index only.

Revision ID: 034_rag_hnsw_cosine_index
Revises: 033_rag_chunk_provenance
Create Date: 2026-09-24

"""

from alembic import op
import sqlalchemy as sa

revision = "034_rag_hnsw_cosine_index"
down_revision = "033_rag_chunk_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_rag_document_chunks_embedding_hnsw "
            "ON rag_document_chunks "
            "USING hnsw (embedding vector_cosine_ops)"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(sa.text("DROP INDEX IF EXISTS ix_rag_document_chunks_embedding_hnsw"))
