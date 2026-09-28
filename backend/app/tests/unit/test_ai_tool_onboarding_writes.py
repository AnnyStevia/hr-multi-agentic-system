"""Unit tests for confirmation-gated Onboarding write tools."""

from __future__ import annotations

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
from app.ai.tools.executor import ToolExecutor, _infer_target
from app.ai.tools.onboarding_writes import (
    AcknowledgeOnboardingTaskInput,
    AcknowledgeOnboardingTaskTool,
    CompleteManualOnboardingTaskInput,
    CompleteManualOnboardingTaskTool,
    CompleteOnboardingInput,
    CompleteOnboardingTool,
)
from app.ai.tools.registry import ToolRegistry
from app.modules.onboarding.models import OnboardingStatus, OnboardingTaskStatus
from app.shared.exceptions import AppException


def _employee() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=9,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"leaves:read"}),
        employee_id=99,
        candidate_id=None,
    )


def _hr() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=1,
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"onboarding:read", "onboarding:write"}),
        employee_id=10,
        candidate_id=None,
    )


def _admin() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=2,
        role_names=frozenset({"admin"}),
        permission_names=frozenset({"onboarding:write"}),
        employee_id=20,
        candidate_id=None,
    )


def _manager() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=5,
        role_names=frozenset({"manager"}),
        permission_names=frozenset({"leaves:read", "leaves:write"}),
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


def _task(*, task_id: int = 7, onboarding_id: int = 1):
    task = MagicMock()
    task.id = task_id
    task.onboarding_id = onboarding_id
    task.status = OnboardingTaskStatus.COMPLETED
    return task


def _onboarding(*, onboarding_id: int = 1, employee_id: int = 99):
    ob = MagicMock()
    ob.id = onboarding_id
    ob.employee_id = employee_id
    ob.status = OnboardingStatus.COMPLETED
    return ob


def _registry_with(*tools) -> ToolRegistry:
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    return registry


def test_infer_target_task_and_onboarding_ids():
    assert _infer_target("acknowledge_onboarding_task", {"task_id": 7}) == (
        "onboarding_task",
        7,
    )
    assert _infer_target("complete_onboarding", {"onboarding_id": 3}) == (
        "onboarding",
        3,
    )


def test_employee_can_authorize_ack_not_hr_writes():
    service = MagicMock()
    authorize_tool(
        AcknowledgeOnboardingTaskTool(service),
        _employee(),
        AcknowledgeOnboardingTaskInput(task_id=1),
    )
    with pytest.raises(ToolAuthorizationError):
        authorize_tool(
            CompleteManualOnboardingTaskTool(service),
            _employee(),
            CompleteManualOnboardingTaskInput(task_id=1),
        )
    with pytest.raises(ToolAuthorizationError):
        authorize_tool(
            CompleteOnboardingTool(service),
            _employee(),
            CompleteOnboardingInput(onboarding_id=1),
        )


def test_manager_and_candidate_denied_all_writes():
    service = MagicMock()
    for ctx in (_manager(), _candidate()):
        # Manager may authorize ACK for self metadata, but candidate lacks employee_id at execute
        if ctx.employee_id is not None:
            authorize_tool(
                AcknowledgeOnboardingTaskTool(service),
                ctx,
                AcknowledgeOnboardingTaskInput(task_id=1),
            )
        with pytest.raises(ToolAuthorizationError):
            authorize_tool(
                CompleteManualOnboardingTaskTool(service),
                ctx,
                CompleteManualOnboardingTaskInput(task_id=1),
            )
        with pytest.raises(ToolAuthorizationError):
            authorize_tool(
                CompleteOnboardingTool(service),
                ctx,
                CompleteOnboardingInput(onboarding_id=1),
            )


