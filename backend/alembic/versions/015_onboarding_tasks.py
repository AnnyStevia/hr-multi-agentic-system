"""Create onboarding_tasks table and onboarding_task_status enum.

Revision ID: 015_onboarding_tasks
Revises: 014_onboarding
Create Date: 2026-09-16

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "015_onboarding_tasks"
down_revision = "014_onboarding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    task_status = sa.Enum("pending", "completed", name="onboarding_task_status")
    if bind.dialect.name == "postgresql":
        task_status = postgresql.ENUM(
            "pending",
            "completed",
            name="onboarding_task_status",
            create_type=False,
        )
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE onboarding_task_status AS ENUM ('pending', 'completed');
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )

    op.create_table(
        "onboarding_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("onboarding_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", task_status, nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["onboarding_id"], ["onboardings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_onboarding_tasks_onboarding_id", "onboarding_tasks", ["onboarding_id"])


def downgrade() -> None:
    op.drop_index("ix_onboarding_tasks_onboarding_id", table_name="onboarding_tasks")
    op.drop_table("onboarding_tasks")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS onboarding_task_status"))
