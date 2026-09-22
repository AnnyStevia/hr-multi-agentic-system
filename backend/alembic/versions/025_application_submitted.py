"""Add application_submitted notification type.

Revision ID: 025_application_submitted
Revises: 024_onboarding_task_templates
Create Date: 2026-09-21

"""

from alembic import op
import sqlalchemy as sa

revision = "025_application_submitted"
down_revision = "024_onboarding_task_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    ALTER TYPE notification_type ADD VALUE 'application_submitted';
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )


def downgrade() -> None:
    pass
