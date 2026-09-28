"""Unit tests for confirmation-gated Training write tools."""

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
from app.ai.tools.registry import ToolRegistry
from app.ai.tools.training_writes import (
    AssignTrainingToOnboardingInput,
    AssignTrainingToOnboardingTool,
    CompleteMyTrainingAssignmentInput,
    CompleteMyTrainingAssignmentTool,
)
from app.modules.training.models import OnboardingTrainingStatus
from app.modules.training.schemas import OnboardingTrainingAssignRequest
from app.shared.exceptions import AppException


def _employee() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=9,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"training:read"}),
        employee_id=99,
        candidate_id=None,
    )


def _hr() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=1,
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"training:read", "training:write"}),
        employee_id=10,
        candidate_id=None,
    )


def _hr_read_only() -> AIExecutionContext:
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
        permission_names=frozenset({"training:write"}),
        employee_id=20,
        candidate_id=None,
    )


def _manager() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=5,
        role_names=frozenset({"manager"}),
        permission_names=frozenset({"training:read"}),
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


def _assignment(
    *,
    assignment_id: int = 11,
    onboarding_id: int = 1,
    training_id: int = 5,
    status: OnboardingTrainingStatus = OnboardingTrainingStatus.COMPLETED,
):
    row = MagicMock()
    row.id = assignment_id
    row.onboarding_id = onboarding_id
    row.training_id = training_id
    row.status = status
    return row


def _registry_with(*tools) -> ToolRegistry:
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    return registry


def test_infer_target_training_assignment_id():
    assert _infer_target(
        "complete_my_training_assignment", {"training_assignment_id": 11}
    ) == ("onboarding_training", 11)
    assert _infer_target(
        "assign_training_to_onboarding", {"onboarding_id": 42, "training_id": 5}
    ) == ("onboarding", 42)


def test_employee_can_authorize_complete_not_assign():
    service = MagicMock()
    authorize_tool(
        CompleteMyTrainingAssignmentTool(service),
        _employee(),
        CompleteMyTrainingAssignmentInput(training_assignment_id=11),
    )
    with pytest.raises(ToolAuthorizationError):
        authorize_tool(
            AssignTrainingToOnboardingTool(service),
            _employee(),
            AssignTrainingToOnboardingInput(onboarding_id=1, training_id=5),
        )


def test_manager_can_authorize_own_complete_not_assign():
    service = MagicMock()
    authorize_tool(
        CompleteMyTrainingAssignmentTool(service),
        _manager(),
        CompleteMyTrainingAssignmentInput(training_assignment_id=11),
    )
    with pytest.raises(ToolAuthorizationError):
        authorize_tool(
            AssignTrainingToOnboardingTool(service),
            _manager(),
            AssignTrainingToOnboardingInput(onboarding_id=1, training_id=5),
        )


def test_candidate_denied_assign_and_complete_execute():
    service = MagicMock()
    with pytest.raises(ToolAuthorizationError):
        authorize_tool(
            AssignTrainingToOnboardingTool(service),
            _candidate(),
            AssignTrainingToOnboardingInput(onboarding_id=1, training_id=5),
        )
    authorize_tool(
        CompleteMyTrainingAssignmentTool(service),
        _candidate(),
        CompleteMyTrainingAssignmentInput(training_assignment_id=11),
    )
    registry = _registry_with(CompleteMyTrainingAssignmentTool(service))
    with pytest.raises(ToolExecutionError, match="No employee profile"):
        ToolExecutor(registry).execute(
            _candidate(),
            "complete_my_training_assignment",
            {"training_assignment_id": 11},
            execute_writes=True,
        )
    service.complete_assignment_for_user.assert_not_called()


def test_hr_and_admin_authorize_assign():
    service = MagicMock()
    for ctx in (_hr(), _admin()):
        authorize_tool(
            AssignTrainingToOnboardingTool(service),
            ctx,
            AssignTrainingToOnboardingInput(onboarding_id=1, training_id=5),
        )


def test_hr_without_training_write_denied():
    service = MagicMock()
    with pytest.raises(ToolAuthorizationError):
        authorize_tool(
            AssignTrainingToOnboardingTool(service),
            _hr_read_only(),
            AssignTrainingToOnboardingInput(onboarding_id=1, training_id=5),
        )


def test_complete_input_rejects_identity_fields():
    with pytest.raises(ValidationError):
        CompleteMyTrainingAssignmentInput.model_validate(
            {"training_assignment_id": 11, "employee_id": 42}
        )
    with pytest.raises(ValidationError):
        CompleteMyTrainingAssignmentInput.model_validate(
            {"training_assignment_id": 11, "user_id": 9}
        )
    with pytest.raises(ValidationError):
        CompleteMyTrainingAssignmentInput.model_validate(
            {"training_assignment_id": 11, "onboarding_id": 7}
        )


