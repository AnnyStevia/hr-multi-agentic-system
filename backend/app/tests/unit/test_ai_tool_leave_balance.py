"""Unit tests for get_my_leave_balance AI tool (mocked LeaveService)."""

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.ai.core.context import AIExecutionContext
from app.ai.tools import (
    GetMyLeaveBalanceTool,
    ToolAuthorizationError,
    ToolExecutor,
    ToolExecutionError,
    ToolRegistry,
    ToolValidationError,
    tool_to_definition,
)
from app.ai.tools.leave import GetMyLeaveBalanceInput
from app.modules.leave.schemas import LeaveBalanceResponse
from app.shared.exceptions import AppException


def _context(
    *,
    user_id: int = 10,
    employee_id: int | None = 55,
    permission_names: frozenset[str] | None = None,
) -> AIExecutionContext:
    return AIExecutionContext(
        user_id=user_id,
        role_names=frozenset({"employee"}),
        permission_names=(
            permission_names
            if permission_names is not None
            else frozenset({"leaves:read"})
        ),
        employee_id=employee_id,
        candidate_id=None,
    )


def _balance_row(*, employee_id: int = 55, year: int = 2026) -> LeaveBalanceResponse:
    return LeaveBalanceResponse(
        employee_id=employee_id,
        leave_type_id=1,
        leave_type_name="Annual Leave",
        year=year,
        days_allowed=20,
        days_used=5,
        days_pending=2,
        days_available=15,
    )


def test_valid_context_calls_leave_service_with_authenticated_employee_id():
    service = MagicMock()
    service.get_balances.return_value = [_balance_row(employee_id=55, year=2026)]
    tool = GetMyLeaveBalanceTool(service)
    registry = ToolRegistry()
    registry.register(tool)

    result = ToolExecutor(registry).execute(_context(employee_id=55), "get_my_leave_balance", {})

    service.get_balances.assert_called_once_with(55)
    assert result.success is True
    assert result.data == {
        "employee_id": 55,
        "year": 2026,
        "balances": [
            {
                "leave_type_id": 1,
                "leave_type_name": "Annual Leave",
                "days_allowed": 20,
                "days_used": 5,
                "days_pending": 2,
                "days_available": 15,
            }
        ],
    }


def test_missing_employee_id_rejects_without_calling_service():
    service = MagicMock()
    tool = GetMyLeaveBalanceTool(service)
    registry = ToolRegistry()
    registry.register(tool)

    with pytest.raises(ToolExecutionError, match="No employee profile"):
        ToolExecutor(registry).execute(
            _context(employee_id=None),
            "get_my_leave_balance",
            {},
        )

    service.get_balances.assert_not_called()


def test_input_schema_rejects_identity_arguments():
    assert "employee_id" not in GetMyLeaveBalanceInput.model_fields
    assert "user_id" not in GetMyLeaveBalanceInput.model_fields

    with pytest.raises(ValidationError):
        GetMyLeaveBalanceInput.model_validate({"employee_id": 99})

    service = MagicMock()
    registry = ToolRegistry()
    registry.register(GetMyLeaveBalanceTool(service))
    with pytest.raises(ToolValidationError):
        ToolExecutor(registry).execute(
            _context(employee_id=55),
            "get_my_leave_balance",
            {"employee_id": 99},
        )
    service.get_balances.assert_not_called()


def test_leave_service_app_exception_becomes_tool_execution_error():
    service = MagicMock()
    service.get_balances.side_effect = AppException("Employee not found", status_code=404)
    tool = GetMyLeaveBalanceTool(service)
    registry = ToolRegistry()
    registry.register(tool)

    with pytest.raises(ToolExecutionError, match="Employee not found"):
        ToolExecutor(registry).execute(_context(employee_id=55), "get_my_leave_balance", {})


def test_authorization_failure_does_not_call_leave_service():
    service = MagicMock()
    tool = GetMyLeaveBalanceTool(service)
    registry = ToolRegistry()
    registry.register(tool)

    with pytest.raises(ToolAuthorizationError, match="Not authorized"):
        ToolExecutor(registry).execute(
            _context(employee_id=55, permission_names=frozenset()),
            "get_my_leave_balance",
            {},
        )

    service.get_balances.assert_not_called()


def test_result_uses_context_employee_id_not_service_row_identity_spoof():
    """Even if service returned another employee_id in rows, tool output uses context."""
    service = MagicMock()
    service.get_balances.return_value = [_balance_row(employee_id=999, year=2026)]
    tool = GetMyLeaveBalanceTool(service)

    output = tool.execute(_context(employee_id=55), GetMyLeaveBalanceInput())
    assert output.employee_id == 55
    service.get_balances.assert_called_once_with(55)


def test_tool_to_definition_has_empty_object_parameters():
    definition = tool_to_definition(GetMyLeaveBalanceTool(MagicMock()))
    assert definition.name == "get_my_leave_balance"
    assert definition.parameters.get("type") == "object"
    assert definition.parameters.get("properties") == {}
