"""Persist application rejection_reason (Phase 6.4G).

Revision ID: 045_application_rejection_reason
Revises: 044_ai_tool_action_audits
Create Date: 2026-09-27

"""

from alembic import op
import sqlalchemy as sa

revision = "045_application_rejection_reason"
down_revision = "044_ai_tool_action_audits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("applications", "rejection_reason")
