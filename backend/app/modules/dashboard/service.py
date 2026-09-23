from datetime import UTC, date, datetime, timedelta

from app.modules.dashboard.schemas import (
    DashboardActivity,
    DashboardApplicationItem,
    DashboardAttention,
    DashboardDeadlineItem,
    DashboardHireItem,
    DashboardInterviewItem,
    DashboardKpis,
    DashboardLeaveItem,
    DashboardLeaveOverview,
    DashboardOnboardingItem,
    DashboardWorkforce,
    HrDashboardResponse,
    WorkforceBreakdownItem,
)
from app.modules.employees.models import Employee
from app.modules.employees.repository import EmployeeRepository
from app.modules.interviews.models import Interview
from app.modules.interviews.repository import InterviewRepository
from app.modules.leave.models import LeaveRequest, LeaveRequestStatus
from app.modules.leave.repository import LeaveRepository
from app.modules.onboarding.models import (
    Onboarding,
    OnboardingStatus,
    OnboardingTask,
    OnboardingTaskStatus,
)
from app.modules.onboarding.repository import OnboardingRepository
from app.modules.recruitment.models import Application, ApplicationStatus, JobStatus
from app.modules.recruitment.repository import ApplicationRepository, JobRepository

SECTION_LIMIT = 8
WINDOW_DAYS = 14


def _employee_name(employee: Employee | None) -> str:
    if employee is None:
        return "Unknown"
    return employee.full_name or "Unknown"


def _candidate_name(application: Application) -> str:
    candidate = application.candidate
    if candidate is None or candidate.user is None:
        return "Unknown"
    return candidate.user.full_name or "Unknown"


def _leave_item(request: LeaveRequest) -> DashboardLeaveItem:
    return DashboardLeaveItem(
        request_id=request.id,
        employee_id=request.employee_id,
        employee_name=_employee_name(request.employee),
        leave_type=request.leave_type.name if request.leave_type else "",
        start_date=request.start_date,
        end_date=request.end_date,
        status=request.status.value if hasattr(request.status, "value") else str(request.status),
    )


def _onboarding_item(onboarding: Onboarding) -> DashboardOnboardingItem:
    tasks = onboarding.tasks or []
    total = len(tasks)
    completed = sum(1 for task in tasks if task.status == OnboardingTaskStatus.COMPLETED)
    percent = int(round((completed / total) * 100)) if total else 0
    return DashboardOnboardingItem(
        onboarding_id=onboarding.id,
        employee_id=onboarding.employee_id,
        employee_name=_employee_name(onboarding.employee),
        status=onboarding.status.value if hasattr(onboarding.status, "value") else str(onboarding.status),
        completed_tasks=completed,
        total_tasks=total,
        progress_percent=percent,
    )


def _interview_item(interview: Interview) -> DashboardInterviewItem:
    application = interview.application
    job = application.job if application is not None else None
    slot = interview.selected_slot
    return DashboardInterviewItem(
        interview_id=interview.id,
        application_id=interview.application_id,
        candidate_name=_candidate_name(application) if application else "Unknown",
        job_id=job.id if job is not None else 0,
        job_title=job.title if job is not None else "",
        starts_at=slot.starts_at if slot is not None else interview.created_at,
        status=interview.status.value if hasattr(interview.status, "value") else str(interview.status),
    )


def _application_item(application: Application) -> DashboardApplicationItem:
    job = application.job
    return DashboardApplicationItem(
        application_id=application.id,
        job_id=application.job_id,
        candidate_name=_candidate_name(application),
        job_title=job.title if job is not None else "",
        status=application.status.value if hasattr(application.status, "value") else str(application.status),
        submitted_at=application.submitted_at,
    )


def _deadline_item(task: OnboardingTask) -> DashboardDeadlineItem:
    onboarding = task.onboarding
    employee = onboarding.employee if onboarding is not None else None
    return DashboardDeadlineItem(
        onboarding_id=task.onboarding_id,
        employee_name=_employee_name(employee),
        task_title=task.title,
        due_date=task.due_date,  # type: ignore[arg-type]
    )


def _breakdown(rows: list[tuple[str, int]]) -> list[WorkforceBreakdownItem]:
    return [WorkforceBreakdownItem(label=label, count=count) for label, count in rows]


