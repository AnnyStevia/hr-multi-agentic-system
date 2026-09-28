"""Unit tests for Onboarding Agent read tools — auth / identity / leakage matrix."""

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
from app.ai.tools.find_employees import FindEmployeesTool
from app.ai.tools.onboarding_reads import (
    EmptyInput,
    GetMyOnboardingProgressTool,
    GetMyOnboardingTool,
    GetOnboardingByEmployeeInput,
    GetOnboardingByEmployeeTool,
    GetOnboardingInput,
    GetOnboardingProgressInput,
    GetOnboardingProgressTool,
    GetOnboardingTool,
    ListMyOnboardingTasksTool,
    ListOnboardingTasksInput,
    ListOnboardingTasksTool,
    ListOnboardingTemplatesInput,
    ListOnboardingTemplatesTool,
    ListOnboardingsTool,
)
from app.ai.tools.registry import ToolRegistry
from app.modules.onboarding.models import (
    OnboardingStatus,
    OnboardingTaskStatus,
    OnboardingTaskType,
)
from app.modules.onboarding.schemas import (
    DocumentCountResponse,
    OnboardingListItemResponse,
    OnboardingProgressResponse,
    ProgressCountResponse,
)


def _employee() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=9,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"leaves:read", "employees:read"}),
        employee_id=99,
        candidate_id=None,
    )


def _hr() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=1,
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"onboarding:read", "recruitment:read"}),
        employee_id=10,
        candidate_id=None,
    )


def _admin() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=2,
        role_names=frozenset({"admin"}),
        permission_names=frozenset({"onboarding:read"}),
        employee_id=20,
        candidate_id=None,
    )


def _manager() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=5,
        role_names=frozenset({"manager"}),
        permission_names=frozenset({"leaves:read", "employees:read"}),
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
    (ListOnboardingsTool, EmptyInput()),
    (GetOnboardingTool, GetOnboardingInput(onboarding_id=1)),
    (GetOnboardingByEmployeeTool, GetOnboardingByEmployeeInput(employee_id=99)),
    (GetOnboardingProgressTool, GetOnboardingProgressInput(onboarding_id=1)),
    (ListOnboardingTasksTool, ListOnboardingTasksInput(onboarding_id=1)),
    (ListOnboardingTemplatesTool, ListOnboardingTemplatesInput()),
)

_SELF_TOOLS = (
    GetMyOnboardingTool,
    GetMyOnboardingProgressTool,
    ListMyOnboardingTasksTool,
)


def _onboarding_mock(*, onboarding_id: int = 1, employee_id: int = 99):
    now = datetime.now(UTC)
    ob = MagicMock()
    ob.id = onboarding_id
    ob.employee_id = employee_id
    ob.status = OnboardingStatus.IN_PROGRESS
    ob.started_at = now
    ob.completed_at = None
    ob.created_at = now
    ob.updated_at = now
    return ob


def _task_mock(*, task_id: int = 7, onboarding_id: int = 1):
    now = datetime.now(UTC)
    task = MagicMock()
    task.id = task_id
    task.onboarding_id = onboarding_id
    task.template_id = None
    task.title = "Read company policies"
    task.description = None
    task.task_type = OnboardingTaskType.ACKNOWLEDGEMENT
    task.is_required = True
    task.document_type = None
    task.training_id = None
    task.status = OnboardingTaskStatus.PENDING
    task.due_date = None
    task.completed_at = None
    task.created_at = now
    task.updated_at = now
    return task


def _progress(*, onboarding_id: int = 1) -> OnboardingProgressResponse:
    return OnboardingProgressResponse(
        onboarding_id=onboarding_id,
        status=OnboardingStatus.IN_PROGRESS,
        completed_at=None,
        tasks=ProgressCountResponse(total=3, completed=1, pending=2),
        required_tasks=ProgressCountResponse(total=2, completed=1, pending=1),
        optional_tasks=ProgressCountResponse(total=1, completed=0, pending=1),
        trainings=ProgressCountResponse(total=1, completed=0, pending=1),
        documents=DocumentCountResponse(total=0),
        overall_percentage=33,
    )


def _assert_generic_deny(exc: ToolAuthorizationError) -> None:
    msg = str(exc).lower()
    assert "not authorized" in msg
    assert "not found" not in msg
    assert "ada" not in msg
    assert "lovelace" not in msg
    assert "employee_id" not in msg


