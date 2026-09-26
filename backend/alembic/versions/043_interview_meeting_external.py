"""Interview meeting external id + meeting-ready notification type (Phase 6.4D).

Revision ID: 043_interview_meeting_external
Revises: 042_interview_workflow_primary
Create Date: 2026-09-26

"""

from alembic import op
import sqlalchemy as sa

revision = "043_interview_meeting_external"
down_revision = "042_interview_workflow_primary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        sa.text(
            """
            DO $$ BEGIN
                ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'interview_meeting_ready';
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )
    op.add_column(
        "interviews",
        sa.Column("meeting_external_id", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.drop_column("interviews", "meeting_external_id")
