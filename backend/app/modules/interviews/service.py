from datetime import UTC, datetime, timedelta

from app.modules.employees.models import Employee, EmploymentStatus
from app.modules.employees.service import EmployeeService
from app.modules.identity.models import User
from app.modules.interviews.models import (
    Interview,
    InterviewInterviewer,
    InterviewerRecommendation,
    InterviewOutcome,
    InterviewSlot,
    InterviewStatus,
)
from app.modules.interviews.repository import InterviewRepository
from app.modules.interviews.schemas import (
    InterviewCompleteRequest,
    InterviewCreateRequest,
    InterviewDetailResponse,
    InterviewFeedbackView,
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

MIN_SLOT_COUNT = 1
MAX_SLOT_COUNT = 10

RECOMMENDATION_LABELS = {
    InterviewerRecommendation.PROCEED: "Proceed",
    InterviewerRecommendation.ADDITIONAL_INTERVIEW: "Additional interview",
    InterviewerRecommendation.DO_NOT_PROCEED: "Do not proceed",
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

        primary, additional = self._resolve_panel(
            payload.primary_employee_id,
            payload.additional_employee_ids,
        )
        message = (payload.message or "").strip() or None

        assignments = [
            InterviewInterviewer(employee_id=primary.id, is_primary=True),
            *[
                InterviewInterviewer(employee_id=employee.id, is_primary=False)
                for employee in additional
            ],
        ]

        interview = Interview(
            application_id=application.id,
            interviewer_employee_id=primary.id,
            created_by_user_id=created_by.id,
            message=message,
            status=InterviewStatus.PROPOSED,
            panel_assignments=assignments,
        )
        created = self.repository.add(interview)

        if self.notifications is not None and primary.user_id is not None:
            self.notifications.create_notification(
                recipient_user_id=primary.user_id,
                type=NotificationType.INTERVIEW_ASSIGNMENT,
                title="Interview assignment",
                message=(
                    f"You have been assigned as the primary interviewer for "
                    f"{application.candidate.user.full_name} ({application.job.title}). "
                    "Please propose available interview slots."
                ),
                related_entity_type="interview",
                related_entity_id=created.id,
            )

        return created

    def propose_slots(
        self,
        interview_id: int,
        slots: list,
        *,
        actor: User,
    ) -> Interview:
        interview = self.repository.get_by_id(interview_id)
        if interview is None:
            raise AppException("Interview not found", status_code=404)

        actor_employee = self._require_actor_employee(actor)
        if not self._is_primary(interview, actor_employee.id):
            raise AppException("Only the primary interviewer can propose slots", status_code=403)

        interview = self._normalize_interview_state(interview)
        if interview.status != InterviewStatus.PROPOSED:
            raise AppException("Slots can only be proposed for proposed interviews", status_code=400)
        if interview.slots:
            raise AppException("Interview slots have already been proposed", status_code=409)

        validated = _validate_slots(slots)
        for starts_at, ends_at in validated:
            interview.slots.append(
                InterviewSlot(
                    starts_at=starts_at,
                    ends_at=ends_at,
                    is_selected=False,
                    is_available=True,
                )
            )
        saved = self.repository.save(interview)

        if self.notifications is not None:
            self.notifications.create_notification(
                recipient_user_id=saved.application.candidate.user_id,
                type=NotificationType.INTERVIEW_INVITATION,
                title="Interview invitation",
                message=(
                    f"You have been invited to an interview for {saved.application.job.title}. "
                    "Please choose one of the proposed time slots."
                ),
                related_entity_type="interview",
                related_entity_id=saved.id,
            )

        return saved

    def list_for_application(self, application_id: int) -> list[Interview]:
        application = self.applications.get_by_id(application_id)
        if application is None:
            raise AppException("Application not found", status_code=404)
        interviews = self.repository.list_for_application(application_id)
        return [self._normalize_interview_state(interview) for interview in interviews]

    def list_for_hr(
        self,
        *,
        status: InterviewStatus | str | None = None,
        application_id: int | None = None,
        job_id: int | None = None,
        primary_employee_id: int | None = None,
        awaiting: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Interview]:
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))
        if awaiting is not None and awaiting not in (
            "primary_slots",
            "candidate_selection",
        ):
            raise AppException(
                "awaiting must be 'primary_slots' or 'candidate_selection'",
                status_code=400,
            )
        status_enum: InterviewStatus | None = None
        if status is not None:
            if isinstance(status, InterviewStatus):
                status_enum = status
            else:
                try:
                    status_enum = InterviewStatus(str(status).strip().lower())
                except ValueError as exc:
                    raise AppException("Invalid interview status", status_code=400) from exc

        interviews = self.repository.list_for_hr(
            status=status_enum,
            application_id=application_id,
            job_id=job_id,
            primary_employee_id=primary_employee_id,
            awaiting=awaiting,
            limit=limit,
            offset=offset,
        )
        return [self._normalize_interview_state(interview) for interview in interviews]

    def list_upcoming_scheduled(
        self,
        *,
        days_ahead: int = 7,
        limit: int = 20,
        now: datetime | None = None,
    ) -> list[Interview]:
        days_ahead = max(1, min(int(days_ahead), 14))
        limit = max(1, min(int(limit), 50))
        start = now if now is not None else datetime.now(UTC)
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        else:
            start = start.astimezone(UTC)
        until = start + timedelta(days=days_ahead)
        interviews = self.repository.list_upcoming_scheduled(
            now=start, until=until, limit=limit
        )
        return [self._normalize_interview_state(interview) for interview in interviews]

    def list_for_employee_user(self, user: User) -> list[Interview]:
        employee = self._require_actor_employee(user)
        interviews = self.repository.list_for_employee(employee.id)
        return [self._normalize_interview_state(interview) for interview in interviews]

    def get_for_panel_member(self, user: User, interview_id: int) -> Interview:
        interview = self.repository.get_by_id(interview_id)
        if interview is None:
            raise AppException("Interview not found", status_code=404)
        employee = self._require_actor_employee(user)
        if not self._is_panel_member(interview, employee.id):
            raise AppException("Interview not found", status_code=404)
        return self._normalize_interview_state(interview)

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
        interview = self._normalize_interview_state(interview)
        if interview.status == InterviewStatus.PROPOSED and not interview.slots:
            raise AppException("Interview not found", status_code=404)
        return interview

    def confirm_slot(self, user: User, interview_id: int, slot_id: int) -> Interview:
        interview = self.repository.get_by_id(interview_id)
        if interview is None:
            raise AppException("Interview not found", status_code=404)
        if interview.application.candidate.user_id != user.id:
            raise AppException("Interview not found", status_code=404)

        interview = self._normalize_interview_state(interview)
        if not interview.slots:
            raise AppException("No interview slots are available yet", status_code=400)
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
        self._notify_scheduled(saved)
        return saved

    def complete_interview(
        self,
        interview_id: int,
        payload: InterviewCompleteRequest,
        *,
        actor: User,
    ) -> Interview:
        interview = self.repository.get_by_id(interview_id)
        if interview is None:
            raise AppException("Interview not found", status_code=404)

        actor_employee = self._require_actor_employee(actor)
        if not self._is_primary(interview, actor_employee.id):
            raise AppException("Only the primary interviewer can complete this interview", status_code=403)

        interview = self._normalize_interview_state(interview)
        if interview.status != InterviewStatus.SCHEDULED:
            raise AppException(
                "Only scheduled interviews can be marked as completed",
                status_code=400,
            )

        interview.status = InterviewStatus.COMPLETED
        interview.tech_knowledge = payload.tech_knowledge
        interview.communication = payload.communication
        interview.problem_solving = payload.problem_solving
        interview.relevant_experience = payload.relevant_experience
        interview.strengths = payload.strengths.strip()
        interview.weaknesses = payload.weaknesses.strip()
        comments = (payload.additional_comments or "").strip() or None
        interview.additional_comments = comments
        interview.feedback = comments or interview.strengths
        interview.recommendation = payload.recommendation
        interview.completed_by_employee_id = actor_employee.id
        interview.completed_at = datetime.now(UTC)
        saved = self.repository.save(interview)

        if self.notifications is not None and saved.created_by_user_id is not None:
            self.notifications.create_notification(
                recipient_user_id=saved.created_by_user_id,
                type=NotificationType.APPLICATION_STATUS_CHANGED,
                title="Interview feedback ready",
                message=(
                    f"Interview feedback for {saved.application.candidate.user.full_name} "
                    f"({saved.application.job.title}) is ready for your decision."
                ),
                related_entity_type="interview",
                related_entity_id=saved.id,
            )

        return saved

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

    def _notify_scheduled(self, interview: Interview) -> None:
        if self.notifications is None:
            return
        selected = interview.selected_slot
        slot_text = ""
        if selected is not None:
            slot_text = f" for {_format_slot_range(selected.starts_at, selected.ends_at)}"
        candidate_name = interview.application.candidate.user.full_name
        job_title = interview.application.job.title

        notified: set[int] = set()

        self.notifications.create_notification(
            recipient_user_id=interview.application.candidate.user_id,
            type=NotificationType.INTERVIEW_SCHEDULED,
            title="Interview confirmed",
            message=f"Your interview for {job_title} is confirmed{slot_text}.",
            related_entity_type="interview",
            related_entity_id=interview.id,
        )
        notified.add(interview.application.candidate.user_id)

        for assignment in interview.panel_assignments:
            employee = assignment.employee
            if employee is None or employee.user_id is None:
                continue
            if employee.user_id in notified:
                continue
            self.notifications.create_notification(
                recipient_user_id=employee.user_id,
                type=NotificationType.INTERVIEW_SCHEDULED,
                title="Interview scheduled",
                message=f"{candidate_name} confirmed the interview for {job_title}{slot_text}.",
                related_entity_type="interview",
                related_entity_id=interview.id,
            )
            notified.add(employee.user_id)

        hr_recipient_id = interview.created_by_user_id
        if hr_recipient_id is not None and hr_recipient_id not in notified:
            self.notifications.create_notification(
                recipient_user_id=hr_recipient_id,
                type=NotificationType.INTERVIEW_SCHEDULED,
                title="Interview confirmed by candidate",
                message=f"{candidate_name} confirmed the interview for {job_title}{slot_text}.",
                related_entity_type="interview",
                related_entity_id=interview.id,
            )

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

    def _require_actor_employee(self, user: User) -> Employee:
        employee = self.repository.get_employee_for_user(user.id)
        if employee is None:
            raise AppException("Employee profile required", status_code=403)
        return employee

    def _is_panel_member(self, interview: Interview, employee_id: int) -> bool:
        return any(row.employee_id == employee_id for row in (interview.panel_assignments or []))

    def _is_primary(self, interview: Interview, employee_id: int) -> bool:
        for row in interview.panel_assignments or []:
            if row.employee_id == employee_id and row.is_primary:
                return True
        return interview.interviewer_employee_id == employee_id and not (interview.panel_assignments or [])

    def _resolve_panel(
        self,
        primary_employee_id: int,
        additional_employee_ids: list[int],
    ) -> tuple[Employee, list[Employee]]:
        if primary_employee_id in additional_employee_ids:
            raise AppException("Primary interviewer cannot also be listed as additional", status_code=400)
        if len(additional_employee_ids) != len(set(additional_employee_ids)):
            raise AppException("Duplicate interviewer is not allowed", status_code=400)

        all_ids = [primary_employee_id, *additional_employee_ids]
        employees = self.repository.get_employees_by_ids(all_ids)
        by_id = {employee.id: employee for employee in employees}
        missing = [employee_id for employee_id in all_ids if employee_id not in by_id]
        if missing:
            raise AppException("Interviewer employee not found", status_code=404)

        user_ids = [employee.user_id for employee in employees if employee.user_id is not None]
        users_by_id = self.repository.get_users_by_ids(user_ids)

        def _validate(employee: Employee) -> Employee:
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
            return employee

        primary = _validate(by_id[primary_employee_id])
        additional = [_validate(by_id[employee_id]) for employee_id in additional_employee_ids]
        return primary, additional


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


