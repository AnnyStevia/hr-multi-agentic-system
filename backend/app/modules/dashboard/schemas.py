from datetime import date, datetime

from pydantic import BaseModel, Field


class DashboardKpis(BaseModel):
    total_employees: int
    active_employees: int
    on_leave: int
    pending_leave: int
    onboarding: int
    open_jobs: int
    pending_applications: int


class WorkforceBreakdownItem(BaseModel):
    label: str
    count: int


class DashboardWorkforce(BaseModel):
    by_department: list[WorkforceBreakdownItem]
    by_position: list[WorkforceBreakdownItem]
    by_employment_status: list[WorkforceBreakdownItem]


class DashboardHireItem(BaseModel):
    employee_id: int
    employee_name: str
    department: str | None = None
    position: str | None = None
    hire_date: date


class DashboardLeaveItem(BaseModel):
    request_id: int
    employee_id: int
    employee_name: str
    leave_type: str
    start_date: date
    end_date: date
    status: str


class DashboardOnboardingItem(BaseModel):
    onboarding_id: int
    employee_id: int
    employee_name: str
    status: str
    completed_tasks: int
    total_tasks: int
    progress_percent: int = Field(ge=0, le=100)


class DashboardInterviewItem(BaseModel):
    interview_id: int
    application_id: int
    candidate_name: str
    job_id: int
    job_title: str
    starts_at: datetime
    status: str


class DashboardApplicationItem(BaseModel):
    application_id: int
    job_id: int
    candidate_name: str
    job_title: str
    status: str
    submitted_at: datetime | None = None


class DashboardDeadlineItem(BaseModel):
    onboarding_id: int
    employee_name: str
    task_title: str
    due_date: date


class DashboardActivity(BaseModel):
    recent_hires: list[DashboardHireItem]
    on_leave: list[DashboardLeaveItem]
    returning_soon: list[DashboardLeaveItem]
    upcoming_interviews: list[DashboardInterviewItem]
    onboarding: list[DashboardOnboardingItem]
    upcoming_deadlines: list[DashboardDeadlineItem] = []


class DashboardLeaveOverview(BaseModel):
    approved: int
    pending: int
    rejected: int


class DashboardAttention(BaseModel):
    pending_leave: list[DashboardLeaveItem]
    pending_applications: list[DashboardApplicationItem]
    incomplete_onboarding: list[DashboardOnboardingItem]
    upcoming_interviews: list[DashboardInterviewItem]


class HrDashboardResponse(BaseModel):
    kpis: DashboardKpis
    workforce: DashboardWorkforce
    leave_overview: DashboardLeaveOverview
    activity: DashboardActivity
    attention: DashboardAttention
