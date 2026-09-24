"""Add FTS tsvector (simple) + GIN index for hybrid search (Phase 5.6).

Uses PostgreSQL text-search configuration 'simple' (language-neutral) so
mixed English/French HR content is not harmed by English-only stemming.
Preserves the existing HNSW cosine vector index.

Revision ID: 035_rag_fts_gin
Revises: 034_rag_hnsw_cosine_index
Create Date: 2026-09-24

"""

from alembic import op
import sqlalchemy as sa

revision = "035_rag_fts_gin"
down_revision = "034_rag_hnsw_cosine_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        sa.text(
            "ALTER TABLE rag_document_chunks "
            "ADD COLUMN IF NOT EXISTS content_tsv tsvector "
            "GENERATED ALWAYS AS "
            "(to_tsvector('simple', coalesce(content, ''))) STORED"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_rag_document_chunks_content_tsv_gin "
            "ON rag_document_chunks USING gin (content_tsv)"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(sa.text("DROP INDEX IF EXISTS ix_rag_document_chunks_content_tsv_gin"))
    op.execute(sa.text("ALTER TABLE rag_document_chunks DROP COLUMN IF EXISTS content_tsv"))
