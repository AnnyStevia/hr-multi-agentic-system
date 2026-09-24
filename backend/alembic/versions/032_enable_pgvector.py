"""Enable pgvector and add minimal rag_document_chunks table.

Revision ID: 032_enable_pgvector
Revises: 031_company_private_documents
Create Date: 2026-09-24

"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "032_enable_pgvector"
down_revision = "031_company_private_documents"
branch_labels = None
depends_on = None

RAG_EMBEDDING_DIMENSIONS = 768


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    op.create_table(
        "rag_document_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_document_id",
            sa.Integer(),
            sa.ForeignKey("company_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(RAG_EMBEDDING_DIMENSIONS), nullable=True),
        sa.Column("embedding_model", sa.String(length=120), nullable=True),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_rag_document_chunks_company_document_id",
        "rag_document_chunks",
        ["company_document_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.drop_index(
        "ix_rag_document_chunks_company_document_id",
        table_name="rag_document_chunks",
    )
    op.drop_table("rag_document_chunks")
    op.execute(sa.text("DROP EXTENSION IF EXISTS vector"))
