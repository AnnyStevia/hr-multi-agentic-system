"""Align application_status with recruitment v1 workflow.

Maps leftover interview/hired values without deleting applications.

Revision ID: 005_application_status
Revises: 004_applications
Create Date: 2026-08-19

"""

from alembic import op
import sqlalchemy as sa

revision = "005_application_status"
down_revision = "004_applications"
branch_labels = None
depends_on = None

OLD_VALUES = ("submitted", "shortlisted", "rejected", "interview", "hired")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(sa.text("ALTER TABLE applications ALTER COLUMN status DROP DEFAULT"))
    op.execute(
        sa.text(
            "ALTER TABLE applications ALTER COLUMN status TYPE VARCHAR "
            "USING status::text"
        )
    )
    op.execute(
        sa.text("UPDATE applications SET status = 'screening' WHERE status = 'interview'")
    )
    op.execute(
        sa.text("UPDATE applications SET status = 'shortlisted' WHERE status = 'hired'")
    )
    op.execute(sa.text("DROP TYPE application_status"))
    op.execute(
        sa.text(
            "CREATE TYPE application_status AS ENUM "
            "('submitted', 'screening', 'shortlisted', 'rejected')"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE applications ALTER COLUMN status TYPE application_status "
            "USING status::application_status"
        )
    )
    op.execute(
        sa.text("ALTER TABLE applications ALTER COLUMN status SET DEFAULT 'submitted'")
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(sa.text("ALTER TABLE applications ALTER COLUMN status DROP DEFAULT"))
    op.execute(
        sa.text(
            "ALTER TABLE applications ALTER COLUMN status TYPE VARCHAR "
            "USING status::text"
        )
    )
    op.execute(
        sa.text("UPDATE applications SET status = 'interview' WHERE status = 'screening'")
    )
    op.execute(sa.text("DROP TYPE application_status"))
    quoted = ", ".join(f"'{value}'" for value in OLD_VALUES)
    op.execute(sa.text(f"CREATE TYPE application_status AS ENUM ({quoted})"))
    op.execute(
        sa.text(
            "ALTER TABLE applications ALTER COLUMN status TYPE application_status "
            "USING status::application_status"
        )
    )
    op.execute(
        sa.text("ALTER TABLE applications ALTER COLUMN status SET DEFAULT 'submitted'")
    )