def test_hr_and_admin_authorize_hr_writes():
    service = MagicMock()
    for ctx in (_hr(), _admin()):
        authorize_tool(
            CompleteManualOnboardingTaskTool(service),
            ctx,
            CompleteManualOnboardingTaskInput(task_id=1),
        )
        authorize_tool(
            CompleteOnboardingTool(service),
            ctx,
            CompleteOnboardingInput(onboarding_id=1),
        )


def test_ack_input_rejects_employee_id():
    with pytest.raises(ValidationError):
        AcknowledgeOnboardingTaskInput.model_validate(
            {"task_id": 1, "employee_id": 42}
        )


def test_ack_missing_employee_profile_rejects_without_service():
    service = MagicMock()
    registry = _registry_with(AcknowledgeOnboardingTaskTool(service))
    with pytest.raises(ToolExecutionError, match="No employee profile"):
        ToolExecutor(registry).execute(
            _candidate(),
            "acknowledge_onboarding_task",
            {"task_id": 1},
            execute_writes=True,
        )
    service.acknowledge_task_for_employee.assert_not_called()


def test_ack_pending_then_execute_uses_user_id():
    service = MagicMock()
    service.acknowledge_task_for_employee.return_value = _task(task_id=7)
    registry = _registry_with(AcknowledgeOnboardingTaskTool(service))
    args = {"task_id": 7}

    pending = ToolExecutor(registry).execute(
        _employee(), "acknowledge_onboarding_task", args
    )
    assert pending.confirmation_token
    assert pending.data["status"] == "pending_confirmation"
    service.acknowledge_task_for_employee.assert_not_called()

    done = ToolExecutor(registry).execute(
        _employee(), "acknowledge_onboarding_task", args, execute_writes=True
    )
    service.acknowledge_task_for_employee.assert_called_once_with(9, 7)
    assert done.data["task_id"] == 7
    assert done.data["status"] == "completed"


def test_ack_service_rejects_non_ack_task():
    service = MagicMock()
    service.acknowledge_task_for_employee.side_effect = AppException(
        "Only acknowledgement tasks can be acknowledged by the employee",
        status_code=400,
    )
    registry = _registry_with(AcknowledgeOnboardingTaskTool(service))
    with pytest.raises(ToolExecutionError, match="acknowledgement"):
        ToolExecutor(registry).execute(
            _employee(),
            "acknowledge_onboarding_task",
            {"task_id": 7},
            execute_writes=True,
        )


def test_ack_other_employee_task_surfaces_not_found():
    service = MagicMock()
    service.acknowledge_task_for_employee.side_effect = AppException(
        "Onboarding task not found", status_code=404
    )
    registry = _registry_with(AcknowledgeOnboardingTaskTool(service))
    with pytest.raises(ToolExecutionError, match="not found"):
        ToolExecutor(registry).execute(
            _employee(),
            "acknowledge_onboarding_task",
            {"task_id": 99},
            execute_writes=True,
        )


def test_complete_manual_pending_then_execute():
    service = MagicMock()
    service.complete_manual_task_for_hr.return_value = _task(task_id=11, onboarding_id=2)
    registry = _registry_with(CompleteManualOnboardingTaskTool(service))
    args = {"task_id": 11}

    pending = ToolExecutor(registry).execute(
        _hr(), "complete_manual_onboarding_task", args
    )
    assert pending.confirmation_token
    service.complete_manual_task_for_hr.assert_not_called()

    done = ToolExecutor(registry).execute(
        _hr(), "complete_manual_onboarding_task", args, execute_writes=True
    )
    service.complete_manual_task_for_hr.assert_called_once_with(11)
    assert done.data["task_id"] == 11


def test_complete_manual_rejects_non_manual():
    service = MagicMock()
    service.complete_manual_task_for_hr.side_effect = AppException(
        "Only manual tasks can be completed by HR this way", status_code=400
    )
    registry = _registry_with(CompleteManualOnboardingTaskTool(service))
    with pytest.raises(ToolExecutionError, match="manual"):
        ToolExecutor(registry).execute(
            _hr(),
            "complete_manual_onboarding_task",
            {"task_id": 11},
            execute_writes=True,
        )


