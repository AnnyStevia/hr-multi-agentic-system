"""Create offboarding_clearance_items verification table.

Revision ID: 052_offboarding_clearance
Revises: 051_offboarding_requests
Create Date: 2026-09-29

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "052_offboarding_clearance"
down_revision = "051_offboarding_requests"
branch_labels = None
depends_on = None

CATEGORY_VALUES = (
    "equipment",
    "access",
)
STATUS_VALUES = (
    "pending",
    "cleared",
    "not_applicable",
)


def upgrade() -> None:
    bind = op.get_bind()
    category_enum = sa.Enum(*CATEGORY_VALUES, name="offboarding_clearance_category")
    status_enum = sa.Enum(*STATUS_VALUES, name="offboarding_clearance_status")
    if bind.dialect.name == "postgresql":
        category_enum = postgresql.ENUM(
            *CATEGORY_VALUES,
            name="offboarding_clearance_category",
            create_type=False,
        )
        status_enum = postgresql.ENUM(
            *STATUS_VALUES,
            name="offboarding_clearance_status",
            create_type=False,
        )
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE offboarding_clearance_category AS ENUM (
                        'equipment',
                        'access'
                    );
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE offboarding_clearance_status AS ENUM (
                        'pending',
                        'cleared',
                        'not_applicable'
                    );
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )

    op.create_table(
        "offboarding_clearance_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("offboarding_case_id", sa.Integer(), nullable=False),
        sa.Column("category", category_enum, nullable=False),
        sa.Column("item", sa.String(length=200), nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by_user_id", sa.Integer(), nullable=True),
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
            ["offboarding_case_id"], ["offboarding_cases.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["completed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_offboarding_clearance_items_offboarding_case_id",
        "offboarding_clearance_items",
        ["offboarding_case_id"],
    )
    op.create_index(
        "ix_offboarding_clearance_items_status",
        "offboarding_clearance_items",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_offboarding_clearance_items_status",
        table_name="offboarding_clearance_items",
    )
    op.drop_index(
        "ix_offboarding_clearance_items_offboarding_case_id",
        table_name="offboarding_clearance_items",
    )
    op.drop_table("offboarding_clearance_items")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS offboarding_clearance_status"))
        op.execute(sa.text("DROP TYPE IF EXISTS offboarding_clearance_category"))
