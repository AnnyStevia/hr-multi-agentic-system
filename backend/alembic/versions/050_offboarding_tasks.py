"""Create offboarding_tasks checklist table.

Revision ID: 050_offboarding_tasks
Revises: 049_offboarding_cases
Create Date: 2026-09-29

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "050_offboarding_tasks"
down_revision = "049_offboarding_cases"
branch_labels = None
depends_on = None

CATEGORY_VALUES = (
    "documents",
    "handover",
    "equipment",
    "access",
    "administration",
    "other",
)
STATUS_VALUES = (
    "pending",
    "in_progress",
    "completed",
    "skipped",
)


def upgrade() -> None:
    bind = op.get_bind()
    category_enum = sa.Enum(*CATEGORY_VALUES, name="offboarding_task_category")
    status_enum = sa.Enum(*STATUS_VALUES, name="offboarding_task_status")
    if bind.dialect.name == "postgresql":
        category_enum = postgresql.ENUM(
            *CATEGORY_VALUES,
            name="offboarding_task_category",
            create_type=False,
        )
        status_enum = postgresql.ENUM(
            *STATUS_VALUES,
            name="offboarding_task_status",
            create_type=False,
        )
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE offboarding_task_category AS ENUM (
                        'documents',
                        'handover',
                        'equipment',
                        'access',
                        'administration',
                        'other'
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
                    CREATE TYPE offboarding_task_status AS ENUM (
                        'pending',
                        'in_progress',
                        'completed',
                        'skipped'
                    );
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )

    op.create_table(
        "offboarding_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("offboarding_case_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", category_enum, nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("assigned_to_employee_id", sa.Integer(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["assigned_to_employee_id"], ["employees.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["completed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_offboarding_tasks_offboarding_case_id",
        "offboarding_tasks",
        ["offboarding_case_id"],
    )
    op.create_index(
        "ix_offboarding_tasks_assigned_to_employee_id",
        "offboarding_tasks",
        ["assigned_to_employee_id"],
    )
    op.create_index("ix_offboarding_tasks_status", "offboarding_tasks", ["status"])
    op.create_index("ix_offboarding_tasks_due_date", "offboarding_tasks", ["due_date"])


def downgrade() -> None:
    op.drop_index("ix_offboarding_tasks_due_date", table_name="offboarding_tasks")
    op.drop_index("ix_offboarding_tasks_status", table_name="offboarding_tasks")
    op.drop_index(
        "ix_offboarding_tasks_assigned_to_employee_id",
        table_name="offboarding_tasks",
    )
    op.drop_index(
        "ix_offboarding_tasks_offboarding_case_id",
        table_name="offboarding_tasks",
    )
    op.drop_table("offboarding_tasks")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS offboarding_task_status"))
        op.execute(sa.text("DROP TYPE IF EXISTS offboarding_task_category"))
