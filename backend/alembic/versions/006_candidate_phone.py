"""Add optional phone number to candidate profiles.

Revision ID: 006_candidate_phone
Revises: 005_application_status
Create Date: 2026-08-19

"""

from alembic import op
import sqlalchemy as sa

revision = "006_candidate_phone"
down_revision = "005_application_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("phone", sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column("candidates", "phone")
