"""AI tool action audit table (Phase 6.4F).

Revision ID: 044_ai_tool_action_audits
Revises: 043_interview_meeting_external
Create Date: 2026-09-26

"""

from alembic import op
import sqlalchemy as sa

revision = "044_ai_tool_action_audits"
down_revision = "043_interview_meeting_external"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_tool_action_audits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(length=120), nullable=False),
        sa.Column("phase", sa.String(length=32), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("arguments_digest", sa.String(length=64), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_tool_action_audits_actor_user_id",
        "ai_tool_action_audits",
        ["actor_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_tool_action_audits_actor_user_id", table_name="ai_tool_action_audits")
    op.drop_table("ai_tool_action_audits")
