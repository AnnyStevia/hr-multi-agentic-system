"""Integration: Leave Agent write tools + confirm endpoint (real LeaveService)."""

from __future__ import annotations

import base64
import json
import time
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.ai.agents.leave import LeaveAgent, LeaveAgentValidationError
from app.ai.agents.leave.schemas import LeaveAgentAnswer, PendingConfirmationInfo
from app.ai.confirmation import create_confirmation_token
from app.ai.core.context import AIExecutionContext
from app.ai.tools import (
    ApproveLeaveCancellationTool,
    ApproveLeaveRequestTool,
    CancelPendingLeaveRequestTool,
    CreateLeaveRequestTool,
    RejectLeaveRequestTool,
    RequestLeaveCancellationTool,
    ToolExecutor,
    ToolExecutionError,
    ToolRegistry,
)
from app.api.v1 import ai_leave
from app.modules.leave.dependencies import get_leave_service
from app.tests.helpers import auth_header, create_department, create_user_with_role
from app.tests.integration.test_organization import _create_linked_employee

CURRENT_YEAR = date.today().year


def _create_type(client, headers, *, name: str = "Annual Leave AIW"):
    response = client.post(
        "/api/v1/leave/types",
        json={"name": name, "description": "AI write tests", "is_paid": True},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_policy(client, headers, *, leave_type_id: int, days: int = 20):
    response = client.post(
        "/api/v1/leave/policies",
        json={
            "leave_type_id": leave_type_id,
            "year": CURRENT_YEAR,
            "days_allowed": days,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _emp_ctx(user_id: int, employee_id: int) -> AIExecutionContext:
    return AIExecutionContext(
        user_id=user_id,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"leaves:read", "leaves:write"}),
        employee_id=employee_id,
        candidate_id=None,
    )


def test_confirm_endpoint_requires_auth(client):
    response = client.post(
        "/api/v1/ai/leave/confirm",
        json={"confirmation_token": "x" * 20},
    )
    assert response.status_code == 401


def test_confirm_endpoint_happy_path(client, db_session):
    create_user_with_role(
        db_session,
        email="emp.leave.confirm@test.com",
        password="pass12345",
        role_name="employee",
    )
    headers = auth_header(
        client, email="emp.leave.confirm@test.com", password="pass12345"
    )
    mock_agent = MagicMock()
    mock_agent.confirm.return_value = LeaveAgentAnswer(
        answer="Confirmed and completed: create_leave_request.",
        model="confirmed-action",
        tool_names_called=["create_leave_request"],
        usage=None,
        pending_confirmation=None,
    )
    client.app.dependency_overrides[ai_leave.get_leave_agent] = lambda: mock_agent
    try:
        response = client.post(
            "/api/v1/ai/leave/confirm",
            json={"confirmation_token": "valid-token-value-here"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_leave.get_leave_agent, None)
    assert response.status_code == 200, response.text
    assert response.json()["tool_names_called"] == ["create_leave_request"]
    assert response.json()["pending_confirmation"] is None


def test_ask_response_can_include_pending_confirmation(client, db_session):
    create_user_with_role(
        db_session,
        email="emp.leave.pending@test.com",
        password="pass12345",
        role_name="employee",
    )
    headers = auth_header(
        client, email="emp.leave.pending@test.com", password="pass12345"
    )
    mock_agent = MagicMock()
    mock_agent.ask.return_value = LeaveAgentAnswer(
        answer="Please confirm.",
        model="mock",
        tool_names_called=["create_leave_request"],
        usage=None,
        pending_confirmation=PendingConfirmationInfo(
            token="tok1234567890",
            tool_name="create_leave_request",
            summary="Proposed create",
            expires_at=int(time.time()) + 300,
        ),
    )
    client.app.dependency_overrides[ai_leave.get_leave_agent] = lambda: mock_agent
    try:
        response = client.post(
            "/api/v1/ai/leave/ask",
            json={"question": "Request leave"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_leave.get_leave_agent, None)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pending_confirmation"]["tool_name"] == "create_leave_request"
    assert body["pending_confirmation"]["token"] == "tok1234567890"


def test_create_approve_reject_cancel_via_tools(client, db_session):
    headers = auth_header(client)
    leave_type = _create_type(client, headers, name="Annual Leave AI Create")
    _create_policy(client, headers, leave_type_id=leave_type["id"], days=20)
    dept = create_department(client, name="LeaveAIWriteDept")

    mgr_user, manager = _create_linked_employee(
        db_session,
        email="leave.ai.mgr@test.com",
        password="mgrpass123",
        department_id=dept["id"],
        first_name="AI",
        last_name="Manager",
        position="Lead",
    )
    peer_user, peer = _create_linked_employee(
        db_session,
        email="leave.ai.peer@test.com",
        password="peerpass123",
        department_id=dept["id"],
        first_name="Other",
        last_name="Mgr",
        position="Lead",
    )
    emp_user, report = _create_linked_employee(
        db_session,
        email="leave.ai.emp@test.com",
        password="emppass123",
        department_id=dept["id"],
        first_name="AI",
        last_name="Employee",
        manager_id=manager.id,
    )

    leave_service = get_leave_service(db_session)
    create_reg = ToolRegistry()
    create_reg.register(CreateLeaveRequestTool(leave_service))
    approve_reg = ToolRegistry()
    approve_reg.register(ApproveLeaveRequestTool(leave_service))
    reject_reg = ToolRegistry()
    reject_reg.register(RejectLeaveRequestTool(leave_service))
    cancel_reg = ToolRegistry()
    cancel_reg.register(CancelPendingLeaveRequestTool(leave_service))

    emp_ctx = _emp_ctx(emp_user.id, report.id)
    mgr_ctx = _emp_ctx(mgr_user.id, manager.id)
    peer_ctx = _emp_ctx(peer_user.id, peer.id)

    start = date(CURRENT_YEAR, 11, 10)
    end = date(CURRENT_YEAR, 11, 12)
    create_args = {
        "leave_type_id": leave_type["id"],
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "reason": "Trip",
    }
    pending = ToolExecutor(create_reg).execute(
        emp_ctx, "create_leave_request", create_args
    )
    assert pending.confirmation_token

    created = ToolExecutor(create_reg).execute(
        emp_ctx, "create_leave_request", create_args, execute_writes=True
    )
    request_id = created.data["request_id"]
    assert created.data["status"] == "pending"

    with pytest.raises(ToolExecutionError):
        ToolExecutor(create_reg).execute(
            emp_ctx, "create_leave_request", create_args, execute_writes=True
        )

    with pytest.raises(ToolExecutionError):
        ToolExecutor(create_reg).execute(
            emp_ctx,
            "create_leave_request",
            {
                "leave_type_id": leave_type["id"],
                "start_date": end.isoformat(),
                "end_date": start.isoformat(),
            },
            execute_writes=True,
        )

    with pytest.raises(ToolExecutionError):
        ToolExecutor(approve_reg).execute(
            peer_ctx,
            "approve_leave_request",
            {"request_id": request_id},
            execute_writes=True,
        )

    with pytest.raises(ToolExecutionError):
        ToolExecutor(approve_reg).execute(
            emp_ctx,
            "approve_leave_request",
            {"request_id": request_id},
            execute_writes=True,
        )

    mgr_done = ToolExecutor(approve_reg).execute(
        mgr_ctx,
        "approve_leave_request",
        {"request_id": request_id},
        execute_writes=True,
    )
    assert mgr_done.data["manager_approval"] == "approved"

    start2 = date(CURRENT_YEAR, 12, 1)
    end2 = date(CURRENT_YEAR, 12, 2)
    created2 = ToolExecutor(create_reg).execute(
        emp_ctx,
        "create_leave_request",
        {
            "leave_type_id": leave_type["id"],
            "start_date": start2.isoformat(),
            "end_date": end2.isoformat(),
        },
        execute_writes=True,
    )
    cancelled = ToolExecutor(cancel_reg).execute(
        emp_ctx,
        "cancel_pending_leave_request",
        {"request_id": created2.data["request_id"]},
        execute_writes=True,
    )
    assert cancelled.data["status"] == "cancelled"

    start3 = date(CURRENT_YEAR, 12, 10)
    end3 = date(CURRENT_YEAR, 12, 11)
    created3 = ToolExecutor(create_reg).execute(
        emp_ctx,
        "create_leave_request",
        {
            "leave_type_id": leave_type["id"],
            "start_date": start3.isoformat(),
            "end_date": end3.isoformat(),
        },
        execute_writes=True,
    )
    rejected = ToolExecutor(reject_reg).execute(
        mgr_ctx,
        "reject_leave_request",
        {
            "request_id": created3.data["request_id"],
            "rejection_reason": "Busy period",
        },
        execute_writes=True,
    )
    assert rejected.data["status"] == "rejected"


def test_cancellation_lifecycle_via_tools(client, db_session):
    headers = auth_header(client)
    leave_type = _create_type(client, headers, name="Annual Leave AI Cancel")
    _create_policy(client, headers, leave_type_id=leave_type["id"], days=20)
    dept = create_department(client, name="LeaveAICancelDept")

    mgr_user, manager = _create_linked_employee(
        db_session,
        email="leave.ai.cancel.mgr@test.com",
        password="mgrpass123",
        department_id=dept["id"],
        first_name="Cancel",
        last_name="Mgr",
        position="Lead",
    )
    emp_user, report = _create_linked_employee(
        db_session,
        email="leave.ai.cancel.emp@test.com",
        password="emppass123",
        department_id=dept["id"],
        first_name="Cancel",
        last_name="Emp",
        manager_id=manager.id,
    )
    create_user_with_role(
        db_session,
        email="leave.ai.cancel.hr@test.com",
        password="hrpass123",
        role_name="hr",
    )
    hr_headers = auth_header(client, "leave.ai.cancel.hr@test.com", "hrpass123")
    mgr_headers = auth_header(client, "leave.ai.cancel.mgr@test.com", "mgrpass123")
    emp_headers = auth_header(client, "leave.ai.cancel.emp@test.com", "emppass123")

    start = date.today() + timedelta(days=30)
    if start.year != CURRENT_YEAR:
        start = date(CURRENT_YEAR, 12, 15)
    end = start + timedelta(days=2)

    created = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        headers=emp_headers,
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]

    assert (
        client.patch(
            f"/api/v1/leave/requests/{request_id}/approve", headers=mgr_headers
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/leave/requests/{request_id}/approve", headers=hr_headers
        ).status_code
        == 200
    )
    detail = client.get(
        f"/api/v1/me/leave/requests/{request_id}", headers=emp_headers
    )
    assert detail.json()["status"] == "approved"

    leave_service = get_leave_service(db_session)
    registry = ToolRegistry()
    registry.register(RequestLeaveCancellationTool(leave_service))
    registry.register(ApproveLeaveCancellationTool(leave_service))

    emp_ctx = _emp_ctx(emp_user.id, report.id)
    mgr_ctx = _emp_ctx(mgr_user.id, manager.id)

    pending = ToolExecutor(registry).execute(
        emp_ctx,
        "request_leave_cancellation",
        {"request_id": request_id, "reason": "Plans changed"},
    )
    assert pending.confirmation_token

    requested = ToolExecutor(registry).execute(
        emp_ctx,
        "request_leave_cancellation",
        {"request_id": request_id, "reason": "Plans changed"},
        execute_writes=True,
    )
    assert requested.data["status"] == "approved"
    assert requested.data["cancellation_status"] == "requested"

    approved_cancel = ToolExecutor(registry).execute(
        mgr_ctx,
        "approve_leave_cancellation",
        {"request_id": request_id},
        execute_writes=True,
    )
    assert approved_cancel.data["status"] == "cancelled"


def test_confirmation_security_altered_and_wrong_user(client, db_session):
    headers = auth_header(client)
    leave_type = _create_type(client, headers, name="Annual Leave AI Sec")
    _create_policy(client, headers, leave_type_id=leave_type["id"], days=10)
    dept = create_department(client, name="LeaveAISecDept")
    emp_user, report = _create_linked_employee(
        db_session,
        email="leave.ai.sec.emp@test.com",
        password="emppass123",
        department_id=dept["id"],
        first_name="Sec",
        last_name="Emp",
    )
    other_user, other_emp = _create_linked_employee(
        db_session,
        email="leave.ai.sec.other@test.com",
        password="otherpass123",
        department_id=dept["id"],
        first_name="Other",
        last_name="Emp",
    )

    leave_service = get_leave_service(db_session)
    registry = ToolRegistry()
    registry.register(CreateLeaveRequestTool(leave_service))
    emp_ctx = _emp_ctx(emp_user.id, report.id)
    other_ctx = _emp_ctx(other_user.id, other_emp.id)

    args = {
        "leave_type_id": leave_type["id"],
        "start_date": f"{CURRENT_YEAR}-09-01",
        "end_date": f"{CURRENT_YEAR}-09-02",
    }
    pending = ToolExecutor(registry).execute(emp_ctx, "create_leave_request", args)
    token = pending.confirmation_token
    assert token

    agent = LeaveAgent(
        llm_provider=MagicMock(),
        leave_service=leave_service,
        employee_service=MagicMock(),
        db=db_session,
    )
    with pytest.raises(LeaveAgentValidationError):
        agent.confirm(token=token, context=other_ctx)

    padded = token + "=" * (-len(token) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    body, sig = raw.rsplit(b".", 1)
    payload = json.loads(body)
    payload["arguments"] = {**args, "leave_type_id": 99999}
    tampered_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    bad = (
        base64.urlsafe_b64encode(tampered_body + b"." + sig)
        .decode("ascii")
        .rstrip("=")
    )
    with pytest.raises(LeaveAgentValidationError):
        agent.confirm(token=bad, context=emp_ctx)

    short, _ = create_confirmation_token(
        user_id=emp_user.id,
        tool_name="create_leave_request",
        arguments=args,
        summary="x",
        ttl_seconds=60,
    )
    with patch(
        "app.ai.confirmation.tokens.time.time", return_value=time.time() + 10_000
    ):
        with pytest.raises(LeaveAgentValidationError):
            agent.confirm(token=short, context=emp_ctx)

    ok = agent.confirm(token=token, context=emp_ctx)
    assert "create_leave_request" in ok.tool_names_called
    assert ok.pending_confirmation is None