def _status_label(interview: Interview) -> str:
    if interview.status == InterviewStatus.PROPOSED:
        if interview.slots:
            return "Waiting for candidate to choose a slot"
        return "Waiting for primary interviewer availability"
    if interview.status == InterviewStatus.SCHEDULED:
        return "Scheduled"
    if interview.status == InterviewStatus.COMPLETED:
        return "Completed"
    if interview.status == InterviewStatus.CANCELLED:
        return "Cancelled"
    return interview.status.value


def _outcome_label(outcome: InterviewOutcome | None) -> str | None:
    if outcome is None:
        return None
    return OUTCOME_LABELS.get(outcome, outcome.value)


def _recommendation_label(value: InterviewerRecommendation | None) -> str | None:
    if value is None:
        return None
    return RECOMMENDATION_LABELS.get(value, value.value)


def _primary_employee(interview: Interview) -> Employee | None:
    for row in interview.panel_assignments or []:
        if row.is_primary and row.employee is not None:
            return row.employee
    if interview.interviewer is not None:
        return interview.interviewer
    return None


def _resolve_hr_notification_recipient(interview: Interview) -> int | None:
    if interview.created_by_user_id is not None:
        return interview.created_by_user_id
    primary = _primary_employee(interview)
    if primary is not None and primary.user_id is not None:
        return primary.user_id
    return None


