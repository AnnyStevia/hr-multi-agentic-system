"""Create documents table and employee_document_type enum.

Revision ID: 019_employee_documents
Revises: 018_onboarding_task_assigned
Create Date: 2026-09-17

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "019_employee_documents"
down_revision = "018_onboarding_task_assigned"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    document_type = sa.Enum(
        "id_document",
        "contract",
        "diploma",
        "certificate",
        "other",
        name="employee_document_type",
    )
    if bind.dialect.name == "postgresql":
        document_type = postgresql.ENUM(
            "id_document",
            "contract",
            "diploma",
            "certificate",
            "other",
            name="employee_document_type",
            create_type=False,
        )
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE employee_document_type AS ENUM (
                        'id_document', 'contract', 'diploma', 'certificate', 'other'
                    );
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("document_type", document_type, nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_employee_id", "documents", ["employee_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_employee_id", table_name="documents")
    op.drop_table("documents")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS employee_document_type"))
