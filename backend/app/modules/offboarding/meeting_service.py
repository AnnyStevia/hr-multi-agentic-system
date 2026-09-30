"""Orchestrate Meet link provisioning for scheduled exit interviews."""

from __future__ import annotations

import logging

from app.modules.notifications.models import NotificationType
from app.modules.notifications.service import NotificationService
from app.modules.offboarding.models import ExitInterview, ExitInterviewStatus
from app.modules.offboarding.repository import OffboardingRepository
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


class ExitInterviewMeetingService:
    def __init__(
        self,
        repository: OffboardingRepository,
        *,
        notifications: NotificationService | None = None,
        provider: MeetingProvider | None = None,
    ):
        self.repository = repository
        self.notifications = notifications
        self.provider = provider if provider is not None else get_meeting_provider()

    def ensure_meeting(self, exit_interview_id: int) -> ExitInterview:
        interview = self.repository.get_exit_interview_by_id(exit_interview_id)
        if interview is None:
            raise AppException("Exit interview not found", status_code=404)

        if interview.status != ExitInterviewStatus.SCHEDULED:
            raise AppException(
                "Meetings can only be created for scheduled exit interviews",
                status_code=400,
            )

        if interview.meeting_url:
            return interview

        if interview.meeting_external_id:
            repaired = self._try_repair_from_external(interview)
            if repaired is not None and repaired.meeting_url:
                return repaired

        case = interview.offboarding_case
        employee = case.employee if case is not None else None
        employee_name = employee.full_name if employee is not None else "Employee"
        title = f"Exit interview: {employee_name}"
        request = MeetingRequest(
            title=title,
            starts_at=interview.scheduled_at,
            ends_at=interview.ends_at,
            description=(
                f"Exit interview for {employee_name}. "
                "Join via the link in the HR platform."
            ),
            attendees=tuple(self._attendees(interview)),
            idempotency_key=f"exit-interview-{interview.id}",
        )

        try:
            result = self.provider.create_meeting(request)
        except MeetingSkipped:
            logger.info(
                "Meeting creation skipped for exit_interview_id=%s", interview.id
            )
            return interview
        except MeetingProviderError as exc:
            logger.warning(
                "Meeting creation failed for exit_interview_id=%s: %s",
                interview.id,
                exc.message,
            )
            return interview

        interview.meeting_url = result.meeting_url
        interview.meeting_external_id = result.external_id
        saved = self.repository.save_exit_interview(interview)
        self._notify_meeting_ready(saved)
        return saved

    def _try_repair_from_external(self, interview: ExitInterview) -> ExitInterview | None:
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
        saved = self.repository.save_exit_interview(interview)
        self._notify_meeting_ready(saved)
        return saved

    def _notify_meeting_ready(self, interview: ExitInterview) -> None:
        if self.notifications is None:
            return
        case = interview.offboarding_case
        employee = case.employee if case is not None else None
        employee_name = employee.full_name if employee is not None else "Employee"
        title = "Exit interview meeting link ready"
        message = (
            f"The meeting link for the exit interview with {employee_name} is ready. "
            "Open the offboarding case in the platform to join."
        )
        recipients: set[int] = set()
        if employee is not None and employee.user_id is not None:
            recipients.add(employee.user_id)
        interviewer = interview.interviewer
        if interviewer is not None and interviewer.user_id is not None:
            recipients.add(interviewer.user_id)

        for user_id in recipients:
            self.notifications.create_if_absent(
                recipient_user_id=user_id,
                type=NotificationType.EXIT_INTERVIEW_MEETING_READY,
                title=title,
                message=message,
                related_entity_type="exit_interview",
                related_entity_id=interview.id,
            )

    def _attendees(self, interview: ExitInterview) -> list[MeetingAttendee]:
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

        case = interview.offboarding_case
        if case is not None and case.employee is not None:
            add(case.employee.email, case.employee.full_name)
        if interview.interviewer is not None:
            add(interview.interviewer.email, interview.interviewer.full_name)
        return attendees
