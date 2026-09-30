"""Chat history service — user-owned conversations for the unified assistant."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.ai.core.context.models import AIExecutionContext
from app.ai.history.models import AiConversation, AiConversationMessage
from app.ai.history.repository import ChatHistoryRepository
from app.ai.history.sanitize import (
    derive_title,
    sanitize_citations_for_history,
    token_digest,
)
from app.ai.orchestration.graph.run import OrchestratorResult

logger = logging.getLogger(__name__)


class ConversationNotFoundError(Exception):
    """Owned conversation missing (treat as HTTP 404)."""


class ChatHistoryService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ChatHistoryRepository(db)

    def list_conversations(self, user_id: int) -> list[AiConversation]:
        return self.repo.list_for_user(user_id)

    def get_conversation(
        self, conversation_id: int, user_id: int
    ) -> AiConversation:
        row = self.repo.get_for_user(conversation_id, user_id, with_messages=True)
        if row is None:
            raise ConversationNotFoundError()
        return row

    def delete_conversation(self, conversation_id: int, user_id: int) -> None:
        if not self.repo.delete_for_user(conversation_id, user_id):
            raise ConversationNotFoundError()
        self.db.commit()

    def begin_turn(
        self,
        *,
        context: AIExecutionContext,
        message: str,
        conversation_id: int | None,
    ) -> tuple[AiConversation, AiConversationMessage]:
        """Create or load conversation and append the user message (locked sequence)."""
        if conversation_id is None:
            conversation = self.repo.create_conversation(
                user_id=context.user_id,
                employee_id=context.employee_id,
                candidate_id=context.candidate_id,
                title=derive_title(message),
            )
            locked = self.repo.lock_for_user(conversation.id, context.user_id)
            assert locked is not None
            conversation = locked
        else:
            conversation = self.repo.lock_for_user(conversation_id, context.user_id)
            if conversation is None:
                raise ConversationNotFoundError()

        seq = self.repo.next_sequence(conversation.id)
        user_msg = AiConversationMessage(
            conversation_id=conversation.id,
            role="user",
            content=message,
            sequence=seq,
        )
        self.repo.add_message(user_msg)
        self.repo.touch_conversation(conversation)
        self.db.flush()
        return conversation, user_msg

    def append_assistant_from_result(
        self,
        *,
        conversation: AiConversation,
        result: OrchestratorResult,
        pending_token: str | None = None,
    ) -> AiConversationMessage:
        locked = self.repo.lock_for_user(conversation.id, conversation.user_id)
        if locked is None:
            raise ConversationNotFoundError()
        seq = self.repo.next_sequence(locked.id)

        pending_tool = None
        pending_summary = None
        pending_expires = None
        pending_digest = None
        pending_resolved = None
        if result.pending_confirmation:
            pending_tool = result.pending_confirmation.get("tool_name")
            pending_summary = result.pending_confirmation.get("summary")
            pending_expires = result.pending_confirmation.get("expires_at")
            raw_token = pending_token or result.pending_confirmation.get("token")
            if isinstance(raw_token, str) and raw_token:
                pending_digest = token_digest(raw_token)
            pending_resolved = False

        assistant = AiConversationMessage(
            conversation_id=locked.id,
            role="assistant",
            content=result.answer or "",
            sequence=seq,
            agent_id=result.agent_id,
            status=result.status,
            route_reason=result.route_reason,
            node_path=list(result.node_path) if result.node_path else None,
            tool_names_called=list(result.tool_names_called)
            if result.tool_names_called
            else None,
            citations_json=sanitize_citations_for_history(result.citations),
            pending_tool_name=pending_tool,
            pending_summary=pending_summary,
            pending_expires_at=pending_expires,
            pending_token_digest=pending_digest,
            pending_resolved=pending_resolved,
            model=result.model,
            usage_json=result.usage,
        )
        self.repo.add_message(assistant)
        self.repo.touch_conversation(locked)
        self.db.flush()
        return assistant

    def append_error_assistant(
        self,
        *,
        conversation: AiConversation,
        content: str,
    ) -> AiConversationMessage:
        locked = self.repo.lock_for_user(conversation.id, conversation.user_id)
        if locked is None:
            raise ConversationNotFoundError()
        seq = self.repo.next_sequence(locked.id)
        assistant = AiConversationMessage(
            conversation_id=locked.id,
            role="assistant",
            content=content,
            sequence=seq,
            agent_id=None,
            status="error",
        )
        self.repo.add_message(assistant)
        self.repo.touch_conversation(locked)
        self.db.flush()
        return assistant

    def resolve_pending(
        self, *, user_id: int, token: str, resolved: bool
    ) -> bool:
        """Best-effort update of pending_resolved. Returns True if a row was updated."""
        digest = token_digest(token)
        row = self.repo.find_pending_by_digest(user_id=user_id, token_digest=digest)
        if row is None:
            return False
        row.pending_resolved = resolved
        self.db.flush()
        return True

    def commit_quietly(self) -> None:
        try:
            self.db.commit()
        except Exception:
            logger.exception("Chat history commit failed")
            try:
                self.db.rollback()
            except Exception:
                logger.exception("Chat history rollback failed")

    def flush_quietly(self) -> bool:
        try:
            self.db.flush()
            return True
        except Exception:
            logger.exception("Chat history flush failed")
            try:
                self.db.rollback()
            except Exception:
                logger.exception("Chat history rollback after flush failure")
            return False
