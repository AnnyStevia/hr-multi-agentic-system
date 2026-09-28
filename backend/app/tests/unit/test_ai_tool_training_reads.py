"""Unit tests for Training Agent read tools — auth / identity / leakage matrix."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.ai.core.context import AIExecutionContext
from app.ai.tools.authorization import authorize_tool
from app.ai.tools.exceptions import (
    ToolAuthorizationError,
    ToolExecutionError,
    ToolValidationError,
)
from app.ai.tools.executor import ToolExecutor
from app.ai.tools.registry import ToolRegistry
from app.ai.tools.training_reads import (
    EmptyInput,
    ListMyTrainingAssignmentsTool,
    ListOnboardingTrainingAssignmentsInput,
    ListOnboardingTrainingAssignmentsTool,
    ListTrainingsTool,
)
from app.modules.training.models import OnboardingTrainingStatus
from app.shared.exceptions import AppException


def _employee() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=9,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"training:read", "leaves:read"}),
        employee_id=99,
        candidate_id=None,
    )


def _hr() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=1,
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"training:read"}),
        employee_id=10,
        candidate_id=None,
    )


def _admin() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=2,
        role_names=frozenset({"admin"}),
        permission_names=frozenset({"training:read"}),
        employee_id=20,
        candidate_id=None,
    )


def _manager() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=5,
        role_names=frozenset({"manager"}),
        permission_names=frozenset({"training:read", "leaves:read"}),
        employee_id=50,
        candidate_id=None,
    )


def _candidate() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=8,
        role_names=frozenset({"candidate"}),
        permission_names=frozenset(),
        employee_id=None,
        candidate_id=3,
    )


_HR_TOOLS = (
    (ListTrainingsTool, EmptyInput()),
    (
        ListOnboardingTrainingAssignmentsTool,
        ListOnboardingTrainingAssignmentsInput(onboarding_id=1),
    ),
)


def _assert_generic_deny(exc: ToolAuthorizationError) -> None:
    msg = str(exc).lower()
    assert "not authorized" in msg
    assert "not found" not in msg
    assert "employee_id" not in msg
    assert "onboarding" not in msg or "not authorized" in msg
    assert "resource_url" not in msg
    assert "sqlalchemy" not in msg
    assert "traceback" not in msg
    assert "sarah" not in msg
    assert "ada" not in msg


def _assignment_mock(
    *,
    assignment_id: int = 11,
    onboarding_id: int = 1,
    training_id: int = 5,
    status: OnboardingTrainingStatus = OnboardingTrainingStatus.PENDING,
    resource_url: str | None = "https://learn.example.com/safety",
):
    now = datetime.now(UTC)
    training = MagicMock()
    training.id = training_id
    training.title = "Safety Course"
    training.description = "Read the handbook"
    training.resource_url = resource_url
    assignment = MagicMock()
    assignment.id = assignment_id
    assignment.onboarding_id = onboarding_id
    assignment.training_id = training_id
    assignment.status = status
    assignment.assigned_at = now
    assignment.completed_at = now if status == OnboardingTrainingStatus.COMPLETED else None
    assignment.created_at = now
    assignment.updated_at = now
    assignment.training = training
    return assignment


def _training_mock(*, training_id: int = 5, resource_url: str | None = None):
    training = MagicMock()
    training.id = training_id
    training.title = "Catalogue Course"
    training.description = "Overview"
    training.resource_url = resource_url
    return training


# --- Authorization ---


def test_employee_can_authorize_self_tool():
    authorize_tool(ListMyTrainingAssignmentsTool(MagicMock()), _employee(), EmptyInput())


def test_manager_can_authorize_self_tool():
    authorize_tool(ListMyTrainingAssignmentsTool(MagicMock()), _manager(), EmptyInput())


def test_employee_cannot_authorize_hr_tools_even_with_training_read():
    service = MagicMock()
    ctx = _employee()
    for tool_cls, args in _HR_TOOLS:
        with pytest.raises(ToolAuthorizationError) as exc_info:
            authorize_tool(tool_cls(service), ctx, args)
        _assert_generic_deny(exc_info.value)


def test_manager_cannot_authorize_hr_tools_even_with_training_read():
    service = MagicMock()
    ctx = _manager()
    for tool_cls, args in _HR_TOOLS:
        with pytest.raises(ToolAuthorizationError) as exc_info:
            authorize_tool(tool_cls(service), ctx, args)
        _assert_generic_deny(exc_info.value)


def test_candidate_cannot_authorize_hr_tools():
    service = MagicMock()
    ctx = _candidate()
    for tool_cls, args in _HR_TOOLS:
        with pytest.raises(ToolAuthorizationError) as exc_info:
            authorize_tool(tool_cls(service), ctx, args)
        _assert_generic_deny(exc_info.value)


def test_hr_can_authorize_hr_tools():
    service = MagicMock()
    ctx = _hr()
    for tool_cls, args in _HR_TOOLS:
        authorize_tool(tool_cls(service), ctx, args)


def test_admin_can_authorize_hr_tools():
    service = MagicMock()
    ctx = _admin()
    for tool_cls, args in _HR_TOOLS:
        authorize_tool(tool_cls(service), ctx, args)


def test_self_input_rejects_identity_and_onboarding_arguments():
    assert "employee_id" not in EmptyInput.model_fields
    assert "user_id" not in EmptyInput.model_fields
    assert "onboarding_id" not in EmptyInput.model_fields
    with pytest.raises(ValidationError):
        EmptyInput.model_validate({"employee_id": 42})
    with pytest.raises(ValidationError):
        EmptyInput.model_validate({"onboarding_id": 7})

    service = MagicMock()
    registry = ToolRegistry()
    registry.register(ListMyTrainingAssignmentsTool(service))
    executor = ToolExecutor(registry)
    with pytest.raises(ToolValidationError):
        executor.execute(_employee(), "list_my_training_assignments", {"employee_id": 42})
    with pytest.raises(ToolValidationError):
        executor.execute(
            _employee(), "list_my_training_assignments", {"onboarding_id": 7}
        )
    service.list_assignments_for_user.assert_not_called()


def test_hr_onboarding_assignments_reject_employee_id_input():
    with pytest.raises(ValidationError):
        ListOnboardingTrainingAssignmentsInput.model_validate(
            {"onboarding_id": 1, "employee_id": 99}
        )


# --- SELF execute ---


def test_employee_lists_own_pending_and_completed_with_resource_url():
    service = MagicMock()
    pending = _assignment_mock(assignment_id=1, status=OnboardingTrainingStatus.PENDING)
    completed = _assignment_mock(
        assignment_id=2,
        training_id=6,
        status=OnboardingTrainingStatus.COMPLETED,
        resource_url="https://learn.example.com/done",
    )
    completed.training.title = "Completed Course"
    service.list_assignments_for_user.return_value = [pending, completed]

    out = ListMyTrainingAssignmentsTool(service).execute(_employee(), EmptyInput())
    service.list_assignments_for_user.assert_called_once_with(9)
    assert len(out.assignments) == 2
    assert out.assignments[0].status == "pending"
    assert out.assignments[0].resource_url == "https://learn.example.com/safety"
    assert out.assignments[0].assignment_id == 1
    assert out.assignments[0].title == "Safety Course"
    assert out.assignments[1].status == "completed"
    assert out.assignments[1].resource_url == "https://learn.example.com/done"
    assert out.assignments[1].completed_at is not None


def test_missing_onboarding_returns_empty_list():
    service = MagicMock()
    service.list_assignments_for_user.return_value = []
    out = ListMyTrainingAssignmentsTool(service).execute(_employee(), EmptyInput())
    assert out.assignments == []
    service.list_assignments_for_user.assert_called_once_with(9)


def test_candidate_self_returns_empty_without_error():
    service = MagicMock()
    service.list_assignments_for_user.return_value = []
    authorize_tool(ListMyTrainingAssignmentsTool(service), _candidate(), EmptyInput())
    out = ListMyTrainingAssignmentsTool(service).execute(_candidate(), EmptyInput())
    assert out.assignments == []
    service.list_assignments_for_user.assert_called_once_with(8)


# --- HR execute ---


def test_hr_lists_catalogue_including_resource_url():
    service = MagicMock()
    service.list_trainings.return_value = [
        _training_mock(training_id=1, resource_url="https://learn.example.com/a"),
        _training_mock(training_id=2, resource_url=None),
    ]
    service.list_trainings.return_value[1].title = "No Link"

    out = ListTrainingsTool(service).execute(_hr(), EmptyInput())
    service.list_trainings.assert_called_once_with()
    assert len(out.trainings) == 2
    assert out.trainings[0].training_id == 1
    assert out.trainings[0].resource_url == "https://learn.example.com/a"
    assert out.trainings[1].resource_url is None


def test_admin_lists_catalogue():
    service = MagicMock()
    service.list_trainings.return_value = [_training_mock()]
    out = ListTrainingsTool(service).execute(_admin(), EmptyInput())
    assert len(out.trainings) == 1
    assert out.trainings[0].title == "Catalogue Course"


def test_hr_lists_onboarding_assignments():
    service = MagicMock()
    service.list_assignments_for_hr.return_value = [
        _assignment_mock(onboarding_id=44, status=OnboardingTrainingStatus.PENDING)
    ]
    out = ListOnboardingTrainingAssignmentsTool(service).execute(
        _hr(),
        ListOnboardingTrainingAssignmentsInput(onboarding_id=44),
    )
    service.list_assignments_for_hr.assert_called_once_with(44)
    assert len(out.assignments) == 1
    assert out.assignments[0].onboarding_id == 44
    assert out.assignments[0].status == "pending"
    assert out.assignments[0].resource_url == "https://learn.example.com/safety"


def test_hr_onboarding_not_found_is_controlled():
    service = MagicMock()
    service.list_assignments_for_hr.side_effect = AppException(
        "Onboarding not found", status_code=404
    )
    with pytest.raises(ToolExecutionError, match="Onboarding not found"):
        ListOnboardingTrainingAssignmentsTool(service).execute(
            _hr(),
            ListOnboardingTrainingAssignmentsInput(onboarding_id=999),
        )


def test_hr_without_training_read_denied():
    service = MagicMock()
    ctx = AIExecutionContext(
        user_id=1,
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"onboarding:read"}),
        employee_id=10,
        candidate_id=None,
    )
    for tool_cls, args in _HR_TOOLS:
        with pytest.raises(ToolAuthorizationError) as exc_info:
            authorize_tool(tool_cls(service), ctx, args)
        _assert_generic_deny(exc_info.value)
        if tool_cls is ListTrainingsTool:
            service.list_trainings.assert_not_called()
        else:
            service.list_assignments_for_hr.assert_not_called()


def test_admin_lists_onboarding_assignments():
    service = MagicMock()
    service.list_assignments_for_hr.return_value = [
        _assignment_mock(onboarding_id=7, status=OnboardingTrainingStatus.COMPLETED)
    ]
    out = ListOnboardingTrainingAssignmentsTool(service).execute(
        _admin(),
        ListOnboardingTrainingAssignmentsInput(onboarding_id=7),
    )
    assert out.assignments[0].onboarding_id == 7
    assert out.assignments[0].status == "completed"


def test_manager_lists_own_assignments_only():
    service = MagicMock()
    service.list_assignments_for_user.return_value = [
        _assignment_mock(assignment_id=3, resource_url=None)
    ]
    out = ListMyTrainingAssignmentsTool(service).execute(_manager(), EmptyInput())
    service.list_assignments_for_user.assert_called_once_with(5)
    assert len(out.assignments) == 1
    assert out.assignments[0].resource_url is None


def test_post_hire_candidate_role_with_employee_uses_self_user_id():
    """Post-hire: candidate role may remain, but employee_id is set."""
    ctx = AIExecutionContext(
        user_id=88,
        role_names=frozenset({"candidate", "employee"}),
        permission_names=frozenset({"training:read"}),
        employee_id=880,
        candidate_id=3,
    )
    service = MagicMock()
    service.list_assignments_for_user.return_value = [_assignment_mock()]
    authorize_tool(ListMyTrainingAssignmentsTool(service), ctx, EmptyInput())
    out = ListMyTrainingAssignmentsTool(service).execute(ctx, EmptyInput())
    service.list_assignments_for_user.assert_called_once_with(88)
    assert out.assignments[0].title == "Safety Course"
    # Still no HR catalogue
    with pytest.raises(ToolAuthorizationError) as exc_info:
        authorize_tool(ListTrainingsTool(service), ctx, EmptyInput())
    _assert_generic_deny(exc_info.value)


def test_executor_denies_employee_hr_catalogue_without_service_call():
    service = MagicMock()
    registry = ToolRegistry()
    registry.register(ListTrainingsTool(service))
    executor = ToolExecutor(registry)
    with pytest.raises(ToolAuthorizationError) as exc_info:
        executor.execute(_employee(), "list_trainings", {})
    _assert_generic_deny(exc_info.value)
    service.list_trainings.assert_not_called()


def test_executor_denies_manager_hr_onboarding_assignments_without_service_call():
    service = MagicMock()
    registry = ToolRegistry()
    registry.register(ListOnboardingTrainingAssignmentsTool(service))
    executor = ToolExecutor(registry)
    with pytest.raises(ToolAuthorizationError) as exc_info:
        executor.execute(
            _manager(),
            "list_onboarding_training_assignments",
            {"onboarding_id": 99},
        )
    _assert_generic_deny(exc_info.value)
    service.list_assignments_for_hr.assert_not_called()


def test_self_tool_metadata_has_no_training_read_requirement():
    tool = ListMyTrainingAssignmentsTool(MagicMock())
    assert tool.metadata.operates_on_current_user is True
    assert tool.metadata.required_permissions == frozenset()
    assert tool.metadata.required_roles == frozenset()


def test_hr_tool_metadata_requires_staff_and_training_read():
    for tool_cls in (ListTrainingsTool, ListOnboardingTrainingAssignmentsTool):
        meta = tool_cls(MagicMock()).metadata
        assert meta.required_roles == frozenset({"hr", "admin"})
        assert meta.required_permissions == frozenset({"training:read"})
        assert meta.operates_on_current_user is False


def test_unexpected_service_exception_is_generic():
    service = MagicMock()
    service.list_trainings.side_effect = RuntimeError(
        "sqlalchemy.exc.OperationalError: secret db"
    )
    with pytest.raises(ToolExecutionError) as exc_info:
        ListTrainingsTool(service).execute(_hr(), EmptyInput())
    msg = str(exc_info.value).lower()
    assert "unable to load training catalogue" in msg
    assert "sqlalchemy" not in msg
    assert "secret" not in msg


def test_app_exception_with_orm_noise_is_sanitized():
    service = MagicMock()
    service.list_assignments_for_hr.side_effect = AppException(
        "SQLAlchemy traceback leaked", status_code=500
    )
    with pytest.raises(ToolExecutionError) as exc_info:
        ListOnboardingTrainingAssignmentsTool(service).execute(
            _hr(),
            ListOnboardingTrainingAssignmentsInput(onboarding_id=1),
        )
    assert "sqlalchemy" not in str(exc_info.value).lower()
    assert "Unable to load onboarding training assignments" in str(exc_info.value)


def test_outputs_are_plain_pydantic_not_orm():
    service = MagicMock()
    service.list_assignments_for_user.return_value = [_assignment_mock()]
    out = ListMyTrainingAssignmentsTool(service).execute(_employee(), EmptyInput())
    dumped = out.model_dump()
    assert "assignments" in dumped
    assert set(dumped["assignments"][0].keys()) == {
        "assignment_id",
        "training_id",
        "title",
        "description",
        "resource_url",
        "status",
        "assigned_at",
        "completed_at",
    }
