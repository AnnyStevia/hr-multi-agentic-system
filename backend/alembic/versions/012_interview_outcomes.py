"""Interview feedback, outcome, and application hired status.

Revision ID: 012_interview_outcomes
Revises: 011_repair_interview_state
Create Date: 2026-09-15

"""

from alembic import op
import sqlalchemy as sa

revision = "012_interview_outcomes"
down_revision = "011_repair_interview_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    interview_outcome = sa.Enum(
        "rejected",
        "another_interview",
        "hired",
        name="interview_outcome",
    )
    interview_outcome.create(bind, checkfirst=True)

    op.add_column("interviews", sa.Column("feedback", sa.Text(), nullable=True))
    op.add_column("interviews", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "interviews",
        sa.Column("outcome", interview_outcome, nullable=True),
    )

    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    ALTER TYPE application_status ADD VALUE 'hired';
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )


def downgrade() -> None:
    op.drop_column("interviews", "outcome")
    op.drop_column("interviews", "completed_at")
    op.drop_column("interviews", "feedback")

    bind = op.get_bind()
    sa.Enum(name="interview_outcome").drop(bind, checkfirst=True)
