"""Company document library and private documents.

Revision ID: 031_company_private_documents
Revises: 030_leave_dual_approval
Create Date: 2026-09-23

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "031_company_private_documents"
down_revision = "030_leave_dual_approval"
branch_labels = None
depends_on = None

COMPANY_DOC_STATUSES = ("active", "archived")

INITIAL_CATEGORIES = [
    ("hr_policies", "HR Policies", 1),
    ("company_policies", "Company Policies", 2),
    ("procedures", "Procedures", 3),
    ("employee_handbook", "Employee Handbook", 4),
    ("it_security", "IT & Security", 5),
    ("forms_templates", "Forms & Templates", 6),
    ("other", "Other", 7),
]


def upgrade() -> None:
    bind = op.get_bind()

    status_enum = sa.Enum(*COMPANY_DOC_STATUSES, name="company_document_status")
    if bind.dialect.name == "postgresql":
        status_enum = postgresql.ENUM(
            *COMPANY_DOC_STATUSES,
            name="company_document_status",
            create_type=False,
        )
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE company_document_status AS ENUM (
                        'active', 'archived'
                    );
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )

    op.create_table(
        "company_document_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    categories = sa.table(
        "company_document_categories",
        sa.column("slug", sa.String),
        sa.column("label", sa.String),
        sa.column("sort_order", sa.Integer),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        categories,
        [
            {"slug": slug, "label": label, "sort_order": order, "is_active": True}
            for slug, label, order in INITIAL_CATEGORIES
        ],
    )

    op.create_table(
        "company_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default="active"),
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
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["company_document_categories.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_company_documents_category_id", "company_documents", ["category_id"])
    op.create_index("ix_company_documents_status", "company_documents", ["status"])
    op.create_index(
        "ix_company_documents_uploaded_by_user_id",
        "company_documents",
        ["uploaded_by_user_id"],
    )

    op.create_table(
        "private_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_employee_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["owner_employee_id"],
            ["employees.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_private_documents_owner_employee_id",
        "private_documents",
        ["owner_employee_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_private_documents_owner_employee_id", table_name="private_documents")
    op.drop_table("private_documents")
    op.drop_index("ix_company_documents_uploaded_by_user_id", table_name="company_documents")
    op.drop_index("ix_company_documents_status", table_name="company_documents")
    op.drop_index("ix_company_documents_category_id", table_name="company_documents")
    op.drop_table("company_documents")
    op.drop_table("company_document_categories")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS company_document_status"))
