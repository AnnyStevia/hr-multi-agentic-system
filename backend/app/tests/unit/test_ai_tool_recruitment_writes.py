"""Unit tests for Phase 6.3B recruitment overview + write tools."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.ai.core.context import AIExecutionContext
from app.ai.tools import (
    ListRecruitmentApplicationsTool,
    RejectApplicationTool,
    ShortlistApplicationTool,
    ToolAuthorizationError,
    ToolExecutor,
    ToolExecutionError,
    ToolRegistry,
)
from app.modules.recruitment.models import ApplicationStatus
from app.modules.recruitment.schemas import (
    ApplicationsByJobItem,
    RecruitmentApplicationListItem,
    RecruitmentApplicationListResponse,
    RecruitmentOverviewResponse,
)
from app.shared.exceptions import AppException


def _hr_read(**overrides) -> AIExecutionContext:
    data = dict(
        user_id=1,
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"recruitment:read"}),
        employee_id=10,
        candidate_id=None,
    )
    data.update(overrides)
    return AIExecutionContext(**data)


def _hr_write() -> AIExecutionContext:
    return _hr_read(permission_names=frozenset({"recruitment:read", "recruitment:write"}))


def test_overview_summary_tool():
    service = MagicMock()
    service.get_recruitment_overview.return_value = RecruitmentOverviewResponse(
        total_unique_candidates=2,
        total_applications=3,
        total_jobs_with_applications=2,
        applications_by_job=[
            ApplicationsByJobItem(job_id=1, job_title="Java", application_count=2),
        ],
    )
    registry = ToolRegistry()
    registry.register(ListRecruitmentApplicationsTool(service))
    result = ToolExecutor(registry).execute(
        _hr_read(),
        "list_recruitment_applications",
        {"mode": "summary"},
    )
    assert result.data["mode"] == "summary"
    assert result.data["summary"]["total_unique_candidates"] == 2
    assert result.data["summary"]["total_applications"] == 3


def test_overview_list_tool():
    service = MagicMock()
    service.list_recruitment_applications.return_value = RecruitmentApplicationListResponse(
        total=1,
        limit=50,
        offset=0,
        items=[
            RecruitmentApplicationListItem(
                application_id=9,
                candidate_id=4,
                candidate_name="Ada Lovelace",
                job_id=1,
                job_title="Java",
                status=ApplicationStatus.SCREENING,
                fit_score=84,
                fit_level="GOOD",
            )
        ],
    )
    registry = ToolRegistry()
    registry.register(ListRecruitmentApplicationsTool(service))
    result = ToolExecutor(registry).execute(
        _hr_read(),
        "list_recruitment_applications",
        {"mode": "list", "job_id": 1, "status": "screening"},
    )
    assert result.data["listing"]["total"] == 1
    assert result.data["listing"]["items"][0]["fit_score"] == 84


def test_overview_denied_for_employee_and_candidate():
    service = MagicMock()
    registry = ToolRegistry()
    registry.register(ListRecruitmentApplicationsTool(service))
    with pytest.raises(ToolAuthorizationError):
        ToolExecutor(registry).execute(
            _hr_read(role_names=frozenset({"employee"}), permission_names=frozenset({"leaves:read"})),
            "list_recruitment_applications",
            {"mode": "summary"},
        )
    with pytest.raises(ToolAuthorizationError):
        ToolExecutor(registry).execute(
            _hr_read(role_names=frozenset({"candidate"}), permission_names=frozenset(), candidate_id=1, employee_id=None),
            "list_recruitment_applications",
            {"mode": "summary"},
        )
    service.get_recruitment_overview.assert_not_called()


def _application_mock(*, status: ApplicationStatus):
    app = MagicMock()
    app.id = 12
    app.status = status
    app.candidate_id = 5
    app.candidate.user.full_name = "Jane Doe"
    app.job_id = 3
    app.job.title = "Backend"
    return app


def test_shortlist_success_and_confirmation_flag():
    service = MagicMock()
    current = _application_mock(status=ApplicationStatus.SCREENING)
    updated = _application_mock(status=ApplicationStatus.SHORTLISTED)
    service.get_for_hr.return_value = current
    service.update_status.return_value = updated
    registry = ToolRegistry()
    registry.register(ShortlistApplicationTool(service))
    result = ToolExecutor(registry).execute(
        _hr_write(), "shortlist_application", {"application_id": 12}
    )
    assert result.may_require_confirmation is True
    assert result.data["previous_status"] == "screening"
    assert result.data["new_status"] == "shortlisted"
    service.update_status.assert_called_once_with(12, ApplicationStatus.SHORTLISTED)


def test_shortlist_invalid_transition():
    service = MagicMock()
    service.get_for_hr.return_value = _application_mock(status=ApplicationStatus.SUBMITTED)
    service.update_status.side_effect = AppException(
        "Cannot change status from submitted to shortlisted", status_code=400
    )
    registry = ToolRegistry()
    registry.register(ShortlistApplicationTool(service))
    with pytest.raises(ToolExecutionError, match="submitted to shortlisted"):
        ToolExecutor(registry).execute(_hr_write(), "shortlist_application", {"application_id": 12})


def test_shortlist_unauthorized_without_write():
    service = MagicMock()
    registry = ToolRegistry()
    registry.register(ShortlistApplicationTool(service))
    with pytest.raises(ToolAuthorizationError):
        ToolExecutor(registry).execute(_hr_read(), "shortlist_application", {"application_id": 12})
    service.update_status.assert_not_called()


def test_reject_success_echoes_reason():
    service = MagicMock()
    current = _application_mock(status=ApplicationStatus.SUBMITTED)
    updated = _application_mock(status=ApplicationStatus.REJECTED)
    service.get_for_hr.return_value = current
    service.update_status.return_value = updated
    registry = ToolRegistry()
    registry.register(RejectApplicationTool(service))
    result = ToolExecutor(registry).execute(
        _hr_write(),
        "reject_application",
        {"application_id": 12, "reason": "Missing experience"},
    )
    assert result.may_require_confirmation is True
    assert result.data["new_status"] == "rejected"
    assert result.data["reason"] == "Missing experience"
    service.update_status.assert_called_once_with(12, ApplicationStatus.REJECTED)


def test_reject_unauthorized():
    service = MagicMock()
    registry = ToolRegistry()
    registry.register(RejectApplicationTool(service))
    with pytest.raises(ToolAuthorizationError):
        ToolExecutor(registry).execute(_hr_read(), "reject_application", {"application_id": 1})
