"""CRUD APIs for persistent AI assistant conversations (user-owned)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.history.schemas import (
    ConversationDetailResponse,
    ConversationSummaryResponse,
    message_to_response,
)
from app.ai.history.service import ChatHistoryService, ConversationNotFoundError
from app.core.database import get_db
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User

router = APIRouter(prefix="/ai/conversations", tags=["AI Conversations"])


@router.get("", response_model=list[ConversationSummaryResponse])
def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ConversationSummaryResponse]:
    rows = ChatHistoryService(db).list_conversations(current_user.id)
    return [
        ConversationSummaryResponse(
            id=r.id,
            title=r.title,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationDetailResponse:
    try:
        row = ChatHistoryService(db).get_conversation(conversation_id, current_user.id)
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        ) from exc
    messages = sorted(row.messages or [], key=lambda m: m.sequence)
    return ConversationDetailResponse(
        id=row.id,
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
        messages=[message_to_response(m) for m in messages],
    )


@router.delete("/{conversation_id}", status_code=204, response_model=None)
def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        ChatHistoryService(db).delete_conversation(conversation_id, current_user.id)
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        ) from exc