def _interviewer_summaries(interview: Interview) -> list[InterviewerSummary]:
    summaries: list[InterviewerSummary] = []
    for row in interview.panel_assignments or []:
        if row.employee is None:
            continue
        summaries.append(
            InterviewerSummary(
                employee_id=row.employee.id,
                full_name=row.employee.full_name,
                position=row.employee.position,
                is_primary=bool(row.is_primary),
            )
        )
    if summaries:
        return summaries
    primary = interview.interviewer
    if primary is None:
        return []
    return [
        InterviewerSummary(
            employee_id=primary.id,
            full_name=primary.full_name,
            position=primary.position,
            is_primary=True,
        )
    ]


def _evaluation_view(interview: Interview, *, include: bool) -> InterviewFeedbackView | None:
    if not include:
        return None
    if interview.status != InterviewStatus.COMPLETED and interview.recommendation is None:
        return None
    return InterviewFeedbackView(
        tech_knowledge=interview.tech_knowledge,
        communication=interview.communication,
        problem_solving=interview.problem_solving,
        relevant_experience=interview.relevant_experience,
        strengths=interview.strengths,
        weaknesses=interview.weaknesses,
        additional_comments=interview.additional_comments or interview.feedback,
        recommendation=interview.recommendation.value if interview.recommendation else None,
        recommendation_label=_recommendation_label(interview.recommendation),
    )