# --- Authorization ---


def test_employee_can_authorize_self_tools():
    service = MagicMock()
    ctx = _employee()
    for tool_cls in _SELF_TOOLS:
        authorize_tool(tool_cls(service), ctx, EmptyInput())


def test_manager_can_authorize_self_tools_only():
    """Managers may read their own onboarding; not organizational HR tools."""
    service = MagicMock()
    ctx = _manager()
    for tool_cls in _SELF_TOOLS:
        authorize_tool(tool_cls(service), ctx, EmptyInput())


def test_employee_cannot_authorize_any_hr_tool():
    service = MagicMock()
    ctx = _employee()
    for tool_cls, args in _HR_TOOLS:
        with pytest.raises(ToolAuthorizationError) as exc_info:
            authorize_tool(tool_cls(service), ctx, args)
        _assert_generic_deny(exc_info.value)


def test_manager_cannot_authorize_any_hr_tool():
    service = MagicMock()
    ctx = _manager()
    for tool_cls, args in _HR_TOOLS:
        with pytest.raises(ToolAuthorizationError) as exc_info:
            authorize_tool(tool_cls(service), ctx, args)
        _assert_generic_deny(exc_info.value)


def test_candidate_cannot_authorize_any_hr_tool():
    service = MagicMock()
    ctx = _candidate()
    for tool_cls, args in _HR_TOOLS:
        with pytest.raises(ToolAuthorizationError) as exc_info:
            authorize_tool(tool_cls(service), ctx, args)
        _assert_generic_deny(exc_info.value)


def test_hr_can_authorize_all_hr_tools():
    service = MagicMock()
    ctx = _hr()
    for tool_cls, args in _HR_TOOLS:
        authorize_tool(tool_cls(service), ctx, args)


def test_admin_can_authorize_all_hr_tools():
    service = MagicMock()
    ctx = _admin()
    for tool_cls, args in _HR_TOOLS:
        authorize_tool(tool_cls(service), ctx, args)


def test_missing_employee_id_rejects_self_without_calling_service():
    service = MagicMock()
    ctx = _candidate()
    for tool_cls in _SELF_TOOLS:
        authorize_tool(tool_cls(service), ctx, EmptyInput())
        with pytest.raises(ToolExecutionError, match="No employee profile"):
            tool_cls(service).execute(ctx, EmptyInput())
    service.get_for_employee_user.assert_not_called()
    service.get_progress_for_employee_user.assert_not_called()
    service.list_tasks_for_employee_user.assert_not_called()


def test_input_schema_rejects_identity_arguments():
    assert "employee_id" not in EmptyInput.model_fields
    assert "user_id" not in EmptyInput.model_fields

    with pytest.raises(ValidationError):
        EmptyInput.model_validate({"employee_id": 42})
    with pytest.raises(ValidationError):
        EmptyInput.model_validate({"user_id": 9})

    service = MagicMock()
    registry = ToolRegistry()
    registry.register(GetMyOnboardingTool(service))
    executor = ToolExecutor(registry)
    with pytest.raises(ToolValidationError):
        executor.execute(_employee(), "get_my_onboarding", {"employee_id": 42})
    service.get_for_employee_user.assert_not_called()


def test_find_employees_still_requires_recruitment_read():
    tool = FindEmployeesTool(MagicMock())
    assert "recruitment:read" in tool.metadata.required_permissions
    with pytest.raises(ToolAuthorizationError) as exc_info:
        authorize_tool(
            tool,
            AIExecutionContext(
                user_id=1,
                role_names=frozenset({"hr"}),
                permission_names=frozenset({"onboarding:read"}),
                employee_id=10,
                candidate_id=None,
            ),
            tool.input_model.model_validate({"q": "Ada"}),
        )
    _assert_generic_deny(exc_info.value)


# --- SELF execution ---


def test_get_my_onboarding_uses_caller_user_id_only():
    service = MagicMock()
    service.get_for_employee_user.return_value = _onboarding_mock()
    out = GetMyOnboardingTool(service).execute(_employee(), EmptyInput())
    service.get_for_employee_user.assert_called_once_with(9)
    assert out.onboarding.onboarding_id == 1
    assert out.onboarding.employee_id == 99
    assert out.onboarding.status == "in_progress"


