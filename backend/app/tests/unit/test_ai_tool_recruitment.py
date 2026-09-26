"""Unit tests for recruitment AI tools (mocked services; no Gemini)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.ai.core.context import AIExecutionContext
from app.ai.tools import (
    GetApplicationFitTool,
    GetApplicationTool,
    GetJobTool,
    ListJobApplicationsTool,
    ToolAuthorizationError,
    ToolExecutor,
    ToolExecutionError,
    ToolRegistry,
)
from app.modules.recruitment.models import ApplicationStatus, EmploymentType, JobStatus
from app.modules.recruitment.schemas import (
    CandidateSummary,
    FitAssessmentResponse,
    HrApplicationDetail,
    JobSummary,
)
from app.shared.exceptions import AppException


def _hr_context(**overrides) -> AIExecutionContext:
    data = dict(
        user_id=1,
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"recruitment:read"}),
        employee_id=10,
        candidate_id=None,
    )
    data.update(overrides)
    return AIExecutionContext(**data)


def _employee_context() -> AIExecutionContext:
    return _hr_context(
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"leaves:read"}),
        employee_id=99,
    )


def _candidate_context() -> AIExecutionContext:
    return _hr_context(
        role_names=frozenset({"candidate"}),
        permission_names=frozenset(),
        employee_id=None,
        candidate_id=5,
    )


def _job():
    job = MagicMock()
    job.id = 7
    job.title = "Backend Engineer"
    job.description = "Build APIs"
    job.requirements = "Python, FastAPI"
    job.employment_type = EmploymentType.FULL_TIME
    job.internship_duration_months = None
    job.status = JobStatus.PUBLISHED
    job.department_id = 1
    job.department_rel = MagicMock(name="Engineering")
    job.department_rel.name = "Engineering"
    job.position = "Engineer"
    job.location = "Tunis"
    job.published_at = datetime(2026, 1, 1, tzinfo=UTC)
    job.closed_at = None
    job.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    job.updated_at = datetime(2026, 1, 1, tzinfo=UTC)
    job.created_by_user_id = 1
    job.questions = []
    return job


def _registry_with(*tools) -> ToolRegistry:
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    return registry


def test_get_job_happy_path():
    service = MagicMock()
    service.get_job.return_value = _job()
    registry = _registry_with(GetJobTool(service))
    result = ToolExecutor(registry).execute(_hr_context(), "get_job", {"job_id": 7})
    assert result.success is True
    assert result.data["title"] == "Backend Engineer"
    assert result.data["employment_type"] == "full_time"
    service.get_job.assert_called_once_with(7)


def test_get_job_not_found():
    service = MagicMock()
    service.get_job.side_effect = AppException("Job not found", status_code=404)
    registry = _registry_with(GetJobTool(service))
    with pytest.raises(ToolExecutionError, match="Job not found"):
        ToolExecutor(registry).execute(_hr_context(), "get_job", {"job_id": 99})


def test_get_application_includes_fit():
    application = MagicMock()
    detail = HrApplicationDetail(
        id=3,
        status=ApplicationStatus.SUBMITTED,
        submitted_at=datetime(2026, 1, 2, tzinfo=UTC),
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
        updated_at=datetime(2026, 1, 2, tzinfo=UTC),
        candidate=CandidateSummary(
            id=1,
            user_id=2,
            first_name="Ada",
            last_name="Lovelace",
            full_name="Ada Lovelace",
            email="ada@example.com",
            phone=None,
        ),
        job=JobSummary(
            id=7,
            title="Backend Engineer",
            department="Engineering",
            department_id=1,
            status=JobStatus.PUBLISHED,
        ),
        education=[],
        experience=[],
        answers=[],
        documents=[],
        fit_assessment=FitAssessmentResponse(
            fit_score=82,
            fit_level="GOOD",
            matching_skills=["Python"],
            missing_skills=["Kubernetes"],
            experience_match="Strong",
            education_match="Match",
            explanation="Evidence only",
            analysis_version="1",
            analyzed_at=datetime(2026, 1, 3, tzinfo=UTC),
        ),
    )
    service = MagicMock()
    service.get_for_hr.return_value = application
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.ai.tools.recruitment.build_hr_application_detail",
            lambda _app: detail,
        )
        registry = _registry_with(GetApplicationTool(service))
        result = ToolExecutor(registry).execute(
            _hr_context(), "get_application", {"application_id": 3}
        )
    assert result.data["application"]["fit_assessment"]["fit_score"] == 82
    assert result.data["application"]["candidate"]["full_name"] == "Ada Lovelace"


def test_get_application_fit_unavailable():
    service = MagicMock()
    service.get_for_hr.return_value = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.ai.tools.recruitment.build_fit_assessment", lambda _app: None)
        registry = _registry_with(GetApplicationFitTool(service))
        result = ToolExecutor(registry).execute(
            _hr_context(), "get_application_fit", {"application_id": 3}
        )
    assert result.data["available"] is False
    assert result.data["fit_assessment"] is None


def test_get_application_fit_available():
    fit = FitAssessmentResponse(
        fit_score=55,
        fit_level="MEDIUM",
        matching_skills=["Python"],
        missing_skills=["FastAPI"],
        experience_match="Partial",
        education_match="Match",
        explanation="Medium fit",
        analysis_version="1",
        analyzed_at=datetime(2026, 1, 3, tzinfo=UTC),
    )
    service = MagicMock()
    service.get_for_hr.return_value = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.ai.tools.recruitment.build_fit_assessment", lambda _app: fit)
        registry = _registry_with(GetApplicationFitTool(service))
        result = ToolExecutor(registry).execute(
            _hr_context(), "get_application_fit", {"application_id": 3}
        )
    assert result.data["available"] is True
    assert result.data["fit_assessment"]["fit_level"] == "MEDIUM"


def test_list_job_applications_filters_status():
    submitted = MagicMock(status=ApplicationStatus.SUBMITTED)
    screening = MagicMock(status=ApplicationStatus.SCREENING)
    service = MagicMock()
    service.list_for_job.return_value = [submitted, screening]

    from app.modules.recruitment.schemas import ApplicationListItem

    def real_item(app):
        return ApplicationListItem(
            id=1 if app is submitted else 2,
            status=app.status,
            submitted_at=datetime(2026, 1, 1, tzinfo=UTC),
            candidate=CandidateSummary(
                id=1,
                user_id=2,
                first_name="A",
                last_name="B",
                full_name="A B",
                email="a@b.com",
            ),
            has_cv=True,
            has_cover_letter=False,
            fit_score=None,
            fit_level=None,
        )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.ai.tools.recruitment.build_application_list_item", real_item)
        registry = _registry_with(ListJobApplicationsTool(service))
        result = ToolExecutor(registry).execute(
            _hr_context(),
            "list_job_applications",
            {"job_id": 7, "status": "screening"},
        )
    assert result.data["count"] == 1
    assert result.data["applications"][0]["status"] == "screening"


def test_employee_cannot_call_recruitment_tools():
    service = MagicMock()
    registry = _registry_with(GetJobTool(service))
    with pytest.raises(ToolAuthorizationError):
        ToolExecutor(registry).execute(_employee_context(), "get_job", {"job_id": 1})
    service.get_job.assert_not_called()


def test_candidate_cannot_call_recruitment_tools():
    service = MagicMock()
    registry = _registry_with(GetApplicationTool(service))
    with pytest.raises(ToolAuthorizationError):
        ToolExecutor(registry).execute(
            _candidate_context(), "get_application", {"application_id": 1}
        )
    service.get_for_hr.assert_not_called()


def test_recruitment_registry_is_read_only():
    jobs = MagicMock()
    apps = MagicMock()
    registry = _registry_with(
        GetJobTool(jobs),
        GetApplicationTool(apps),
        GetApplicationFitTool(apps),
        ListJobApplicationsTool(apps),
    )
    names = {tool.name for tool in registry.list_tools()}
    assert names == {
        "get_job",
        "get_application",
        "get_application_fit",
        "list_job_applications",
    }
    for tool in registry.list_tools():
        assert tool.metadata.operation == "read"
