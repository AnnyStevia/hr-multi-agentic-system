"""Make Meet your manager optional until HR assigns a manager.

Revision ID: 027_meet_manager_optional
Revises: 026_onboarding_task_verify
Create Date: 2026-09-22

"""

from alembic import op
import sqlalchemy as sa

revision = "027_meet_manager_optional"
down_revision = "026_onboarding_task_verify"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE onboarding_task_templates
            SET is_required = false
            WHERE title = 'Meet your manager'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE onboarding_tasks
            SET is_required = false
            WHERE title = 'Meet your manager'
              AND task_type = 'manual'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE onboarding_task_templates
            SET is_required = true
            WHERE title = 'Meet your manager'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE onboarding_tasks
            SET is_required = true
            WHERE title = 'Meet your manager'
              AND task_type = 'manual'
            """
        )
    )
