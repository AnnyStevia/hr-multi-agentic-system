"""Unit tests for self + manager scoped leave tools."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import MagicMock

import pytest

from app.ai.core.context import AIExecutionContext
from app.ai.tools import (
    FindDirectReportsTool,
    GetDirectReportLeaveBalanceTool,
    GetLeaveBalanceTool,
    GetMyLeaveBalanceTool,
    GetMyLeaveRequestTool,
    GetMyWorkStatusTool,
    GetTeamLeaveRequestTool,
    ListMyLeaveRequestsTool,
    ListTeamCurrentlyOnLeaveTool,
    ListTeamPendingLeaveRequestsTool,
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
from app.modules.leave.schemas import (
    CurrentLeaveSummary,
    CurrentWorkStatus,
    CurrentWorkStatusPayload,
    LeaveBalanceResponse,
)
from app.shared.exceptions import AppException


def _employee_ctx(*, user_id: int = 10, employee_id: int = 55) -> AIExecutionContext:
    return AIExecutionContext(
        user_id=user_id,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"leaves:read"}),
        employee_id=employee_id,
        candidate_id=None,
    )


def _hr_ctx() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=1,
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"leaves:read", "recruitment:read"}),
        employee_id=10,
        candidate_id=None,
    )


def _request_mock(*, request_id: int = 7, employee_id: int = 3):
    now = datetime.now(UTC)
    req = MagicMock()
    req.id = request_id
    req.employee_id = employee_id
    req.employee.first_name = "Sara"
    req.employee.last_name = "Chen"
    req.leave_type_id = 1
    req.leave_type.name = "Annual"
    req.start_date = date(2026, 6, 1)
    req.end_date = date(2026, 6, 5)
    req.requested_days = 5
    req.reason = "Vacation"
    req.rejection_reason = None
    req.status = LeaveRequestStatus.PENDING
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
    req.cancellation_status = LeaveCancellationStatus.NONE
    req.cancellation_requested_at = None
    req.cancellation_requested_by = None
    req.cancellation_reason = None
    req.cancellation_processed_at = None
    req.cancellation_processed_by = None
    req.cancellation_rejection_reason = None
    req.created_at = now
    req.updated_at = now
    return req


# --- SELF ---


def test_self_balance_and_requests():
    service = MagicMock()
    service.get_balances.return_value = [
        LeaveBalanceResponse(
            employee_id=55,
            leave_type_id=1,
            leave_type_name="Annual",
            year=2026,
            days_allowed=20,
            days_used=5,
            days_pending=1,
            days_available=15,
        )
    ]
    req = _request_mock(request_id=9, employee_id=55)
    service.list_requests_for_user.return_value = [req]
    service.get_request_for_user.return_value = req
    service.get_current_work_status.return_value = CurrentWorkStatusPayload(
        current_work_status=CurrentWorkStatus.ACTIVE,
        current_leave=None,
    )
    registry = ToolRegistry()
    registry.register(GetMyLeaveBalanceTool(service))
    registry.register(ListMyLeaveRequestsTool(service))
    registry.register(GetMyLeaveRequestTool(service))
    registry.register(GetMyWorkStatusTool(service))
    ctx = _employee_ctx()

    bal = ToolExecutor(registry).execute(ctx, "get_my_leave_balance", {})
    assert bal.data["balances"][0]["days_available"] == 15

    listed = ToolExecutor(registry).execute(ctx, "list_my_leave_requests", {})
    assert listed.data["count"] == 1

    one = ToolExecutor(registry).execute(
        ctx, "get_my_leave_request", {"request_id": 9}
    )
    assert one.data["request"]["request_id"] == 9

    status = ToolExecutor(registry).execute(ctx, "get_my_work_status", {})
    assert status.data["current_work_status"] == "ACTIVE"


def test_employee_cannot_use_hr_org_wide_balance_tool():
    service = MagicMock()
    registry = ToolRegistry()
    registry.register(GetLeaveBalanceTool(service))
    with pytest.raises(ToolAuthorizationError):
        ToolExecutor(registry).execute(
            _employee_ctx(), "get_leave_balance", {"employee_id": 3}
        )
    service.get_balances.assert_not_called()


# --- MANAGER ---


def test_manager_direct_report_balance_and_deny_unrelated():
    service = MagicMock()
    service.get_balances_for_direct_report.return_value = [
        LeaveBalanceResponse(
            employee_id=3,
            leave_type_id=1,
            leave_type_name="Annual",
            year=2026,
            days_allowed=20,
            days_used=2,
            days_pending=0,
            days_available=18,
        )
    ]
    registry = ToolRegistry()
    registry.register(GetDirectReportLeaveBalanceTool(service))
    registry.register(GetMyLeaveBalanceTool(service))
    mgr = _employee_ctx(user_id=20, employee_id=100)

    ok = ToolExecutor(registry).execute(
        mgr, "get_direct_report_leave_balance", {"employee_id": 3}
    )
    service.get_balances_for_direct_report.assert_called_once_with(20, 3, year=None)
    assert ok.data["balances"][0]["days_available"] == 18

    # Same manager can also read own balance
    service.get_balances.return_value = [
        LeaveBalanceResponse(
            employee_id=100,
            leave_type_id=1,
            leave_type_name="Annual",
            year=2026,
            days_allowed=20,
            days_used=0,
            days_pending=0,
            days_available=20,
        )
    ]
    own = ToolExecutor(registry).execute(mgr, "get_my_leave_balance", {})
    assert own.data["employee_id"] == 100

    service.get_balances_for_direct_report.side_effect = AppException(
        "Employee not found", status_code=404
    )
    with pytest.raises(ToolExecutionError, match="not found"):
        ToolExecutor(registry).execute(
            mgr, "get_direct_report_leave_balance", {"employee_id": 999}
        )


def test_manager_team_pending_and_on_leave():
    service = MagicMock()
    req = _request_mock()
    service.list_team_requests_for_user.return_value = [req]
    covering = _request_mock(request_id=11, employee_id=3)
    covering.status = LeaveRequestStatus.APPROVED
    service.list_currently_on_leave_for_team.return_value = [covering]
    service.get_request_for_team_member.return_value = req

    registry = ToolRegistry()
    registry.register(ListTeamPendingLeaveRequestsTool(service))
    registry.register(ListTeamCurrentlyOnLeaveTool(service))
    registry.register(GetTeamLeaveRequestTool(service))
    mgr = _employee_ctx(user_id=20, employee_id=100)

    pending = ToolExecutor(registry).execute(
        mgr, "list_team_pending_leave_requests", {}
    )
    assert pending.data["count"] == 1

    on_leave = ToolExecutor(registry).execute(
        mgr, "list_team_currently_on_leave", {"as_of": "2026-06-03"}
    )
    assert on_leave.data["count"] == 1

    one = ToolExecutor(registry).execute(
        mgr, "get_team_leave_request", {"request_id": 7}
    )
    assert one.data["request"]["employee_id"] == 3


def test_find_direct_reports_ambiguity_and_not_found():
    service = MagicMock()
    a = MagicMock()
    a.id = 3
    a.first_name = "Sara"
    a.last_name = "A"
    a.email = "a@test.com"
    b = MagicMock()
    b.id = 4
    b.first_name = "Sara"
    b.last_name = "B"
    b.email = "b@test.com"
    service.list_direct_reports_for_user.return_value = [a, b]
    registry = ToolRegistry()
    registry.register(FindDirectReportsTool(service))
    mgr = _employee_ctx(user_id=20, employee_id=100)

    multi = ToolExecutor(registry).execute(
        mgr, "find_direct_reports", {"q": "Sara"}
    )
    assert multi.data["count"] == 2
    assert "Multiple" in (multi.data["message"] or "")

    service.list_direct_reports_for_user.return_value = []
    empty = ToolExecutor(registry).execute(
        mgr, "find_direct_reports", {"q": "Nobody"}
    )
    assert empty.data["count"] == 0
    assert empty.data["message"]


def test_hr_still_can_use_org_wide_tools():
    service = MagicMock()
    service.get_balances.return_value = []
    registry = ToolRegistry()
    registry.register(GetLeaveBalanceTool(service))
    out = ToolExecutor(registry).execute(
        _hr_ctx(), "get_leave_balance", {"employee_id": 3, "year": 2026}
    )
    assert out.success is True
