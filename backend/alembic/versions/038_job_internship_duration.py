"""Add internship_duration_months to jobs (Phase 5.12).

Revision ID: 038_job_internship_duration
Revises: 037_leave_cancellation
Create Date: 2026-09-25

"""

from alembic import op
import sqlalchemy as sa

revision = "038_job_internship_duration"
down_revision = "037_leave_cancellation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.add_column(
        "jobs",
        sa.Column("internship_duration_months", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.drop_column("jobs", "internship_duration_months")
