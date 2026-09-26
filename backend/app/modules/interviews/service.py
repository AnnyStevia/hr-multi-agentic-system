from datetime import UTC, datetime

from app.modules.employees.models import Employee, EmploymentStatus
from app.modules.employees.service import EmployeeService
from app.modules.identity.models import User
from app.modules.interviews.models import (
    Interview,
    InterviewInterviewer,
    InterviewOutcome,
    InterviewSlot,
    InterviewStatus,
)
from app.modules.interviews.repository import InterviewRepository
from app.modules.interviews.schemas import (
    InterviewCreateRequest,
    InterviewDetailResponse,
    InterviewerSummary,
    InterviewSlotResponse,
    InterviewSummary,
)
from app.modules.notifications.models import NotificationType
from app.modules.notifications.service import NotificationService
from app.modules.recruitment.application_service import ApplicationService
from app.modules.recruitment.models import Application, ApplicationStatus
from app.modules.recruitment.repository import ApplicationRepository
from app.shared.exceptions import AppException

MIN_SLOT_COUNT = 2
MAX_SLOT_COUNT = 5

STATUS_LABELS = {
    InterviewStatus.PROPOSED: "Waiting for candidate's response to the invitation",
    InterviewStatus.SCHEDULED: "Scheduled",
    InterviewStatus.COMPLETED: "Completed",
    InterviewStatus.CANCELLED: "Cancelled",
}

OUTCOME_LABELS = {
    InterviewOutcome.REJECTED: "Rejected",
    InterviewOutcome.ANOTHER_INTERVIEW: "Another interview",
    InterviewOutcome.HIRED: "Hired",
}