def test_assign_input_rejects_employee_id():
    with pytest.raises(ValidationError):
        AssignTrainingToOnboardingInput.model_validate(
            {"onboarding_id": 1, "training_id": 5, "employee_id": 99}
        )


def test_complete_pending_then_execute_uses_user_id():
    service = MagicMock()
    service.complete_assignment_for_user.return_value = _assignment()
    registry = _registry_with(CompleteMyTrainingAssignmentTool(service))
    args = {"training_assignment_id": 11}

    pending = ToolExecutor(registry).execute(
        _employee(), "complete_my_training_assignment", args
    )
    assert pending.confirmation_token
    assert pending.data["status"] == "pending_confirmation"
    service.complete_assignment_for_user.assert_not_called()

    done = ToolExecutor(registry).execute(
        _employee(), "complete_my_training_assignment", args, execute_writes=True
    )
    service.complete_assignment_for_user.assert_called_once_with(9, 11)
    assert done.data["training_assignment_id"] == 11
    assert done.data["status"] == "completed"


def test_manager_complete_own_pending_then_execute():
    service = MagicMock()
    service.complete_assignment_for_user.return_value = _assignment(assignment_id=3)
    registry = _registry_with(CompleteMyTrainingAssignmentTool(service))
    args = {"training_assignment_id": 3}
    pending = ToolExecutor(registry).execute(
        _manager(), "complete_my_training_assignment", args
    )
    assert pending.confirmation_token
    done = ToolExecutor(registry).execute(
        _manager(), "complete_my_training_assignment", args, execute_writes=True
    )
    service.complete_assignment_for_user.assert_called_once_with(5, 3)
    assert done.data["training_assignment_id"] == 3


def test_complete_foreign_assignment_surfaces_not_found():
    service = MagicMock()
    service.complete_assignment_for_user.side_effect = AppException(
        "Training assignment not found", status_code=404
    )
    registry = _registry_with(CompleteMyTrainingAssignmentTool(service))
    with pytest.raises(ToolExecutionError, match="not found"):
        ToolExecutor(registry).execute(
            _employee(),
            "complete_my_training_assignment",
            {"training_assignment_id": 99},
            execute_writes=True,
        )


def test_complete_rejects_identity_args_via_executor():
    service = MagicMock()
    registry = _registry_with(CompleteMyTrainingAssignmentTool(service))
    with pytest.raises(ToolValidationError):
        ToolExecutor(registry).execute(
            _employee(),
            "complete_my_training_assignment",
            {"training_assignment_id": 11, "employee_id": 42},
        )
    service.complete_assignment_for_user.assert_not_called()


def test_assign_pending_then_execute():
    service = MagicMock()
    service.assign_training.return_value = _assignment(
        assignment_id=20, onboarding_id=42, training_id=5, status=OnboardingTrainingStatus.PENDING
    )
    registry = _registry_with(AssignTrainingToOnboardingTool(service))
    args = {"onboarding_id": 42, "training_id": 5}

    pending = ToolExecutor(registry).execute(
        _hr(), "assign_training_to_onboarding", args
    )
    assert pending.confirmation_token
    service.assign_training.assert_not_called()

    done = ToolExecutor(registry).execute(
        _hr(), "assign_training_to_onboarding", args, execute_writes=True
    )
    service.assign_training.assert_called_once()
    call_args = service.assign_training.call_args
    assert call_args[0][0] == 42
    assert isinstance(call_args[0][1], OnboardingTrainingAssignRequest)
    assert call_args[0][1].training_id == 5
    assert done.data["assignment_id"] == 20
    assert done.data["status"] == "pending"


def test_assign_duplicate_surfaces_conflict():
    service = MagicMock()
    service.assign_training.side_effect = AppException(
        "Training is already assigned to this onboarding", status_code=409
    )
    registry = _registry_with(AssignTrainingToOnboardingTool(service))
    with pytest.raises(ToolExecutionError, match="already assigned"):
        ToolExecutor(registry).execute(
            _hr(),
            "assign_training_to_onboarding",
            {"onboarding_id": 42, "training_id": 5},
            execute_writes=True,
        )


def test_employee_assign_authorize_fails_before_service():
    service = MagicMock()
    registry = _registry_with(AssignTrainingToOnboardingTool(service))
    with pytest.raises(ToolAuthorizationError):
        ToolExecutor(registry).execute(
            _employee(),
            "assign_training_to_onboarding",
            {"onboarding_id": 42, "training_id": 5},
        )
    service.assign_training.assert_not_called()


def test_hr_can_authorize_own_complete():
    service = MagicMock()
    authorize_tool(
        CompleteMyTrainingAssignmentTool(service),
        _hr(),
        CompleteMyTrainingAssignmentInput(training_assignment_id=11),
    )
