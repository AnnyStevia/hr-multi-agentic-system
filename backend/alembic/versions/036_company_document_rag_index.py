"""Add company document RAG indexing lifecycle columns (Phase 5.11).

Revision ID: 036_company_document_rag_index
Revises: 035_rag_fts_gin
Create Date: 2026-09-25

"""

from alembic import op
import sqlalchemy as sa

revision = "036_company_document_rag_index"
down_revision = "035_rag_fts_gin"
branch_labels = None
depends_on = None

_RAG_INDEX_STATUS = sa.Enum(
    "pending",
    "processing",
    "ready",
    "failed",
    name="company_document_rag_index_status",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    _RAG_INDEX_STATUS.create(bind, checkfirst=True)
    op.add_column(
        "company_documents",
        sa.Column(
            "rag_index_status",
            _RAG_INDEX_STATUS,
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "company_documents",
        sa.Column("rag_indexed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "company_documents",
        sa.Column("rag_indexing_error", sa.String(length=500), nullable=True),
    )
    op.create_index(
        "ix_company_documents_rag_index_status",
        "company_documents",
        ["rag_index_status"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.drop_index(
        "ix_company_documents_rag_index_status",
        table_name="company_documents",
    )
    op.drop_column("company_documents", "rag_indexing_error")
    op.drop_column("company_documents", "rag_indexed_at")
    op.drop_column("company_documents", "rag_index_status")
    _RAG_INDEX_STATUS.drop(bind, checkfirst=True)