class InterviewService:
    def __init__(
        self,
        repository: InterviewRepository,
        applications: ApplicationRepository,
        notification_service: NotificationService | None = None,
        employee_service: EmployeeService | None = None,
        application_service: ApplicationService | None = None,
    ):
        self.repository = repository
        self.applications = applications
        self.notifications = notification_service
        self.employees = employee_service
        self.application_service = application_service

    def create_invitation(
        self,
        application_id: int,
        payload: InterviewCreateRequest,
        *,
        created_by: User,
    ) -> Interview:
        application = self._require_shortlisted_application(application_id)
        if self.repository.has_active_invitation_for_application(application_id):
            raise AppException(
                "An active interview invitation already exists for this application",
                status_code=409,
            )

        slots = _validate_slots(payload.slots)
        panel = self._resolve_interviewers(payload.interviewer_employee_ids)

        interview = Interview(
            application_id=application.id,
            interviewer_employee_id=panel[0].id,
            created_by_user_id=created_by.id,
            message=payload.message.strip(),
            status=InterviewStatus.PROPOSED,
            slots=[
                InterviewSlot(starts_at=starts_at, ends_at=ends_at, is_selected=False, is_available=True)
                for starts_at, ends_at in slots
            ],
            panel_assignments=[
                InterviewInterviewer(employee_id=employee.id) for employee in panel
            ],
        )
        created = self.repository.add(interview)

        if self.notifications is not None:
            self.notifications.create_notification(
                recipient_user_id=application.candidate.user_id,
                type=NotificationType.INTERVIEW_INVITATION,
                title="Interview invitation",
                message=(
                    f"You have been invited to an interview for {application.job.title}. "
                    "Please choose one of the proposed time slots."
                ),
                related_entity_type="interview",
                related_entity_id=created.id,
            )

        return created

    def list_for_application(self, application_id: int) -> list[Interview]:
        application = self.applications.get_by_id(application_id)
        if application is None:
            raise AppException("Application not found", status_code=404)
        interviews = self.repository.list_for_application(application_id)
        return [self._normalize_interview_state(interview) for interview in interviews]

    def has_pending_proposed(self, application_id: int) -> bool:
        return self.repository.has_proposed_for_application(application_id)

    def get_for_hr(self, interview_id: int) -> Interview:
        interview = self.repository.get_by_id(interview_id)
        if interview is None:
            raise AppException("Interview not found", status_code=404)
        return self._normalize_interview_state(interview)

    def get_own(self, user: User, interview_id: int) -> Interview:
        interview = self.repository.get_by_id(interview_id)
        if interview is None:
            raise AppException("Interview not found", status_code=404)
        if interview.application.candidate.user_id != user.id:
            raise AppException("Interview not found", status_code=404)
        return self._normalize_interview_state(interview)

    def confirm_slot(self, user: User, interview_id: int, slot_id: int) -> Interview:
        interview = self.repository.get_by_id(interview_id)
        if interview is None:
            raise AppException("Interview not found", status_code=404)
        if interview.application.candidate.user_id != user.id:
            raise AppException("Interview not found", status_code=404)

        interview = self._normalize_interview_state(interview)
        if interview.status == InterviewStatus.SCHEDULED:
            if interview.selected_slot_id == slot_id:
                return interview
            raise AppException("This interview invitation is no longer available", status_code=400)
        if interview.status != InterviewStatus.PROPOSED:
            raise AppException("This interview invitation is no longer available", status_code=400)

        slot = next((item for item in interview.slots if item.id == slot_id), None)
        if slot is None:
            raise AppException("Selected slot not found", status_code=404)
        if not slot.is_available or slot.is_selected:
            raise AppException("Selected slot is no longer available", status_code=400)

        now = datetime.now(UTC)
        if _ensure_utc(slot.starts_at) <= now:
            raise AppException("Selected slot is no longer in the future", status_code=400)

        interview.selected_slot_id = slot.id
        interview.status = InterviewStatus.SCHEDULED
        slot.is_selected = True
        for other in interview.slots:
            if other.id != slot.id:
                other.is_available = False

        saved = self.repository.save(interview)

        hr_recipient_id = _resolve_hr_notification_recipient(saved)
        if self.notifications is not None and hr_recipient_id is not None:
            selected = saved.selected_slot
            slot_text = ""
            if selected is not None:
                slot_text = f" for {_format_slot_range(selected.starts_at, selected.ends_at)}"
            self.notifications.create_notification(
                recipient_user_id=hr_recipient_id,
                type=NotificationType.INTERVIEW_SCHEDULED,
                title="Interview confirmed by candidate",
                message=(
                    f"{saved.application.candidate.user.full_name} confirmed the interview "
                    f"for {saved.application.job.title}{slot_text}."
                ),
                related_entity_type="interview",
                related_entity_id=saved.id,
            )

        return saved

    def complete_interview(self, interview_id: int, feedback: str) -> Interview:
        interview = self.get_for_hr(interview_id)
        if interview.status != InterviewStatus.SCHEDULED:
            raise AppException(
                "Only scheduled interviews can be marked as completed",
                status_code=400,
            )
        cleaned = feedback.strip()
        if not cleaned:
            raise AppException("Interview feedback is required", status_code=400)

        interview.status = InterviewStatus.COMPLETED
        interview.feedback = cleaned
        interview.completed_at = datetime.now(UTC)
        return self.repository.save(interview)

    def record_outcome(self, interview_id: int, outcome: InterviewOutcome) -> Interview:
        interview = self.get_for_hr(interview_id)
        if interview.status != InterviewStatus.COMPLETED:
            raise AppException(
                "Interview must be completed before recording an outcome",
                status_code=400,
            )
        if interview.outcome is not None:
            raise AppException("An outcome has already been recorded for this interview", status_code=409)

        application = interview.application
        if application.status != ApplicationStatus.SHORTLISTED:
            raise AppException(
                "Application must be shortlisted to record an interview outcome",
                status_code=400,
            )

        if self.application_service is None:
            raise AppException("Application service is not configured", status_code=500)

        hired_employee: Employee | None = None
        try:
            interview.outcome = outcome

            if outcome == InterviewOutcome.REJECTED:
                self.application_service.apply_interview_driven_status(
                    application, ApplicationStatus.REJECTED
                )
            elif outcome == InterviewOutcome.HIRED:
                if self.employees is None:
                    raise AppException("Employee service is not configured", status_code=500)
                hired_employee = self.employees.create_from_hired_candidate(
                    application, commit=False
                )
                self.application_service.apply_interview_driven_status(
                    application, ApplicationStatus.HIRED
                )
            elif outcome == InterviewOutcome.ANOTHER_INTERVIEW:
                self.repository.save_without_commit(interview)
            else:
                raise AppException("Invalid interview outcome", status_code=400)

            self.repository.save_without_commit(interview)
            self.repository.commit()
        except AppException:
            self.repository.rollback()
            raise
        except Exception:
            self.repository.rollback()
            raise

        saved = self.repository.get_by_id(interview_id)
        if saved is None:
            raise AppException("Failed to load updated interview", status_code=500)

        if outcome == InterviewOutcome.REJECTED:
            job_title = saved.application.job.title
            self._notify_application_status(
                saved.application,
                title="Application update",
                message=(
                    f"Thank you for your interest in {job_title}. After careful consideration, "
                    "we won’t move forward with your application this time. We truly appreciate "
                    "the time you invested and wish you every success ahead."
                ),
            )
        elif outcome == InterviewOutcome.HIRED:
            job_title = saved.application.job.title
            self._notify_application_status(
                saved.application,
                title="Welcome aboard!",
                message=(
                    f"Congratulations — we’re delighted to offer you the {job_title} role. "
                    "An employee record has been created and HR will follow up with next steps soon."
                ),
            )
            if hired_employee is not None and self.employees is not None and self.employees.onboarding is not None:
                self.employees.onboarding.notify_onboarding_started(hired_employee)
        elif outcome == InterviewOutcome.ANOTHER_INTERVIEW:
            job_title = saved.application.job.title
            self._notify_application_status(
                saved.application,
                title="Next step: another interview",
                message=(
                    f"Thank you for the interview. We’d like to continue with another conversation "
                    f"for {job_title}. Please watch for a new invitation from our team."
                ),
            )

        return saved

    def _notify_application_status(self, application: Application, *, title: str, message: str) -> None:
        if self.notifications is None:
            return
        self.notifications.create_notification(
            recipient_user_id=application.candidate.user_id,
            type=NotificationType.APPLICATION_STATUS_CHANGED,
            title=title,
            message=message,
            related_entity_type="application",
            related_entity_id=application.id,
        )

    def resolve_hired_employee_id(self, interview: Interview) -> int | None:
        if interview.outcome != InterviewOutcome.HIRED or self.employees is None:
            return None
        employee = self.employees.get_by_user_id(interview.application.candidate.user_id)
        return employee.id if employee else None

    def _normalize_interview_state(self, interview: Interview) -> Interview:
        changed = False
        selected = interview.selected_slot
        if selected is None:
            selected = next((slot for slot in interview.slots if slot.is_selected), None)
            if selected is not None:
                interview.selected_slot_id = selected.id
                changed = True

        if selected is not None and interview.status == InterviewStatus.PROPOSED:
            interview.status = InterviewStatus.SCHEDULED
            selected.is_selected = True
            changed = True

        if selected is not None:
            for slot in interview.slots:
                if slot.id != selected.id and slot.is_available:
                    slot.is_available = False
                    changed = True

        if changed:
            return self.repository.save(interview)
        return interview

    def _require_shortlisted_application(self, application_id: int) -> Application:
        application = self.applications.get_by_id(application_id)
        if application is None:
            raise AppException("Application not found", status_code=404)
        if application.status != ApplicationStatus.SHORTLISTED:
            raise AppException(
                "Interview invitations can only be created for shortlisted applications",
                status_code=400,
            )
        return application

    def _resolve_interviewers(self, employee_ids: list[int]) -> list[Employee]:
        if not employee_ids:
            raise AppException("At least one interviewer is required", status_code=400)

        if len(employee_ids) != len(set(employee_ids)):
            raise AppException("Duplicate interviewer is not allowed", status_code=400)

        employees = self.repository.get_employees_by_ids(employee_ids)
        by_id = {employee.id: employee for employee in employees}
        missing = [employee_id for employee_id in employee_ids if employee_id not in by_id]
        if missing:
            raise AppException("Interviewer employee not found", status_code=404)

        user_ids = [employee.user_id for employee in employees if employee.user_id is not None]
        users_by_id = self.repository.get_users_by_ids(user_ids)

        ordered: list[Employee] = []
        for employee_id in employee_ids:
            employee = by_id[employee_id]
            if employee.employment_status != EmploymentStatus.ACTIVE:
                raise AppException(
                    "Only active employees can be selected as interviewers",
                    status_code=400,
                )
            if employee.user_id is not None:
                linked = users_by_id.get(employee.user_id)
                if linked is None or not linked.is_active:
                    raise AppException(
                        "Interviewer linked user account is inactive",
                        status_code=400,
                    )
            ordered.append(employee)
        return ordered


