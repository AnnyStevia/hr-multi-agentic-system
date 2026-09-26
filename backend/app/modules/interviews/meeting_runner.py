"""BackgroundTasks entrypoint for interview Meet provisioning."""

from __future__ import annotations

import logging

from app.core.database import SessionLocal
from app.modules.interviews.meeting_service import InterviewMeetingService
from app.modules.interviews.repository import InterviewRepository
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import NotificationService
from app.shared.meetings import get_meeting_provider

logger = logging.getLogger(__name__)


def run_interview_meeting_provision(interview_id: int) -> None:
    """Fresh DB session; never raises to the request path."""
    db = SessionLocal()
    try:
        service = InterviewMeetingService(
            InterviewRepository(db),
            notifications=NotificationService(NotificationRepository(db)),
            provider=get_meeting_provider(),
        )
        service.ensure_meeting(interview_id)
    except Exception:
        logger.exception(
            "Unhandled error provisioning meeting for interview_id=%s",
            interview_id,
        )
    finally:
        db.close()
