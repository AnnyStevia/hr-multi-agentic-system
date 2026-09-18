"""Add onboarding lifecycle notification types.

Revision ID: 021_onboarding_notifications
Revises: 020_training_assignments
Create Date: 2026-09-18

"""

from alembic import op
import sqlalchemy as sa

revision = "021_onboarding_notifications"
down_revision = "020_training_assignments"
branch_labels = None
depends_on = None

_NEW_VALUES = (
    "onboarding_started",
    "onboarding_task_completed",
    "onboarding_training_assigned",
    "onboarding_training_completed",
    "onboarding_completed",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for value in _NEW_VALUES:
            op.execute(
                sa.text(
                    f"""
                    DO $$ BEGIN
                        ALTER TYPE notification_type ADD VALUE '{value}';
                    EXCEPTION WHEN duplicate_object THEN NULL;
                    END $$;
                    """
                )
            )


def downgrade() -> None:
    pass
