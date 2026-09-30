"""Best-effort chat-history hooks (must never break confirm/ask domain paths)."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.ai.history.service import ChatHistoryService

logger = logging.getLogger(__name__)


def resolve_pending_best_effort(
    db: Session,
    *,
    user_id: int,
    token: str,
    resolved: bool = True,
) -> None:
    """Update pending_resolved by token digest if a history row exists."""
    try:
        ChatHistoryService(db).resolve_pending(
            user_id=user_id, token=token, resolved=resolved
        )
        db.commit()
    except Exception:
        logger.exception("Chat history pending resolve failed (non-blocking)")
        try:
            db.rollback()
        except Exception:
            logger.exception("Chat history pending resolve rollback failed")
