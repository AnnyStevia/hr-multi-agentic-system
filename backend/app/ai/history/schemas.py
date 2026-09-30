"""Pydantic schemas for AI chat history APIs (safe fields only)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MessageRole = Literal["user", "assistant"]


class ConversationSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    title: str | None = None
    created_at: datetime
    updated_at: datetime


class HistoryPendingState(BaseModel):
    """Safe pending display state — never includes token or digest."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str | None = None
    summary: str | None = None
    expires_at: int | None = None
    resolved: bool | None = None


class ConversationMessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    role: MessageRole
    content: str
    sequence: int
    agent_id: str | None = None
    status: str | None = None
    tool_names_called: list[str] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    pending: HistoryPendingState | None = None
    model: str | None = None
    created_at: datetime


class ConversationDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    title: str | None = None
    created_at: datetime
    updated_at: datetime
    messages: list[ConversationMessageResponse] = Field(default_factory=list)


def message_to_response(row) -> ConversationMessageResponse:
    pending = None
    if row.pending_tool_name or row.pending_summary or row.pending_expires_at is not None:
        pending = HistoryPendingState(
            tool_name=row.pending_tool_name,
            summary=row.pending_summary,
            expires_at=row.pending_expires_at,
            resolved=row.pending_resolved,
        )
    return ConversationMessageResponse(
        id=row.id,
        role=row.role,
        content=row.content,
        sequence=row.sequence,
        agent_id=row.agent_id,
        status=row.status,
        tool_names_called=list(row.tool_names_called or []),
        citations=list(row.citations_json or []),
        pending=pending,
        model=row.model,
        created_at=row.created_at,
    )
