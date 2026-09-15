"""Notifications table.

Revision ID: 008_notifications
Revises: 007_departments_employees
Create Date: 2026-08-23

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "008_notifications"
down_revision = "007_departments_employees"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    notification_type = sa.Enum(
        "application_status_changed",
        "interview_invitation",
        name="notification_type",
    )
    if bind.dialect.name == "postgresql":
        notification_type = postgresql.ENUM(
            "application_status_changed",
            "interview_invitation",
            name="notification_type",
            create_type=False,
        )
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE notification_type AS ENUM (
                        'application_status_changed',
                        'interview_invitation'
                    );
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recipient_user_id", sa.Integer(), nullable=False),
        sa.Column("type", notification_type, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("related_entity_type", sa.String(length=50), nullable=True),
        sa.Column("related_entity_id", sa.Integer(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"],
            ["users.id"],
            name="fk_notifications_recipient_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notifications_recipient_user_id",
        "notifications",
        ["recipient_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_recipient_created_at",
        "notifications",
        ["recipient_user_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_notifications_recipient_is_read",
        "notifications",
        ["recipient_user_id", "is_read"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_recipient_is_read", table_name="notifications")
    op.drop_index("ix_notifications_recipient_created_at", table_name="notifications")
    op.drop_index("ix_notifications_recipient_user_id", table_name="notifications")
    op.drop_table("notifications")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS notification_type"))