class DashboardService:
    def __init__(
        self,
        employees: EmployeeRepository,
        leave: LeaveRepository,
        onboarding: OnboardingRepository,
        jobs: JobRepository,
        applications: ApplicationRepository,
        interviews: InterviewRepository,
    ):
        self.employees = employees
        self.leave = leave
        self.onboarding = onboarding
        self.jobs = jobs
        self.applications = applications
        self.interviews = interviews

    def get_hr_dashboard(self) -> HrDashboardResponse:
        today = date.today()
        now = datetime.now(UTC)
        until = now + timedelta(days=WINDOW_DAYS)
        hire_since = today - timedelta(days=WINDOW_DAYS)
        return_until = today + timedelta(days=WINDOW_DAYS)
        pending_app_statuses = [ApplicationStatus.SUBMITTED, ApplicationStatus.SCREENING]

        on_leave_rows = self.leave.list_approved_covering(today)
        pending_leave_rows = self.leave.list_pending_for_dashboard(limit=SECTION_LIMIT)
        returning_rows = self.leave.list_returning_soon(
            from_date=today, to_date=return_until, limit=SECTION_LIMIT
        )
        onboarding_rows = self.onboarding.list_by_status(
            OnboardingStatus.IN_PROGRESS, limit=SECTION_LIMIT
        )
        interview_rows = self.interviews.list_upcoming_scheduled(
            now=now, until=until, limit=SECTION_LIMIT
        )
        pending_apps = self.applications.list_pending(limit=SECTION_LIMIT)
        recent_hires = self.employees.list_recent_hires(since=hire_since, limit=SECTION_LIMIT)
        deadline_rows = self.onboarding.list_upcoming_task_deadlines(
            from_date=today, to_date=return_until, limit=SECTION_LIMIT
        )

        kpis = DashboardKpis(
            total_employees=self.employees.count_all(),
            active_employees=self.employees.count_active(),
            on_leave=int(self.leave.count_employees_on_leave(today)),
            pending_leave=self.leave.count_requests(status=LeaveRequestStatus.PENDING),
            onboarding=self.onboarding.count_by_status(OnboardingStatus.IN_PROGRESS),
            open_jobs=self.jobs.count_by_status(JobStatus.PUBLISHED),
            pending_applications=self.applications.count_by_statuses(pending_app_statuses),
        )

        leave_overview = DashboardLeaveOverview(
            approved=self.leave.count_requests(status=LeaveRequestStatus.APPROVED),
            pending=self.leave.count_requests(status=LeaveRequestStatus.PENDING),
            rejected=self.leave.count_requests(status=LeaveRequestStatus.REJECTED),
        )

        workforce = DashboardWorkforce(
            by_department=_breakdown(self.employees.count_by_department()),
            by_position=_breakdown(self.employees.count_by_position()),
            by_employment_status=_breakdown(self.employees.count_by_employment_status()),
        )

        activity = DashboardActivity(
            recent_hires=[
                DashboardHireItem(
                    employee_id=emp.id,
                    employee_name=_employee_name(emp),
                    department=emp.department.name if emp.department else None,
                    position=(
                        emp.org_position.title
                        if emp.org_position is not None
                        else emp.position
                    ),
                    hire_date=emp.hire_date,
                )
                for emp in recent_hires
            ],
            on_leave=[_leave_item(row) for row in on_leave_rows[:SECTION_LIMIT]],
            returning_soon=[_leave_item(row) for row in returning_rows],
            upcoming_interviews=[_interview_item(row) for row in interview_rows],
            onboarding=[_onboarding_item(row) for row in onboarding_rows],
            upcoming_deadlines=[_deadline_item(row) for row in deadline_rows],
        )

        attention = DashboardAttention(
            pending_leave=[_leave_item(row) for row in pending_leave_rows],
            pending_applications=[_application_item(row) for row in pending_apps],
            incomplete_onboarding=[_onboarding_item(row) for row in onboarding_rows],
            upcoming_interviews=[_interview_item(row) for row in interview_rows],
        )

        return HrDashboardResponse(
            kpis=kpis,
            workforce=workforce,
            leave_overview=leave_overview,
            activity=activity,
            attention=attention,
        )
