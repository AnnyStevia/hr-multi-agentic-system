"""Orchestrate Meet link provisioning for scheduled interviews (provider-agnostic)."""

from __future__ import annotations

import logging

from app.modules.interviews.models import Interview, InterviewStatus
from app.modules.interviews.repository import InterviewRepository
from app.modules.notifications.models import NotificationType
from app.modules.notifications.service import NotificationService
from app.shared.exceptions import AppException
from app.shared.meetings import (
    MeetingAttendee,
    MeetingProvider,
    MeetingRequest,
    MeetingSkipped,
    get_meeting_provider,
)
from app.shared.meetings.exceptions import MeetingProviderError

logger = logging.getLogger(__name__)


class InterviewMeetingService:
    def __init__(
        self,
        repository: InterviewRepository,
        *,
        notifications: NotificationService | None = None,
        provider: MeetingProvider | None = None,
    ):
        self.repository = repository
        self.notifications = notifications
        self.provider = provider if provider is not None else get_meeting_provider()

    def ensure_meeting(self, interview_id: int) -> Interview:
        interview = self.repository.get_by_id(interview_id)
        if interview is None:
            raise AppException("Interview not found", status_code=404)

        interview = self._normalize(interview)
        if interview.status != InterviewStatus.SCHEDULED:
            raise AppException(
                "Meetings can only be created for scheduled interviews",
                status_code=400,
            )

        if interview.meeting_url:
            return interview

        if interview.meeting_external_id:
            repaired = self._try_repair_from_external(interview)
            if repaired is not None and repaired.meeting_url:
                return repaired

        selected = interview.selected_slot
        if selected is None:
            raise AppException("Scheduled interview is missing a selected slot", status_code=400)

        application = interview.application
        candidate = application.candidate
        title = f"Interview: {candidate.user.full_name} — {application.job.title}"
        attendees = self._attendees(interview)
        request = MeetingRequest(
            title=title,
            starts_at=selected.starts_at,
            ends_at=selected.ends_at,
            description=(
                f"Interview for {application.job.title}. "
                "Join via the link in the HR platform."
            ),
            attendees=tuple(attendees),
            idempotency_key=f"interview-{interview.id}",
        )

        try:
            result = self.provider.create_meeting(request)
        except MeetingSkipped:
            logger.info("Meeting creation skipped for interview_id=%s", interview.id)
            return interview
        except MeetingProviderError as exc:
            logger.warning(
                "Meeting creation failed for interview_id=%s: %s",
                interview.id,
                exc.message,
            )
            return interview

        interview.meeting_url = result.meeting_url
        interview.meeting_external_id = result.external_id
        saved = self.repository.save(interview)
        self._notify_meeting_ready(saved)
        return saved

    def _try_repair_from_external(self, interview: Interview) -> Interview | None:
        external_id = interview.meeting_external_id
        if not external_id:
            return None
        try:
            result = self.provider.get_meeting(external_id)
        except MeetingProviderError:
            return None
        if result is None or not result.meeting_url:
            return None
        interview.meeting_url = result.meeting_url
        if result.external_id:
            interview.meeting_external_id = result.external_id
        saved = self.repository.save(interview)
        self._notify_meeting_ready(saved)
        return saved

    def _notify_meeting_ready(self, interview: Interview) -> None:
        if self.notifications is None:
            return
        job_title = interview.application.job.title
        candidate_name = interview.application.candidate.user.full_name
        title = "Interview meeting link ready"
        message = (
            f"The Google Meet link for the interview ({candidate_name} — {job_title}) "
            "is ready. Open the interview in the platform to join."
        )
        recipients: set[int] = set()
        recipients.add(interview.application.candidate.user_id)
        for assignment in interview.panel_assignments or []:
            employee = assignment.employee
            if employee is not None and employee.user_id is not None:
                recipients.add(employee.user_id)

        for user_id in recipients:
            self.notifications.create_if_absent(
                recipient_user_id=user_id,
                type=NotificationType.INTERVIEW_MEETING_READY,
                title=title,
                message=message,
                related_entity_type="interview",
                related_entity_id=interview.id,
            )

    def _attendees(self, interview: Interview) -> list[MeetingAttendee]:
        attendees: list[MeetingAttendee] = []
        seen: set[str] = set()

        def add(email: str | None, name: str | None = None) -> None:
            if not email:
                return
            normalized = email.strip().lower()
            if not normalized or normalized in seen:
                return
            seen.add(normalized)
            attendees.append(MeetingAttendee(email=email.strip(), display_name=name))

        candidate_user = interview.application.candidate.user
        add(candidate_user.email, candidate_user.full_name)
        for assignment in interview.panel_assignments or []:
            employee = assignment.employee
            if employee is None:
                continue
            add(employee.email, employee.full_name)
        return attendees

    def _normalize(self, interview: Interview) -> Interview:
        # Reuse repository-loaded state; InterviewService has richer normalization
        # but meeting ensure only needs SCHEDULED + selected slot consistency.
        return interview
