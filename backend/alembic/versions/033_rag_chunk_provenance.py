"""Add provenance columns to rag_document_chunks (Phase 5.3).

Revision ID: 033_rag_chunk_provenance
Revises: 032_enable_pgvector
Create Date: 2026-09-24

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "033_rag_chunk_provenance"
down_revision = "032_enable_pgvector"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.add_column(
        "rag_document_chunks",
        sa.Column("page_start", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "rag_document_chunks",
        sa.Column("page_end", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "rag_document_chunks",
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "rag_document_chunks",
        sa.Column(
            "content_hash",
            sa.String(length=64),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "rag_document_chunks",
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    # Drop server defaults after backfill so new rows must supply values explicitly.
    op.alter_column("rag_document_chunks", "page_start", server_default=None)
    op.alter_column("rag_document_chunks", "page_end", server_default=None)
    op.alter_column("rag_document_chunks", "chunk_index", server_default=None)
    op.alter_column("rag_document_chunks", "content_hash", server_default=None)
    op.alter_column("rag_document_chunks", "metadata", server_default=None)

    op.create_index(
        "ix_rag_document_chunks_content_hash",
        "rag_document_chunks",
        ["content_hash"],
    )
    op.create_unique_constraint(
        "uq_rag_document_chunks_document_chunk_index",
        "rag_document_chunks",
        ["company_document_id", "chunk_index"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.drop_constraint(
        "uq_rag_document_chunks_document_chunk_index",
        "rag_document_chunks",
        type_="unique",
    )
    op.drop_index(
        "ix_rag_document_chunks_content_hash",
        table_name="rag_document_chunks",
    )
    op.drop_column("rag_document_chunks", "metadata")
    op.drop_column("rag_document_chunks", "content_hash")
    op.drop_column("rag_document_chunks", "chunk_index")
    op.drop_column("rag_document_chunks", "page_end")
    op.drop_column("rag_document_chunks", "page_start")
