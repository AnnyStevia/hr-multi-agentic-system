"""Add interview_reminder notification type.

Revision ID: 013_interview_reminder
Revises: 012_interview_outcomes
Create Date: 2026-09-15

"""

from alembic import op
import sqlalchemy as sa

revision = "013_interview_reminder"
down_revision = "012_interview_outcomes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    ALTER TYPE notification_type ADD VALUE 'interview_reminder';
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )


def downgrade() -> None:
    pass
