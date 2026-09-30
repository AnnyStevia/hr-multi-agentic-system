"""Create ai_conversations and ai_conversation_messages.

Revision ID: 054_ai_chat_history
Revises: 053_offboarding_exit_interview
Create Date: 2026-09-30

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "054_ai_chat_history"
down_revision = "053_offboarding_exit_interview"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=True),
        sa.Column("candidate_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_conversations_user_id",
        "ai_conversations",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_conversations_user_id_updated_at",
        "ai_conversations",
        ["user_id", "updated_at"],
        unique=False,
    )

    json_type = sa.JSON().with_variant(
        postgresql.JSONB(astext_type=sa.Text()),
        "postgresql",
    )
    op.create_table(
        "ai_conversation_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("route_reason", sa.String(length=255), nullable=True),
        sa.Column("node_path", json_type, nullable=True),
        sa.Column("tool_names_called", json_type, nullable=True),
        sa.Column("citations_json", json_type, nullable=True),
        sa.Column("pending_tool_name", sa.String(length=120), nullable=True),
        sa.Column("pending_summary", sa.Text(), nullable=True),
        sa.Column("pending_expires_at", sa.Integer(), nullable=True),
        sa.Column("pending_token_digest", sa.String(length=64), nullable=True),
        sa.Column("pending_resolved", sa.Boolean(), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("usage_json", json_type, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["ai_conversations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id",
            "sequence",
            name="uq_ai_conversation_messages_conversation_sequence",
        ),
    )
    op.create_index(
        "ix_ai_conversation_messages_conversation_id",
        "ai_conversation_messages",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_conversation_messages_conversation_id_created_at",
        "ai_conversation_messages",
        ["conversation_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ai_conversation_messages_conversation_id_created_at",
        table_name="ai_conversation_messages",
    )
    op.drop_index(
        "ix_ai_conversation_messages_conversation_id",
        table_name="ai_conversation_messages",
    )
    op.drop_table("ai_conversation_messages")
    op.drop_index(
        "ix_ai_conversations_user_id_updated_at",
        table_name="ai_conversations",
    )
    op.drop_index("ix_ai_conversations_user_id", table_name="ai_conversations")
    op.drop_table("ai_conversations")
