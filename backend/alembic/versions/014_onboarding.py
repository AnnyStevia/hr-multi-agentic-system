"""Create onboardings table and onboarding_status enum.

Revision ID: 014_onboarding
Revises: 013_interview_reminder
Create Date: 2026-09-15

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "014_onboarding"
down_revision = "013_interview_reminder"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    onboarding_status = sa.Enum("in_progress", "completed", name="onboarding_status")
    if bind.dialect.name == "postgresql":
        onboarding_status = postgresql.ENUM(
            "in_progress",
            "completed",
            name="onboarding_status",
            create_type=False,
        )
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE onboarding_status AS ENUM ('in_progress', 'completed');
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )

    op.create_table(
        "onboardings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("status", onboarding_status, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", name="uq_onboarding_employee_id"),
    )


def downgrade() -> None:
    op.drop_table("onboardings")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS onboarding_status"))