def test_complete_onboarding_pending_then_execute():
    service = MagicMock()
    service.complete_for_hr.return_value = _onboarding(onboarding_id=3, employee_id=99)
    registry = _registry_with(CompleteOnboardingTool(service))
    args = {"onboarding_id": 3}

    pending = ToolExecutor(registry).execute(_hr(), "complete_onboarding", args)
    assert pending.confirmation_token
    service.complete_for_hr.assert_not_called()

    done = ToolExecutor(registry).execute(
        _admin(), "complete_onboarding", args, execute_writes=True
    )
    service.complete_for_hr.assert_called_once_with(3)
    assert done.data["onboarding_id"] == 3
    assert done.data["status"] == "completed"


def test_employee_hr_write_authorize_fails_before_service():
    service = MagicMock()
    registry = _registry_with(
        CompleteManualOnboardingTaskTool(service),
        CompleteOnboardingTool(service),
    )
    with pytest.raises(ToolAuthorizationError):
        ToolExecutor(registry).execute(
            _employee(),
            "complete_manual_onboarding_task",
            {"task_id": 1},
            execute_writes=True,
        )
    with pytest.raises(ToolAuthorizationError):
        ToolExecutor(registry).execute(
            _employee(),
            "complete_onboarding",
            {"onboarding_id": 1},
            execute_writes=True,
        )
    service.complete_manual_task_for_hr.assert_not_called()
    service.complete_for_hr.assert_not_called()


def test_ack_rejects_identity_args_via_executor():
    service = MagicMock()
    registry = _registry_with(AcknowledgeOnboardingTaskTool(service))
    with pytest.raises(ToolValidationError):
        ToolExecutor(registry).execute(
            _employee(),
            "acknowledge_onboarding_task",
            {"task_id": 1, "employee_id": 42},
        )
    service.acknowledge_task_for_employee.assert_not_called()


def test_infer_target_keeps_leave_request_id_mapping():
    """_infer_target is generic field mapping — leave request_id must stay unchanged."""
    assert _infer_target("approve_leave_request", {"request_id": 42}) == (
        "leave_request",
        42,
    )
    assert _infer_target("acknowledge_onboarding_task", {"task_id": 7}) == (
        "onboarding_task",
        7,
    )
    assert _infer_target("complete_onboarding", {"onboarding_id": 3}) == (
        "onboarding",
        3,
    )


def test_ack_already_completed_surfaces_domain_error():
    service = MagicMock()
    service.acknowledge_task_for_employee.side_effect = AppException(
        "Task is already completed", status_code=400
    )
    registry = _registry_with(AcknowledgeOnboardingTaskTool(service))
    with pytest.raises(ToolExecutionError, match="already completed"):
        ToolExecutor(registry).execute(
            _employee(),
            "acknowledge_onboarding_task",
            {"task_id": 7},
            execute_writes=True,
        )


def test_complete_onboarding_already_completed_surfaces_domain_error():
    service = MagicMock()
    service.complete_for_hr.side_effect = AppException(
        "Onboarding is already completed", status_code=400
    )
    registry = _registry_with(CompleteOnboardingTool(service))
    with pytest.raises(ToolExecutionError, match="already completed"):
        ToolExecutor(registry).execute(
            _hr(),
            "complete_onboarding",
            {"onboarding_id": 3},
            execute_writes=True,
        )


def test_ack_completed_onboarding_surfaces_domain_error():
    service = MagicMock()
    service.acknowledge_task_for_employee.side_effect = AppException(
        "Cannot modify tasks on a completed onboarding", status_code=400
    )
    registry = _registry_with(AcknowledgeOnboardingTaskTool(service))
    with pytest.raises(ToolExecutionError, match="completed onboarding"):
        ToolExecutor(registry).execute(
            _employee(),
            "acknowledge_onboarding_task",
            {"task_id": 7},
            execute_writes=True,
        )
