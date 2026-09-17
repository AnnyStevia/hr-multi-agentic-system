"""Add onboarding_task_assigned notification type.

Revision ID: 018_onboarding_task_assigned
Revises: 017_employee_role_backfill
Create Date: 2026-09-17

"""

from alembic import op
import sqlalchemy as sa

revision = "018_onboarding_task_assigned"
down_revision = "017_employee_role_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    ALTER TYPE notification_type ADD VALUE 'onboarding_task_assigned';
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )


def downgrade() -> None:
    pass
