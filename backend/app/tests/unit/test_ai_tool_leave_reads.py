"""Unit tests for HR leave read tools (mocked LeaveService)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import MagicMock

import pytest

from app.ai.core.context import AIExecutionContext
from app.ai.tools import (
    GetLeaveBalanceTool,
    GetLeavePolicyTool,
    GetLeaveRequestTool,
    ListCurrentlyOnLeaveTool,
    ListLeaveRequestsTool,
    ListLeaveTypesTool,
    ListPendingLeaveRequestsTool,
    ToolAuthorizationError,
    ToolExecutor,
    ToolExecutionError,
    ToolRegistry,
)
from app.modules.leave.models import (
    LeaveApprovalStatus,
    LeaveCancellationStatus,
    LeaveRequestStatus,
)
from app.modules.leave.schemas import LeaveBalanceResponse
from app.shared.exceptions import AppException


def _hr() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=1,
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"leaves:read", "recruitment:read"}),
        employee_id=10,
        candidate_id=None,
    )


def _employee_with_leaves_read() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=9,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"leaves:read", "employees:read"}),
        employee_id=99,
        candidate_id=None,
    )


def _request_mock(
    *,
    request_id: int = 7,
    status=LeaveRequestStatus.PENDING,
    cancellation_status=LeaveCancellationStatus.NONE,
):
    now = datetime.now(UTC)
    req = MagicMock()
    req.id = request_id
    req.employee_id = 3
    req.employee.first_name = "Ada"
    req.employee.last_name = "Lovelace"
    req.leave_type_id = 1
    req.leave_type.name = "Annual"
    req.start_date = date(2026, 6, 1)
    req.end_date = date(2026, 6, 5)
    req.requested_days = 5
    req.reason = "Vacation"
    req.rejection_reason = None
    req.status = status
    req.approved_at = None
    req.rejected_at = None
    req.reviewed_by = None
    req.manager_approval = LeaveApprovalStatus.PENDING
    req.manager_approved_by = None
    req.manager_approved_at = None
    req.hr_approval = LeaveApprovalStatus.PENDING
    req.hr_approved_by = None
    req.hr_approved_at = None
    req.admin_override = LeaveApprovalStatus.PENDING
    req.admin_approved_by = None
    req.admin_approved_at = None
    req.cancellation_status = cancellation_status
    req.cancellation_requested_at = None
    req.cancellation_requested_by = None
    req.cancellation_reason = None
    req.cancellation_processed_at = None
    req.cancellation_processed_by = None
    req.cancellation_rejection_reason = None
    req.created_at = now
    req.updated_at = now
    return req


def _balance_row(**kwargs) -> LeaveBalanceResponse:
    base = dict(
        employee_id=3,
        leave_type_id=1,
        leave_type_name="Annual",
        year=2026,
        days_allowed=20,
        days_used=5,
        days_pending=2,
        days_available=15,
    )
    base.update(kwargs)
    return LeaveBalanceResponse(**base)


# --- A. Balance ---


def test_get_leave_balance_echoes_service_values():
    service = MagicMock()
    service.get_balances.return_value = [_balance_row()]
    registry = ToolRegistry()
    registry.register(GetLeaveBalanceTool(service))
    out = ToolExecutor(registry).execute(
        _hr(), "get_leave_balance", {"employee_id": 3, "year": 2026}
    )
    service.get_balances.assert_called_once_with(3, year=2026)
    bal = out.data["balances"][0]
    assert bal["days_allowed"] == 20
    assert bal["days_used"] == 5
    assert bal["days_pending"] == 2
    assert bal["days_available"] == 15
    assert "pending" in out.data["note"].lower()


def test_get_leave_balance_empty_for_year_without_policies():
    service = MagicMock()
    service.get_balances.return_value = []
    registry = ToolRegistry()
    registry.register(GetLeaveBalanceTool(service))
    out = ToolExecutor(registry).execute(
        _hr(), "get_leave_balance", {"employee_id": 3, "year": 2020}
    )
    assert out.data["balances"] == []
    assert out.data["year"] == 2020


def test_get_leave_balance_rejects_out_of_range_year():
    from app.ai.tools import ToolValidationError

    service = MagicMock()
    registry = ToolRegistry()
    registry.register(GetLeaveBalanceTool(service))
    with pytest.raises(ToolValidationError):
        ToolExecutor(registry).execute(
            _hr(), "get_leave_balance", {"employee_id": 3, "year": 1999}
        )
    service.get_balances.assert_not_called()


# --- B. Requests ---


def test_get_leave_request_and_list_pending():
    service = MagicMock()
    req = _request_mock()
    service.get_request_for_hr.return_value = req
    service.list_requests_for_hr.return_value = [req]
    registry = ToolRegistry()
    registry.register(GetLeaveRequestTool(service))
    registry.register(ListPendingLeaveRequestsTool(service))
    registry.register(ListLeaveRequestsTool(service))

    one = ToolExecutor(registry).execute(_hr(), "get_leave_request", {"request_id": 7})
    assert one.data["request"]["request_id"] == 7
    assert one.data["request"]["status"] == "pending"
    assert one.data["request"]["status"] != "approved"

    pending = ToolExecutor(registry).execute(
        _hr(), "list_pending_leave_requests", {"limit": 10}
    )
    service.list_requests_for_hr.assert_called_with(status=LeaveRequestStatus.PENDING)
    assert pending.data["count"] == 1

    listed = ToolExecutor(registry).execute(
        _hr(),
        "list_leave_requests",
        {
            "employee_id": 3,
            "status": "approved",
            "overlaps_start": "2026-06-01",
            "overlaps_end": "2026-06-30",
            "limit": 5,
        },
    )
    assert listed.success is True
    service.list_requests_for_hr.assert_called_with(
        employee_id=3,
        leave_type_id=None,
        status=LeaveRequestStatus.APPROVED,
        cancellation_status=None,
        overlaps_start=date(2026, 6, 1),
        overlaps_end=date(2026, 6, 30),
    )


# --- C. Currently on leave ---


def test_list_currently_on_leave_with_items_and_empty():
    service = MagicMock()
    covering = _request_mock(
        request_id=9,
        status=LeaveRequestStatus.APPROVED,
        cancellation_status=LeaveCancellationStatus.REQUESTED,
    )
    service.list_currently_on_leave.return_value = [covering]
    registry = ToolRegistry()
    registry.register(ListCurrentlyOnLeaveTool(service))

    on_leave = ToolExecutor(registry).execute(
        _hr(), "list_currently_on_leave", {"as_of": "2026-06-03"}
    )
    assert on_leave.data["count"] == 1
    assert on_leave.data["items"][0]["employee_id"] == 3
    assert on_leave.data["items"][0]["cancellation_status"] == "requested"

    service.list_currently_on_leave.return_value = []
    empty = ToolExecutor(registry).execute(_hr(), "list_currently_on_leave", {})
    assert empty.data["count"] == 0
    assert empty.data["items"] == []


# --- D. Policy ---


def test_get_leave_policy_by_id_type_and_name():
    service = MagicMock()
    now = datetime.now(UTC)
    policy = MagicMock()
    policy.id = 2
    policy.leave_type_id = 1
    policy.leave_type.name = "Annual"
    policy.year = 2026
    policy.days_allowed = 20
    policy.created_at = now
    policy.updated_at = now
    leave_type = MagicMock()
    leave_type.id = 1
    leave_type.name = "Annual"
    leave_type.is_paid = True
    service.get_policy.return_value = policy
    service.get_policy_for_type_year.return_value = policy
    service.get_type_by_name.return_value = leave_type
    service.list_types.return_value = [leave_type]

    registry = ToolRegistry()
    registry.register(GetLeavePolicyTool(service))
    registry.register(ListLeaveTypesTool(service))

    by_id = ToolExecutor(registry).execute(_hr(), "get_leave_policy", {"policy_id": 2})
    assert by_id.data["days_allowed"] == 20

    by_type = ToolExecutor(registry).execute(
        _hr(), "get_leave_policy", {"leave_type_id": 1, "year": 2026}
    )
    service.get_policy_for_type_year.assert_called_with(1, 2026)
    assert by_type.data["policy_id"] == 2

    by_name = ToolExecutor(registry).execute(
        _hr(), "get_leave_policy", {"leave_type_name": "Annual", "year": 2026}
    )
    service.get_type_by_name.assert_called_once_with("Annual")
    assert by_name.data["leave_type_name"] == "Annual"

    types = ToolExecutor(registry).execute(_hr(), "list_leave_types", {})
    assert types.data["count"] == 1


def test_get_leave_policy_missing():
    service = MagicMock()
    service.get_policy.side_effect = AppException("Leave policy not found", status_code=404)
    registry = ToolRegistry()
    registry.register(GetLeavePolicyTool(service))
    with pytest.raises(ToolExecutionError, match="not found"):
        ToolExecutor(registry).execute(_hr(), "get_leave_policy", {"policy_id": 99})


# --- F. Security ---


def test_leave_read_tools_require_hr_role_not_just_permission():
    service = MagicMock()
    registry = ToolRegistry()
    registry.register(GetLeaveBalanceTool(service))
    with pytest.raises(ToolAuthorizationError):
        ToolExecutor(registry).execute(
            _employee_with_leaves_read(),
            "get_leave_balance",
            {"employee_id": 1},
        )
    service.get_balances.assert_not_called()


def test_employee_can_list_leave_types():
    service = MagicMock()
    lt = MagicMock()
    lt.id = 1
    lt.name = "Annual"
    lt.is_paid = True
    service.list_types.return_value = [lt]
    registry = ToolRegistry()
    registry.register(ListLeaveTypesTool(service))
    out = ToolExecutor(registry).execute(
        _employee_with_leaves_read(), "list_leave_types", {}
    )
    assert out.data["count"] == 1
    assert out.data["leave_types"][0]["leave_type_id"] == 1
    service.list_types.assert_called_once()


def test_candidate_cannot_invoke_leave_tools():
    registry = ToolRegistry()
    registry.register(GetLeaveBalanceTool(MagicMock()))
    with pytest.raises(ToolAuthorizationError):
        ToolExecutor(registry).execute(
            AIExecutionContext(
                user_id=9,
                role_names=frozenset({"candidate"}),
                permission_names=frozenset(),
                employee_id=None,
                candidate_id=1,
            ),
            "get_leave_balance",
            {"employee_id": 1},
        )


def test_leave_service_error_mapped():
    service = MagicMock()
    service.get_request_for_hr.side_effect = AppException(
        "Leave request not found", status_code=404
    )
    registry = ToolRegistry()
    registry.register(GetLeaveRequestTool(service))
    with pytest.raises(ToolExecutionError, match="not found"):
        ToolExecutor(registry).execute(_hr(), "get_leave_request", {"request_id": 99})


# --- H. Status semantics ---


def test_pending_not_reported_as_approved_in_summary():
    service = MagicMock()
    service.get_request_for_hr.return_value = _request_mock(status=LeaveRequestStatus.PENDING)
    registry = ToolRegistry()
    registry.register(GetLeaveRequestTool(service))
    out = ToolExecutor(registry).execute(_hr(), "get_leave_request", {"request_id": 1})
    assert out.data["request"]["status"] == "pending"
    assert out.data["request"]["cancellation_status"] == "none"


def test_cancellation_requested_not_cancelled_in_summary():
    service = MagicMock()
    service.get_request_for_hr.return_value = _request_mock(
        status=LeaveRequestStatus.APPROVED,
        cancellation_status=LeaveCancellationStatus.REQUESTED,
    )
    registry = ToolRegistry()
    registry.register(GetLeaveRequestTool(service))
    out = ToolExecutor(registry).execute(_hr(), "get_leave_request", {"request_id": 1})
    assert out.data["request"]["status"] == "approved"
    assert out.data["request"]["cancellation_status"] == "requested"
    assert out.data["request"]["cancellation_status"] != "cancelled"
