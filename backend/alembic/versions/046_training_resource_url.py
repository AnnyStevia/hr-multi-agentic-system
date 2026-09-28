"""Add optional resource_url to trainings catalogue (Phase 10.1B).

Revision ID: 046_training_resource_url
Revises: 045_application_rejection_reason
Create Date: 2026-09-28

"""

from alembic import op
import sqlalchemy as sa

revision = "046_training_resource_url"
down_revision = "045_application_rejection_reason"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trainings",
        sa.Column("resource_url", sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("trainings", "resource_url")
