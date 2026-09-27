"""Unit tests for confirmation-gated Leave write tools."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from app.ai.core.context import AIExecutionContext
from app.ai.tools import (
    ApproveLeaveCancellationTool,
    ApproveLeaveRequestTool,
    CancelPendingLeaveRequestTool,
    CreateLeaveRequestTool,
    RejectLeaveCancellationTool,
    RejectLeaveRequestTool,
    RequestLeaveCancellationTool,
    ToolAuthorizationError,
    ToolExecutor,
    ToolExecutionError,
    ToolRegistry,
)
from app.ai.tools.executor import _infer_target
from app.modules.leave.models import (
    LeaveApprovalStatus,
    LeaveCancellationStatus,
    LeaveRequestStatus,
)
from app.modules.leave.schemas import LeaveRequestCreateRequest
from app.shared.exceptions import AppException


def _ctx(**overrides) -> AIExecutionContext:
    data = dict(
        user_id=10,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"leaves:read", "leaves:write"}),
        employee_id=100,
        candidate_id=None,
    )
    data.update(overrides)
    return AIExecutionContext(**data)


def _mock_request(**overrides):
    req = MagicMock()
    req.id = overrides.get("id", 1)
    req.employee_id = overrides.get("employee_id", 100)
    req.leave_type_id = overrides.get("leave_type_id", 5)
    req.leave_type = MagicMock()
    req.leave_type.name = overrides.get("leave_type_name", "Annual")
    req.start_date = overrides.get("start_date", date(2026, 10, 5))
    req.end_date = overrides.get("end_date", date(2026, 10, 9))
    req.requested_days = overrides.get("requested_days", 5)
    req.status = overrides.get("status", LeaveRequestStatus.PENDING)
    req.cancellation_status = overrides.get(
        "cancellation_status", LeaveCancellationStatus.NONE
    )
    req.manager_approval = overrides.get(
        "manager_approval", LeaveApprovalStatus.PENDING
    )
    req.hr_approval = overrides.get("hr_approval", LeaveApprovalStatus.PENDING)
    return req


def _registry_with(*tools) -> ToolRegistry:
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    return registry


def test_infer_target_request_id():
    assert _infer_target("approve_leave_request", {"request_id": 42}) == (
        "leave_request",
        42,
    )


def test_create_leave_request_pending_then_execute():
    leave_service = MagicMock()
    leave_service.create_request_for_user.return_value = _mock_request(id=77)
    tool = CreateLeaveRequestTool(leave_service)
    registry = _registry_with(tool)
    args = {
        "leave_type_id": 5,
        "start_date": "2026-10-05",
        "end_date": "2026-10-09",
        "reason": "Vacation",
    }
    pending = ToolExecutor(registry).execute(_ctx(), "create_leave_request", args)
    assert pending.confirmation_token
    assert pending.data["status"] == "pending_confirmation"
    leave_service.create_request_for_user.assert_not_called()

    done = ToolExecutor(registry).execute(
        _ctx(), "create_leave_request", args, execute_writes=True
    )
    assert done.data["request_id"] == 77
    assert done.data["status"] == "pending"
    leave_service.create_request_for_user.assert_called_once()
    call_args = leave_service.create_request_for_user.call_args
    assert call_args.args[0] == 10  # authenticated user_id
    assert isinstance(call_args.args[1], LeaveRequestCreateRequest)
    assert call_args.args[1].leave_type_id == 5


def test_create_leave_request_resolves_type_name():
    leave_service = MagicMock()
    leave_type = MagicMock()
    leave_type.id = 5
    leave_service.get_type_by_name.return_value = leave_type
    leave_service.create_request_for_user.return_value = _mock_request(id=88)
    registry = _registry_with(CreateLeaveRequestTool(leave_service))
    done = ToolExecutor(registry).execute(
        _ctx(),
        "create_leave_request",
        {
            "leave_type_name": "Annual Leave",
            "start_date": "2026-10-05",
            "end_date": "2026-10-09",
        },
        execute_writes=True,
    )
    assert done.data["request_id"] == 88
    leave_service.get_type_by_name.assert_called_once_with("Annual Leave")
    assert leave_service.create_request_for_user.call_args.args[1].leave_type_id == 5


def test_create_leave_request_rejects_employee_id_field():
    registry = _registry_with(CreateLeaveRequestTool(MagicMock()))
    with pytest.raises(Exception):
        ToolExecutor(registry).execute(
            _ctx(),
            "create_leave_request",
            {
                "leave_type_id": 5,
                "start_date": "2026-10-05",
                "end_date": "2026-10-09",
                "employee_id": 999,
            },
            execute_writes=True,
        )


def test_create_sanitizes_service_error():
    leave_service = MagicMock()
    leave_service.create_request_for_user.side_effect = AppException(
        "Insufficient leave balance", status_code=400
    )
    registry = _registry_with(CreateLeaveRequestTool(leave_service))
    with pytest.raises(ToolExecutionError, match="Insufficient leave balance"):
        ToolExecutor(registry).execute(
            _ctx(),
            "create_leave_request",
            {
                "leave_type_id": 5,
                "start_date": "2026-10-05",
                "end_date": "2026-10-09",
            },
            execute_writes=True,
        )


def test_approve_pending_then_execute():
    leave_service = MagicMock()
    leave_service.approve_request.return_value = _mock_request(
        id=3, status=LeaveRequestStatus.APPROVED
    )
    registry = _registry_with(ApproveLeaveRequestTool(leave_service))
    pending = ToolExecutor(registry).execute(
        _ctx(role_names=frozenset({"hr"})),
        "approve_leave_request",
        {"request_id": 3},
    )
    assert pending.confirmation_token
    leave_service.approve_request.assert_not_called()
    done = ToolExecutor(registry).execute(
        _ctx(role_names=frozenset({"hr"})),
        "approve_leave_request",
        {"request_id": 3},
        execute_writes=True,
    )
    assert done.data["status"] == "approved"
    leave_service.approve_request.assert_called_once_with(3, 10)


def test_reject_pending_then_execute():
    leave_service = MagicMock()
    leave_service.reject_request.return_value = _mock_request(
        id=4, status=LeaveRequestStatus.REJECTED
    )
    registry = _registry_with(RejectLeaveRequestTool(leave_service))
    args = {"request_id": 4, "rejection_reason": "Coverage gap"}
    assert ToolExecutor(registry).execute(
        _ctx(), "reject_leave_request", args
    ).confirmation_token
    leave_service.reject_request.assert_not_called()
    done = ToolExecutor(registry).execute(
        _ctx(), "reject_leave_request", args, execute_writes=True
    )
    assert done.data["status"] == "rejected"
    leave_service.reject_request.assert_called_once_with(4, 10, "Coverage gap")


def test_cancel_pending_then_execute():
    leave_service = MagicMock()
    leave_service.cancel_request_for_user.return_value = _mock_request(
        id=5, status=LeaveRequestStatus.CANCELLED
    )
    registry = _registry_with(CancelPendingLeaveRequestTool(leave_service))
    pending = ToolExecutor(registry).execute(
        _ctx(), "cancel_pending_leave_request", {"request_id": 5}
    )
    assert pending.confirmation_token
    leave_service.cancel_request_for_user.assert_not_called()
    done = ToolExecutor(registry).execute(
        _ctx(),
        "cancel_pending_leave_request",
        {"request_id": 5},
        execute_writes=True,
    )
    assert done.data["status"] == "cancelled"
    leave_service.cancel_request_for_user.assert_called_once_with(10, 5)


def test_request_cancellation_pending_then_execute():
    leave_service = MagicMock()
    leave_service.request_cancellation_for_user.return_value = _mock_request(
        id=6,
        status=LeaveRequestStatus.APPROVED,
        cancellation_status=LeaveCancellationStatus.REQUESTED,
    )
    registry = _registry_with(RequestLeaveCancellationTool(leave_service))
    args = {"request_id": 6, "reason": "Plans changed"}
    assert ToolExecutor(registry).execute(
        _ctx(), "request_leave_cancellation", args
    ).confirmation_token
    leave_service.request_cancellation_for_user.assert_not_called()
    done = ToolExecutor(registry).execute(
        _ctx(), "request_leave_cancellation", args, execute_writes=True
    )
    assert done.data["cancellation_status"] == "requested"
    leave_service.request_cancellation_for_user.assert_called_once_with(
        10, 6, "Plans changed"
    )


def test_approve_cancellation_pending_then_execute():
    leave_service = MagicMock()
    leave_service.approve_cancellation.return_value = _mock_request(
        id=7, status=LeaveRequestStatus.CANCELLED
    )
    registry = _registry_with(ApproveLeaveCancellationTool(leave_service))
    assert ToolExecutor(registry).execute(
        _ctx(), "approve_leave_cancellation", {"request_id": 7}
    ).confirmation_token
    leave_service.approve_cancellation.assert_not_called()
    done = ToolExecutor(registry).execute(
        _ctx(),
        "approve_leave_cancellation",
        {"request_id": 7},
        execute_writes=True,
    )
    assert done.data["status"] == "cancelled"
    leave_service.approve_cancellation.assert_called_once_with(7, 10)


def test_reject_cancellation_pending_then_execute():
    leave_service = MagicMock()
    leave_service.reject_cancellation.return_value = _mock_request(
        id=8,
        status=LeaveRequestStatus.APPROVED,
        cancellation_status=LeaveCancellationStatus.REJECTED,
    )
    registry = _registry_with(RejectLeaveCancellationTool(leave_service))
    args = {"request_id": 8, "rejection_reason": "Too late"}
    assert ToolExecutor(registry).execute(
        _ctx(), "reject_leave_cancellation", args
    ).confirmation_token
    leave_service.reject_cancellation.assert_not_called()
    done = ToolExecutor(registry).execute(
        _ctx(), "reject_leave_cancellation", args, execute_writes=True
    )
    assert done.data["cancellation_status"] == "rejected"
    leave_service.reject_cancellation.assert_called_once_with(8, 10, "Too late")


def test_write_tools_require_leaves_write():
    registry = _registry_with(ApproveLeaveRequestTool(MagicMock()))
    with pytest.raises(ToolAuthorizationError):
        ToolExecutor(registry).execute(
            _ctx(permission_names=frozenset({"leaves:read"})),
            "approve_leave_request",
            {"request_id": 1},
        )


def test_candidate_cannot_write():
    registry = _registry_with(CreateLeaveRequestTool(MagicMock()))
    with pytest.raises(ToolAuthorizationError):
        ToolExecutor(registry).execute(
            AIExecutionContext(
                user_id=9,
                role_names=frozenset({"candidate"}),
                permission_names=frozenset(),
                employee_id=None,
                candidate_id=3,
            ),
            "create_leave_request",
            {
                "leave_type_id": 1,
                "start_date": "2026-10-05",
                "end_date": "2026-10-06",
            },
        )
