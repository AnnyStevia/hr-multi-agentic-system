"""AI chat conversation history models (persistent unified assistant)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base

_JsonType = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class AiConversation(Base):
    __tablename__ = "ai_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    candidate_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    messages: Mapped[list["AiConversationMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AiConversationMessage.sequence",
    )


class AiConversationMessage(Base):
    __tablename__ = "ai_conversation_messages"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "sequence",
            name="uq_ai_conversation_messages_conversation_sequence",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    route_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    node_path: Mapped[Any | None] = mapped_column(_JsonType, nullable=True)
    tool_names_called: Mapped[Any | None] = mapped_column(_JsonType, nullable=True)
    citations_json: Mapped[Any | None] = mapped_column(_JsonType, nullable=True)
    pending_tool_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pending_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    pending_expires_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pending_token_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pending_resolved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    usage_json: Mapped[Any | None] = mapped_column(_JsonType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )

    conversation: Mapped[AiConversation] = relationship(back_populates="messages")