def test_manager_self_uses_manager_user_id_not_report():
    service = MagicMock()
    service.get_for_employee_user.return_value = _onboarding_mock(
        onboarding_id=8, employee_id=50
    )
    out = GetMyOnboardingTool(service).execute(_manager(), EmptyInput())
    service.get_for_employee_user.assert_called_once_with(5)
    assert out.onboarding.employee_id == 50


def test_get_my_progress_and_tasks():
    service = MagicMock()
    service.get_progress_for_employee_user.return_value = _progress()
    service.list_tasks_for_employee_user.return_value = [_task_mock()]
    progress_out = GetMyOnboardingProgressTool(service).execute(
        _employee(), EmptyInput()
    )
    tasks_out = ListMyOnboardingTasksTool(service).execute(_employee(), EmptyInput())
    service.get_progress_for_employee_user.assert_called_once_with(9)
    service.list_tasks_for_employee_user.assert_called_once_with(9)
    assert progress_out.progress.overall_percentage == 33
    assert tasks_out.count == 1
    assert tasks_out.tasks[0].is_required is True
    assert tasks_out.tasks[0].task_type == "acknowledgement"


# --- HR execution ---


def test_hr_list_and_get_onboarding():
    service = MagicMock()
    now = datetime.now(UTC)
    service.list_for_hr.return_value = [
        OnboardingListItemResponse(
            id=1,
            employee_id=99,
            employee_name="Ada Lovelace",
            position="Engineer",
            status=OnboardingStatus.IN_PROGRESS,
            started_at=now,
            completed_at=None,
            completed_tasks_count=1,
            total_tasks_count=3,
        )
    ]
    service.get_for_hr.return_value = _onboarding_mock()
    service.get_by_employee_id_for_hr.return_value = _onboarding_mock(employee_id=99)
    service.get_progress_for_hr.return_value = _progress()
    service.list_tasks_for_hr.return_value = [_task_mock()]

    listed = ListOnboardingsTool(service).execute(_hr(), EmptyInput())
    assert listed.count == 1
    assert listed.items[0].employee_name == "Ada Lovelace"

    got = GetOnboardingTool(service).execute(
        _hr(), GetOnboardingInput(onboarding_id=1)
    )
    assert got.onboarding.onboarding_id == 1

    by_emp = GetOnboardingByEmployeeTool(service).execute(
        _hr(), GetOnboardingByEmployeeInput(employee_id=99)
    )
    service.get_by_employee_id_for_hr.assert_called_once_with(99)
    assert by_emp.onboarding.employee_id == 99

    prog = GetOnboardingProgressTool(service).execute(
        _hr(), GetOnboardingProgressInput(onboarding_id=1)
    )
    assert prog.progress.required_tasks.pending == 1

    tasks = ListOnboardingTasksTool(service).execute(
        _hr(), ListOnboardingTasksInput(onboarding_id=1)
    )
    assert tasks.count == 1


def test_admin_list_templates():
    service = MagicMock()
    now = datetime.now(UTC)
    tmpl = MagicMock()
    tmpl.id = 2
    tmpl.title = "Upload ID"
    tmpl.description = None
    tmpl.task_type = OnboardingTaskType.DOCUMENT
    tmpl.is_required = True
    tmpl.is_active = True
    tmpl.document_type = None
    tmpl.training_id = None
    tmpl.created_at = now
    tmpl.updated_at = now
    service.list_templates.return_value = [tmpl]
    out = ListOnboardingTemplatesTool(service).execute(
        _admin(), ListOnboardingTemplatesInput(active_only=True)
    )
    service.list_templates.assert_called_once_with(active_only=True)
    assert out.count == 1
    assert out.templates[0].title == "Upload ID"


def test_hr_list_templates():
    service = MagicMock()
    now = datetime.now(UTC)
    tmpl = MagicMock()
    tmpl.id = 2
    tmpl.title = "Upload ID"
    tmpl.description = None
    tmpl.task_type = OnboardingTaskType.DOCUMENT
    tmpl.is_required = True
    tmpl.is_active = True
    tmpl.document_type = None
    tmpl.training_id = None
    tmpl.created_at = now
    tmpl.updated_at = now
    service.list_templates.return_value = [tmpl]
    out = ListOnboardingTemplatesTool(service).execute(
        _hr(), ListOnboardingTemplatesInput(active_only=True)
    )
    service.list_templates.assert_called_once_with(active_only=True)
    assert out.count == 1
    assert out.templates[0].title == "Upload ID"
