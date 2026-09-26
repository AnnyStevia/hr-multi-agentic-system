"""AI tools that wrap Core HR recruitment services (read-only; no direct DB)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.ai.core.context import AIExecutionContext
from app.ai.tools.base import BaseTool, ToolMetadata
from app.ai.tools.exceptions import ToolExecutionError
from app.modules.recruitment.application_service import (
    ApplicationService,
    build_application_list_item,
    build_fit_assessment,
    build_hr_application_detail,
)
from app.modules.recruitment.models import ApplicationStatus
from app.modules.recruitment.schemas import (
    ApplicationListItem,
    FitAssessmentResponse,
    HrApplicationDetail,
    RecruitmentApplicationListResponse,
    RecruitmentOverviewResponse,
)
from app.modules.recruitment.service import JobService, build_job_response
from app.shared.exceptions import AppException

_READ_META = ToolMetadata(
    operation="read",
    required_permissions=frozenset({"recruitment:read"}),
    operates_on_current_user=False,
)

_WRITE_META = ToolMetadata(
    operation="write",
    required_permissions=frozenset({"recruitment:write"}),
    operates_on_current_user=False,
    may_require_confirmation=True,
)


def _call_service(fn, *, error_message: str):
    try:
        return fn()
    except AppException as exc:
        raise ToolExecutionError(exc.message) from exc
    except ToolExecutionError:
        raise
    except Exception as exc:
        raise ToolExecutionError(error_message) from exc


# --- get_job ---


class GetJobInput(BaseModel):
    model_config = {"extra": "forbid"}

    job_id: int = Field(ge=1)


class GetJobOutput(BaseModel):
    model_config = {"extra": "forbid"}

    id: int
    title: str
    description: str
    requirements: str | None = None
    employment_type: str
    internship_duration_months: int | None = None
    status: str
    department: str | None = None
    position: str | None = None
    location: str | None = None
    published_at: datetime | None = None
    closed_at: datetime | None = None


class GetJobTool(BaseTool):
    name = "get_job"
    description = (
        "Return HR job details by job_id: title, description, requirements, "
        "employment type, status, and related metadata. Read-only."
    )
    metadata = _READ_META
    input_model = GetJobInput
    output_model = GetJobOutput

    def __init__(self, job_service: JobService):
        self._jobs = job_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, GetJobInput)
        job = _call_service(
            lambda: self._jobs.get_job(args.job_id),
            error_message="Failed to retrieve job",
        )
        response = build_job_response(job)
        return GetJobOutput(
            id=response.id,
            title=response.title,
            description=response.description,
            requirements=response.requirements,
            employment_type=response.employment_type.value
            if hasattr(response.employment_type, "value")
            else str(response.employment_type),
            internship_duration_months=response.internship_duration_months,
            status=response.status.value
            if hasattr(response.status, "value")
            else str(response.status),
            department=response.department,
            position=response.position,
            location=response.location,
            published_at=response.published_at,
            closed_at=response.closed_at,
        )


# --- get_application ---


class GetApplicationInput(BaseModel):
    model_config = {"extra": "forbid"}

    application_id: int = Field(ge=1)


class GetApplicationOutput(BaseModel):
    """Compact HR application detail for the agent (includes fit when present)."""

    model_config = {"extra": "forbid"}

    application: HrApplicationDetail


class GetApplicationTool(BaseTool):
    name = "get_application"
    description = (
        "Return an HR application by application_id: candidate, job, status, dates, "
        "education/experience/answers, and fit assessment when available. Read-only."
    )
    metadata = _READ_META
    input_model = GetApplicationInput
    output_model = GetApplicationOutput

    def __init__(self, application_service: ApplicationService):
        self._applications = application_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, GetApplicationInput)
        application = _call_service(
            lambda: self._applications.get_for_hr(args.application_id),
            error_message="Failed to retrieve application",
        )
        return GetApplicationOutput(
            application=build_hr_application_detail(application)
        )


# --- get_application_fit ---


class GetApplicationFitInput(BaseModel):
    model_config = {"extra": "forbid"}

    application_id: int = Field(ge=1)


class GetApplicationFitOutput(BaseModel):
    model_config = {"extra": "forbid"}

    application_id: int
    available: bool
    fit_assessment: FitAssessmentResponse | None = None
    message: str | None = None


class GetApplicationFitTool(BaseTool):
    name = "get_application_fit"
    description = (
        "Return the fit assessment for an application_id (score, level, matching/"
        "missing skills, experience/education match, explanation). "
        "Returns available=false when analysis is not ready. Read-only."
    )
    metadata = _READ_META
    input_model = GetApplicationFitInput
    output_model = GetApplicationFitOutput

    def __init__(self, application_service: ApplicationService):
        self._applications = application_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, GetApplicationFitInput)
        application = _call_service(
            lambda: self._applications.get_for_hr(args.application_id),
            error_message="Failed to retrieve application fit",
        )
        fit = build_fit_assessment(application)
        if fit is None:
            return GetApplicationFitOutput(
                application_id=args.application_id,
                available=False,
                fit_assessment=None,
                message="Fit analysis is not available for this application yet.",
            )
        return GetApplicationFitOutput(
            application_id=args.application_id,
            available=True,
            fit_assessment=fit,
            message=None,
        )


# --- list_job_applications ---


class ListJobApplicationsInput(BaseModel):
    model_config = {"extra": "forbid"}

    job_id: int = Field(ge=1)
    status: ApplicationStatus | None = None


class ListJobApplicationsOutput(BaseModel):
    model_config = {"extra": "forbid"}

    job_id: int
    count: int
    applications: list[ApplicationListItem] = Field(default_factory=list)


class ListJobApplicationsTool(BaseTool):
    name = "list_job_applications"
    description = (
        "List applications for a job_id. Optional status filter "
        "(submitted, screening, shortlisted, rejected, hired). "
        "Returns candidate identifiers, status, and fit score/level when available. Read-only."
    )
    metadata = _READ_META
    input_model = ListJobApplicationsInput
    output_model = ListJobApplicationsOutput

    def __init__(self, application_service: ApplicationService):
        self._applications = application_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, ListJobApplicationsInput)
        rows = _call_service(
            lambda: self._applications.list_for_job(args.job_id),
            error_message="Failed to list job applications",
        )
        if args.status is not None:
            rows = [row for row in rows if row.status == args.status]
        items = [build_application_list_item(row) for row in rows]
        return ListJobApplicationsOutput(
            job_id=args.job_id,
            count=len(items),
            applications=items,
        )


# --- list_recruitment_applications (overview) ---


class ListRecruitmentApplicationsInput(BaseModel):
    model_config = {"extra": "forbid"}

    mode: str = Field(description='Use "summary" for counts/aggregation or "list" for paginated rows.')
    job_id: int | None = Field(default=None, ge=1)
    status: ApplicationStatus | None = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ListRecruitmentApplicationsOutput(BaseModel):
    model_config = {"extra": "forbid"}

    mode: str
    summary: RecruitmentOverviewResponse | None = None
    listing: RecruitmentApplicationListResponse | None = None


class ListRecruitmentApplicationsTool(BaseTool):
    name = "list_recruitment_applications"
    description = (
        "Recruitment overview. mode=summary returns unique candidate count, total applications, "
        "and applications_by_job (use for 'how many candidates/applications'). "
        "mode=list returns paginated compact application rows (optional job_id/status filters). "
        "Distinguish unique candidates from total applications. Read-only."
    )
    metadata = _READ_META
    input_model = ListRecruitmentApplicationsInput
    output_model = ListRecruitmentApplicationsOutput

    def __init__(self, application_service: ApplicationService):
        self._applications = application_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, ListRecruitmentApplicationsInput)
        mode = (args.mode or "").strip().lower()
        if mode not in {"summary", "list"}:
            raise ToolExecutionError('mode must be "summary" or "list"')
        if mode == "summary":
            summary = _call_service(
                lambda: self._applications.get_recruitment_overview(
                    job_id=args.job_id, status=args.status
                ),
                error_message="Failed to load recruitment overview",
            )
            return ListRecruitmentApplicationsOutput(mode="summary", summary=summary, listing=None)
        listing = _call_service(
            lambda: self._applications.list_recruitment_applications(
                job_id=args.job_id,
                status=args.status,
                limit=args.limit,
                offset=args.offset,
            ),
            error_message="Failed to list recruitment applications",
        )
        return ListRecruitmentApplicationsOutput(mode="list", summary=None, listing=listing)


# --- shortlist_application ---


class ShortlistApplicationInput(BaseModel):
    model_config = {"extra": "forbid"}

    application_id: int = Field(ge=1)


class ApplicationStatusChangeOutput(BaseModel):
    model_config = {"extra": "forbid"}

    application_id: int
    previous_status: str
    new_status: str
    candidate_id: int
    candidate_name: str
    job_id: int
    job_title: str
    reason: str | None = None


class ShortlistApplicationTool(BaseTool):
    name = "shortlist_application"
    description = (
        "Shortlist an application by application_id (sets status to shortlisted). "
        "Only valid when current status is screening. "
        "Use only on an explicit shortlist request. Write action."
    )
    metadata = _WRITE_META
    input_model = ShortlistApplicationInput
    output_model = ApplicationStatusChangeOutput

    def __init__(self, application_service: ApplicationService):
        self._applications = application_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, ShortlistApplicationInput)
        current = _call_service(
            lambda: self._applications.get_for_hr(args.application_id),
            error_message="Failed to load application",
        )
        previous = current.status.value if hasattr(current.status, "value") else str(current.status)
        candidate_id = current.candidate_id
        candidate_name = current.candidate.user.full_name
        job_id = current.job_id
        job_title = current.job.title
        updated = _call_service(
            lambda: self._applications.update_status(
                args.application_id, ApplicationStatus.SHORTLISTED
            ),
            error_message="Failed to shortlist application",
        )
        return ApplicationStatusChangeOutput(
            application_id=updated.id,
            previous_status=previous,
            new_status=updated.status.value
            if hasattr(updated.status, "value")
            else str(updated.status),
            candidate_id=candidate_id,
            candidate_name=candidate_name,
            job_id=job_id,
            job_title=job_title,
        )


# --- reject_application ---


class RejectApplicationInput(BaseModel):
    model_config = {"extra": "forbid"}

    application_id: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=2000)


class RejectApplicationTool(BaseTool):
    name = "reject_application"
    description = (
        "Reject an application by application_id (sets status to rejected). "
        "Optional reason is for the reply only and is not stored. "
        "Use only on an explicit reject request. Write action."
    )
    metadata = _WRITE_META
    input_model = RejectApplicationInput
    output_model = ApplicationStatusChangeOutput

    def __init__(self, application_service: ApplicationService):
        self._applications = application_service

    def execute(self, context: AIExecutionContext, args: BaseModel) -> BaseModel:
        assert isinstance(args, RejectApplicationInput)
        current = _call_service(
            lambda: self._applications.get_for_hr(args.application_id),
            error_message="Failed to load application",
        )
        previous = current.status.value if hasattr(current.status, "value") else str(current.status)
        candidate_id = current.candidate_id
        candidate_name = current.candidate.user.full_name
        job_id = current.job_id
        job_title = current.job.title
        updated = _call_service(
            lambda: self._applications.update_status(
                args.application_id, ApplicationStatus.REJECTED
            ),
            error_message="Failed to reject application",
        )
        reason = (args.reason or "").strip() or None
        return ApplicationStatusChangeOutput(
            application_id=updated.id,
            previous_status=previous,
            new_status=updated.status.value
            if hasattr(updated.status, "value")
            else str(updated.status),
            candidate_id=candidate_id,
            candidate_name=candidate_name,
            job_id=job_id,
            job_title=job_title,
            reason=reason,
        )
