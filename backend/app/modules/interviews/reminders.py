"""Send in-app reminders ~30 minutes before scheduled interviews."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session, joinedload, selectinload

from app.modules.interviews.models import Interview, InterviewStatus
from app.modules.interviews.service import _resolve_hr_notification_recipient
from app.modules.notifications.models import NotificationType
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import NotificationService
from app.modules.recruitment.models import Application
from app.modules.identity.models import Candidate


REMINDER_WINDOW = timedelta(minutes=30)


def send_upcoming_interview_reminders(db: Session) -> int:
    """Create idempotent reminder notifications for interviews starting within 30 minutes."""
    now = datetime.now(UTC)
    window_end = now + REMINDER_WINDOW

    interviews = (
        db.query(Interview)
        .options(
            selectinload(Interview.slots),
            joinedload(Interview.selected_slot),
            joinedload(Interview.interviewer),
            joinedload(Interview.application)
            .joinedload(Application.candidate)
            .joinedload(Candidate.user),
            joinedload(Interview.application).joinedload(Application.job),
        )
        .filter(Interview.status == InterviewStatus.SCHEDULED)
        .all()
    )

    notifications = NotificationService(NotificationRepository(db))
    created = 0

    for interview in interviews:
        selected = interview.selected_slot
        if selected is None:
            continue
        starts_at = selected.starts_at
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=UTC)
        else:
            starts_at = starts_at.astimezone(UTC)
        if not (now < starts_at <= window_end):
            continue

        job_title = interview.application.job.title
        title = "Interview starting soon"
        message = (
            f"Friendly reminder: your interview for {job_title} starts in about 30 minutes. "
            "Please be ready a few minutes early."
        )
        hr_message = (
            f"Reminder: the interview with {interview.application.candidate.user.full_name} "
            f"for {job_title} starts in about 30 minutes."
        )

        recipients: list[tuple[int, str]] = [
            (interview.application.candidate.user_id, message),
        ]
        hr_recipient = _resolve_hr_notification_recipient(interview)
        if hr_recipient is not None and hr_recipient != interview.application.candidate.user_id:
            recipients.append((hr_recipient, hr_message))

        for recipient_user_id, body in recipients:
            result = notifications.create_if_absent(
                recipient_user_id=recipient_user_id,
                type=NotificationType.INTERVIEW_REMINDER,
                title=title,
                message=body,
                related_entity_type="interview",
                related_entity_id=interview.id,
            )
            if result is not None:
                created += 1

    return created