def _validate_slots(slots: list) -> list[tuple[datetime, datetime]]:
    if len(slots) < MIN_SLOT_COUNT or len(slots) > MAX_SLOT_COUNT:
        raise AppException(
            f"Between {MIN_SLOT_COUNT} and {MAX_SLOT_COUNT} proposed slots are required",
            status_code=400,
        )

    now = datetime.now(UTC)
    normalized: list[tuple[datetime, datetime]] = []
    seen: set[tuple[datetime, datetime]] = set()

    for slot in slots:
        starts_at = _ensure_utc(slot.starts_at)
        ends_at = _ensure_utc(slot.ends_at)
        if ends_at <= starts_at:
            raise AppException("Each slot end time must be after its start time", status_code=400)
        if starts_at <= now:
            raise AppException("All proposed slots must be in the future", status_code=400)
        key = (starts_at, ends_at)
        if key in seen:
            raise AppException("Duplicate proposed slots are not allowed", status_code=400)
        seen.add(key)
        normalized.append(key)

    return normalized


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _format_slot_range(starts_at: datetime, ends_at: datetime) -> str:
    start = _ensure_utc(starts_at)
    end = _ensure_utc(ends_at)
    return f"{start.strftime('%A %d %b %Y, %H:%M')}–{end.strftime('%H:%M')} UTC"