def _actor_flags(interview: Interview, actor_employee_id: int | None) -> tuple[str | None, bool, bool]:
    if actor_employee_id is None:
        return None, False, False
    role = None
    for row in interview.panel_assignments or []:
        if row.employee_id == actor_employee_id:
            role = "primary" if row.is_primary else "panel"
            break
    if role is None and interview.interviewer_employee_id == actor_employee_id:
        role = "primary"
    can_propose = role == "primary" and interview.status == InterviewStatus.PROPOSED and not interview.slots
    can_complete = role == "primary" and interview.status == InterviewStatus.SCHEDULED
    return role, can_propose, can_complete


def build_interview_summary(
    interview: Interview,
    *,
    hired_employee_id: int | None = None,
    include_evaluation: bool = True,
    actor_employee_id: int | None = None,
) -> InterviewSummary:
    application = interview.application
    candidate = application.candidate
    selected = interview.selected_slot
    primary = _primary_employee(interview)
    role, can_propose, can_complete = _actor_flags(interview, actor_employee_id)
    return InterviewSummary(
        id=interview.id,
        application_id=interview.application_id,
        status=interview.status.value,
        status_label=_status_label(interview),
        message=interview.message,
        created_at=interview.created_at,
        job_title=application.job.title,
        candidate_name=candidate.user.full_name,
        interviewer_name=primary.full_name if primary else None,
        interviewers=_interviewer_summaries(interview),
        selected_slot=_slot_response(selected) if selected else None,
        slot_count=len(interview.slots or []),
        feedback=interview.feedback if include_evaluation else None,
        evaluation=_evaluation_view(interview, include=include_evaluation),
        completed_at=interview.completed_at,
        outcome=interview.outcome.value if interview.outcome else None,
        outcome_label=_outcome_label(interview.outcome),
        hired_employee_id=hired_employee_id,
        meeting_url=interview.meeting_url,
        my_role=role,
        can_propose_slots=can_propose,
        can_complete=can_complete,
    )


def build_interview_detail(
    interview: Interview,
    *,
    hired_employee_id: int | None = None,
    include_evaluation: bool = True,
    actor_employee_id: int | None = None,
) -> InterviewDetailResponse:
    application = interview.application
    candidate = application.candidate
    selected = interview.selected_slot
    primary = _primary_employee(interview)
    role, can_propose, can_complete = _actor_flags(interview, actor_employee_id)
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
        status_label=_status_label(interview),
        message=interview.message,
        created_at=interview.created_at,
        updated_at=interview.updated_at,
        job_title=application.job.title,
        candidate_name=candidate.user.full_name,
        interviewer_name=primary.full_name if primary else None,
        interviewers=_interviewer_summaries(interview),
        slots=[_slot_response(slot) for slot in sorted(visible_slots, key=lambda s: s.starts_at)],
        selected_slot=_slot_response(selected) if selected else None,
        slot_count=len(interview.slots or []),
        feedback=interview.feedback if include_evaluation else None,
        evaluation=_evaluation_view(interview, include=include_evaluation),
        completed_at=interview.completed_at,
        outcome=interview.outcome.value if interview.outcome else None,
        outcome_label=_outcome_label(interview.outcome),
        hired_employee_id=hired_employee_id,
        meeting_url=interview.meeting_url,
        my_role=role,
        can_propose_slots=can_propose,
        can_complete=can_complete,
    )
