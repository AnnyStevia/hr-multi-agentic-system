"""Add training_resource_published notification type.

Revision ID: 047_training_resource_published
Revises: 046_training_resource_url
Create Date: 2026-09-28

"""

from alembic import op
import sqlalchemy as sa

revision = "047_training_resource_published"
down_revision = "046_training_resource_url"
branch_labels = None
depends_on = None

_NEW_VALUE = "training_resource_published"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        sa.text(
            f"ALTER TYPE notification_type ADD VALUE IF NOT EXISTS '{_NEW_VALUE}'"
        )
    )


def downgrade() -> None:
    # PostgreSQL cannot easily remove enum values; leave as no-op.
    return
