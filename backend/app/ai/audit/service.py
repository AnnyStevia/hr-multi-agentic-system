"""Persist minimal AI write audit rows."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.audit.models import AiToolActionAudit


def record_ai_tool_audit(
    db: Session,
    *,
    actor_user_id: int,
    tool_name: str,
    phase: str,
    target_type: str | None = None,
    target_id: int | None = None,
    arguments_digest: str | None = None,
    success: bool = True,
    error_code: str | None = None,
) -> None:
    row = AiToolActionAudit(
        actor_user_id=actor_user_id,
        tool_name=tool_name,
        phase=phase,
        target_type=target_type,
        target_id=target_id,
        arguments_digest=arguments_digest,
        success=success,
        error_code=error_code,
    )
    db.add(row)
    db.commit()
