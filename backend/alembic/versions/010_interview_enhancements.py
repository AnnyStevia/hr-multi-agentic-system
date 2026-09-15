"""Interview slot availability, created_by user, interview_scheduled notification type.

Revision ID: 010_interview_enhancements
Revises: 009_interviews
Create Date: 2026-08-23

"""

from alembic import op
import sqlalchemy as sa

revision = "010_interview_enhancements"
down_revision = "009_interviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column(
        "interview_slots",
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column("interviews", sa.Column("created_by_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_interviews_created_by_user_id",
        "interviews",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                """
                DO $$ BEGIN
                    ALTER TYPE notification_type ADD VALUE 'interview_scheduled';
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )


def downgrade() -> None:
    op.drop_constraint("fk_interviews_created_by_user_id", "interviews", type_="foreignkey")
    op.drop_column("interviews", "created_by_user_id")
    op.drop_column("interview_slots", "is_available")
