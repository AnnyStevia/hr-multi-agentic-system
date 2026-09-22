"""Add rejection_reason to leave_requests.

Revision ID: 029_leave_rejection_reason
Revises: 028_leave_management
Create Date: 2026-09-22

"""

from alembic import op
import sqlalchemy as sa

revision = "029_leave_rejection_reason"
down_revision = "028_leave_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "leave_requests",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("leave_requests", "rejection_reason")
