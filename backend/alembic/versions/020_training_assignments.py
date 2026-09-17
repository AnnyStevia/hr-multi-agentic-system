"""Create trainings and onboarding_trainings tables.

Revision ID: 020_training_assignments
Revises: 019_employee_documents
Create Date: 2026-09-17

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "020_training_assignments"
down_revision = "019_employee_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    status_enum = sa.Enum("pending", "completed", name="onboarding_training_status")
    if bind.dialect.name == "postgresql":
        status_enum = postgresql.ENUM(
            "pending",
            "completed",
            name="onboarding_training_status",
            create_type=False,
        )
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE onboarding_training_status AS ENUM ('pending', 'completed');
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )

    op.create_table(
        "trainings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
    )

    op.create_table(
        "onboarding_trainings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("onboarding_id", sa.Integer(), nullable=False),
        sa.Column("training_id", sa.Integer(), nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(["training_id"], ["trainings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("onboarding_id", "training_id", name="uq_onboarding_training"),
    )
    op.create_index("ix_onboarding_trainings_onboarding_id", "onboarding_trainings", ["onboarding_id"])
    op.create_index("ix_onboarding_trainings_training_id", "onboarding_trainings", ["training_id"])


def downgrade() -> None:
    op.drop_index("ix_onboarding_trainings_training_id", table_name="onboarding_trainings")
    op.drop_index("ix_onboarding_trainings_onboarding_id", table_name="onboarding_trainings")
    op.drop_table("onboarding_trainings")
    op.drop_table("trainings")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS onboarding_training_status"))
