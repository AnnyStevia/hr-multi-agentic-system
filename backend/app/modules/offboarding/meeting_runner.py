"""BackgroundTasks entrypoint for exit-interview Meet provisioning."""

from __future__ import annotations

import logging

from app.core.database import SessionLocal
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import NotificationService
from app.modules.offboarding.meeting_service import ExitInterviewMeetingService
from app.modules.offboarding.repository import OffboardingRepository
from app.shared.meetings import get_meeting_provider

logger = logging.getLogger(__name__)


def run_exit_interview_meeting_provision(exit_interview_id: int) -> None:
    """Fresh DB session; never raises to the request path."""
    db = SessionLocal()
    try:
        service = ExitInterviewMeetingService(
            OffboardingRepository(db),
            notifications=NotificationService(NotificationRepository(db)),
            provider=get_meeting_provider(),
        )
        service.ensure_meeting(exit_interview_id)
    except Exception:
        logger.exception(
            "Unhandled error provisioning meeting for exit_interview_id=%s",
            exit_interview_id,
        )
    finally:
        db.close()