def _slot_response(slot: InterviewSlot) -> InterviewSlotResponse:
    return InterviewSlotResponse(
        id=slot.id,
        starts_at=slot.starts_at,
        ends_at=slot.ends_at,
        is_selected=slot.is_selected,
        is_available=slot.is_available,
    )


def _status_label(status: InterviewStatus) -> str:
    return STATUS_LABELS.get(status, status.value)


def _resolve_hr_notification_recipient(interview: Interview) -> int | None:
    if interview.created_by_user_id is not None:
        return interview.created_by_user_id
    interviewer = interview.interviewer
    if interviewer is not None and interviewer.user_id is not None:
        return interviewer.user_id
    return None


def _outcome_label(outcome: InterviewOutcome | None) -> str | None:
    if outcome is None:
        return None
    return OUTCOME_LABELS.get(outcome, outcome.value)


def _panel_employees(interview: Interview) -> list[Employee]:
    assignments = getattr(interview, "panel_assignments", None) or []
    employees = [row.employee for row in assignments if row.employee is not None]
    if employees:
        return employees
    if interview.interviewer is not None:
        return [interview.interviewer]
    return []


def _interviewer_summaries(interview: Interview) -> list[InterviewerSummary]:
    return [
        InterviewerSummary(
            employee_id=employee.id,
            full_name=employee.full_name,
            position=employee.position,
        )
        for employee in _panel_employees(interview)
    ]


def build_interview_summary(
    interview: Interview,
    *,
    hired_employee_id: int | None = None,
) -> InterviewSummary:
    application = interview.application
    candidate = application.candidate
    selected = interview.selected_slot
    panel = _panel_employees(interview)
    primary = panel[0] if panel else interview.interviewer
    return InterviewSummary(
        id=interview.id,
        application_id=interview.application_id,
        status=interview.status.value,
        status_label=_status_label(interview.status),
        message=interview.message,
        created_at=interview.created_at,
        job_title=application.job.title,
        candidate_name=candidate.user.full_name,
        interviewer_name=primary.full_name if primary else None,
        interviewers=_interviewer_summaries(interview),
        selected_slot=_slot_response(selected) if selected else None,
        feedback=interview.feedback,
        completed_at=interview.completed_at,
        outcome=interview.outcome.value if interview.outcome else None,
        outcome_label=_outcome_label(interview.outcome),
        hired_employee_id=hired_employee_id,
        meeting_url=interview.meeting_url,
    )


def build_interview_detail(
    interview: Interview,
    *,
    hired_employee_id: int | None = None,
) -> InterviewDetailResponse:
    application = interview.application
    candidate = application.candidate
    selected = interview.selected_slot
    panel = _panel_employees(interview)
    primary = panel[0] if panel else interview.interviewer
    if interview.status == InterviewStatus.PROPOSED:
        visible_slots = [slot for slot in interview.slots if slot.is_available]
    elif selected is not None:
        visible_slots = [selected]
    else:
        visible_slots = list(interview.slots)

    return InterviewDetailResponse(
        id=interview.id,
        application_id=interview.application_id,
        status=interview.status.value,
        message=interview.message,
        created_at=interview.created_at,
        updated_at=interview.updated_at,
        job_title=application.job.title,
        candidate_name=candidate.user.full_name,
        interviewer_name=primary.full_name if primary else None,
        interviewers=_interviewer_summaries(interview),
        slots=[_slot_response(slot) for slot in sorted(visible_slots, key=lambda s: s.starts_at)],
        selected_slot=_slot_response(selected) if selected else None,
        feedback=interview.feedback,
        completed_at=interview.completed_at,
        outcome=interview.outcome.value if interview.outcome else None,
        outcome_label=_outcome_label(interview.outcome),
        hired_employee_id=hired_employee_id,
        meeting_url=interview.meeting_url,
    )
