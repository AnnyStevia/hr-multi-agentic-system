"""Repository for AI conversation history (user_id ownership)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.ai.history.models import AiConversation, AiConversationMessage


class ChatHistoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_conversation(
        self,
        *,
        user_id: int,
        employee_id: int | None,
        candidate_id: int | None,
        title: str | None,
    ) -> AiConversation:
        now = datetime.now(UTC)
        row = AiConversation(
            user_id=user_id,
            employee_id=employee_id,
            candidate_id=candidate_id,
            title=title,
            created_at=now,
            updated_at=now,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def get_for_user(
        self, conversation_id: int, user_id: int, *, with_messages: bool = False
    ) -> AiConversation | None:
        stmt = select(AiConversation).where(
            AiConversation.id == conversation_id,
            AiConversation.user_id == user_id,
        )
        if with_messages:
            stmt = stmt.options(selectinload(AiConversation.messages))
        return self.db.execute(stmt).scalar_one_or_none()

    def lock_for_user(
        self, conversation_id: int, user_id: int
    ) -> AiConversation | None:
        stmt = (
            select(AiConversation)
            .where(
                AiConversation.id == conversation_id,
                AiConversation.user_id == user_id,
            )
            .with_for_update()
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_user(self, user_id: int, *, limit: int = 50) -> list[AiConversation]:
        stmt = (
            select(AiConversation)
            .where(AiConversation.user_id == user_id)
            .order_by(AiConversation.updated_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def next_sequence(self, conversation_id: int) -> int:
        current = self.db.execute(
            select(func.max(AiConversationMessage.sequence)).where(
                AiConversationMessage.conversation_id == conversation_id
            )
        ).scalar_one()
        return int(current or 0) + 1

    def add_message(self, message: AiConversationMessage) -> AiConversationMessage:
        self.db.add(message)
        self.db.flush()
        return message

    def touch_conversation(self, conversation: AiConversation) -> None:
        conversation.updated_at = datetime.now(UTC)
        self.db.flush()

    def delete_for_user(self, conversation_id: int, user_id: int) -> bool:
        row = self.get_for_user(conversation_id, user_id)
        if row is None:
            return False
        self.db.delete(row)
        self.db.flush()
        return True

    def find_pending_by_digest(
        self, *, user_id: int, token_digest: str
    ) -> AiConversationMessage | None:
        stmt = (
            select(AiConversationMessage)
            .join(AiConversation)
            .where(
                AiConversation.user_id == user_id,
                AiConversationMessage.pending_token_digest == token_digest,
            )
            .order_by(AiConversationMessage.id.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()
