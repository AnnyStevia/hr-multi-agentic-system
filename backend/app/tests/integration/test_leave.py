from datetime import date, timedelta

from app.modules.notifications.models import Notification, NotificationType
from app.tests.helpers import auth_header, create_candidate_user, create_user_with_role
from app.tests.integration.test_onboarding import _hire


CURRENT_YEAR = date.today().year


def _create_type(client, headers, *, name: str = "Annual Leave", **extra):
    payload = {"name": name, "description": "Company annual leave", "is_paid": True}
    payload.update(extra)
    response = client.post("/api/v1/leave/types", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _create_policy(client, headers, *, leave_type_id: int, year: int = CURRENT_YEAR, days: int = 24):
    response = client.post(
        "/api/v1/leave/policies",
        json={"leave_type_id": leave_type_id, "year": year, "days_allowed": days},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_hr_can_create_and_update_leave_type(client, db_session):
    create_user_with_role(db_session, email="hr.leave.type@test.com", password="hrpass123", role_name="hr")
    headers = auth_header(client, "hr.leave.type@test.com", "hrpass123")
    created = _create_type(client, headers, name="Sick Leave")
    assert created["name"] == "Sick Leave"
    assert created["is_active"] is True

    updated = client.patch(
        f"/api/v1/leave/types/{created['id']}",
        json={"description": "Medical absence", "is_paid": True},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["description"] == "Medical absence"

    deactivated = client.delete(f"/api/v1/leave/types/{created['id']}", headers=headers)
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["is_active"] is False


def test_employee_cannot_manage_leave_types(client, db_session):
    _a, _j, candidate_headers, _h, _body = _hire(client, db_session, email="leave.emp.type@test.com")
    assert (
        client.post(
            "/api/v1/leave/types",
            json={"name": "Nope"},
            headers=candidate_headers,
        ).status_code
        == 403
    )


def test_hr_can_create_update_policy_and_rejects_duplicates_and_negatives(client):
    headers = auth_header(client)
    leave_type = _create_type(client, headers, name="Annual Leave Policy")
    policy = _create_policy(client, headers, leave_type_id=leave_type["id"], year=CURRENT_YEAR, days=24)
    assert policy["days_allowed"] == 24

    duplicate = client.post(
        "/api/v1/leave/policies",
        json={
            "leave_type_id": leave_type["id"],
            "year": CURRENT_YEAR,
            "days_allowed": 20,
        },
        headers=headers,
    )
    assert duplicate.status_code == 409

    negative = client.post(
        "/api/v1/leave/policies",
        json={"leave_type_id": leave_type["id"], "year": CURRENT_YEAR + 1, "days_allowed": -1},
        headers=headers,
    )
    assert negative.status_code == 422

    next_year = _create_policy(
        client, headers, leave_type_id=leave_type["id"], year=CURRENT_YEAR + 1, days=25
    )
    assert next_year["days_allowed"] == 25

    updated = client.patch(
        f"/api/v1/leave/policies/{policy['id']}",
        json={"days_allowed": 26},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["days_allowed"] == 26


def test_balances_and_request_validation_flow(client, db_session):
    headers = auth_header(client)
    leave_type = _create_type(client, headers, name="Annual Leave Bal")
    _create_policy(client, headers, leave_type_id=leave_type["id"], days=10)

    _a, _j, emp_headers, _h, body = _hire(client, db_session, email="leave.bal@test.com")
    employee_id = body["hired_employee_id"]

    balances = client.get("/api/v1/me/leave/balances", headers=emp_headers)
    assert balances.status_code == 200, balances.text
    assert len(balances.json()) == 1
    assert balances.json()[0]["days_allowed"] == 10
    assert balances.json()[0]["days_used"] == 0
    assert balances.json()[0]["days_available"] == 10

    hr_balances = client.get(
        f"/api/v1/employees/{employee_id}/leave/balances",
        headers=headers,
    )
    assert hr_balances.status_code == 200
    assert hr_balances.json()[0]["days_allowed"] == 10

    created = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": f"{CURRENT_YEAR}-06-01",
            "end_date": f"{CURRENT_YEAR}-06-03",
            "reason": "Family",
        },
        headers=emp_headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["requested_days"] == 3
    assert created.json()["status"] == "pending"
    request_id = created.json()["id"]

    pending_balances = client.get("/api/v1/me/leave/balances", headers=emp_headers).json()[0]
    assert pending_balances["days_used"] == 0
    assert pending_balances["days_pending"] == 3
    assert pending_balances["days_available"] == 10

    over = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": f"{CURRENT_YEAR}-07-01",
            "end_date": f"{CURRENT_YEAR}-07-10",
        },
        headers=emp_headers,
    )
    assert over.status_code == 400

    approved = client.patch(
        f"/api/v1/leave/requests/{request_id}/approve",
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    after = client.get("/api/v1/me/leave/balances", headers=emp_headers).json()[0]
    assert after["days_used"] == 3
    assert after["days_pending"] == 0
    assert after["days_available"] == 7

    again = client.patch(
        f"/api/v1/leave/requests/{request_id}/approve",
        headers=headers,
    )
    assert again.status_code == 400


def test_invalid_dates_overlap_reject_cancel_and_security(client, db_session):
    headers = auth_header(client)
    leave_type = _create_type(client, headers, name="Annual Leave Req")
    _create_policy(client, headers, leave_type_id=leave_type["id"], days=20)

    _a, _j, emp_headers, _h, body = _hire(client, db_session, email="leave.req@test.com")
    employee_id = body["hired_employee_id"]

    invalid = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": f"{CURRENT_YEAR}-08-10",
            "end_date": f"{CURRENT_YEAR}-08-01",
        },
        headers=emp_headers,
    )
    assert invalid.status_code == 400
    assert "End date must be on or after the start date" in invalid.json()["detail"]

    multi_year = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": f"{CURRENT_YEAR}-12-30",
            "end_date": f"{CURRENT_YEAR + 1}-01-02",
        },
        headers=emp_headers,
    )
    assert multi_year.status_code == 400

    first = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": f"{CURRENT_YEAR}-09-01",
            "end_date": f"{CURRENT_YEAR}-09-05",
        },
        headers=emp_headers,
    ).json()

    overlap = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": f"{CURRENT_YEAR}-09-04",
            "end_date": f"{CURRENT_YEAR}-09-08",
        },
        headers=emp_headers,
    )
    assert overlap.status_code == 400
    assert "overlaps these dates" in overlap.json()["detail"]

    missing_reason = client.patch(
        f"/api/v1/leave/requests/{first['id']}/reject",
        json={},
        headers=headers,
    )
    assert missing_reason.status_code == 422

    rejected = client.patch(
        f"/api/v1/leave/requests/{first['id']}/reject",
        json={"rejection_reason": "Team coverage needed that week"},
        headers=headers,
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["rejection_reason"] == "Team coverage needed that week"

    balances = client.get("/api/v1/me/leave/balances", headers=emp_headers).json()[0]
    assert balances["days_used"] == 0

    second = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": f"{CURRENT_YEAR}-10-01",
            "end_date": f"{CURRENT_YEAR}-10-02",
        },
        headers=emp_headers,
    ).json()
    cancelled = client.patch(
        f"/api/v1/me/leave/requests/{second['id']}/cancel",
        headers=emp_headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    balances = client.get("/api/v1/me/leave/balances", headers=emp_headers).json()[0]
    assert balances["days_used"] == 0
    assert balances["days_pending"] == 0

    assert (
        client.patch(
            f"/api/v1/leave/requests/{first['id']}/approve",
            headers=emp_headers,
        ).status_code
        == 403
    )

    other = create_candidate_user(
        db_session, email="leave.other@test.com", password="otherpass123"
    )
    other_headers = auth_header(client, other.email, "otherpass123")
    assert client.get("/api/v1/me/leave/balances", headers=other_headers).status_code == 404
    assert (
        client.get(f"/api/v1/me/leave/requests/{second['id']}", headers=other_headers).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/employees/{employee_id}/leave/balances",
            headers=other_headers,
        ).status_code
        == 403
    )


def test_leave_notifications(client, db_session):
    headers = auth_header(client)
    leave_type = _create_type(client, headers, name="Annual Leave Notif")
    _create_policy(client, headers, leave_type_id=leave_type["id"], days=15)
    create_user_with_role(
        db_session, email="leave.notif.hr@test.com", password="hrpass123", role_name="hr"
    )

    _a, _j, emp_headers, _h, body = _hire(client, db_session, email="leave.notif@test.com")
    admin = auth_header(client)

    created = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": f"{CURRENT_YEAR}-11-01",
            "end_date": f"{CURRENT_YEAR}-11-02",
        },
        headers=emp_headers,
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]

    submitted = (
        db_session.query(Notification)
        .filter(Notification.type == NotificationType.LEAVE_REQUEST_SUBMITTED)
        .count()
    )
    assert submitted >= 1

    client.patch(f"/api/v1/leave/requests/{request_id}/approve", headers=admin)
    from app.modules.employees.models import Employee

    employee = db_session.query(Employee).filter(Employee.id == body["hired_employee_id"]).one()
    approved = (
        db_session.query(Notification)
        .filter(
            Notification.type == NotificationType.LEAVE_REQUEST_APPROVED,
            Notification.recipient_user_id == employee.user_id,
        )
        .count()
    )
    assert approved == 1

    # second request for rejection notification
    second = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": f"{CURRENT_YEAR}-11-10",
            "end_date": f"{CURRENT_YEAR}-11-11",
        },
        headers=emp_headers,
    ).json()
    client.patch(
        f"/api/v1/leave/requests/{second['id']}/reject",
        json={"rejection_reason": "Insufficient notice"},
        headers=admin,
    )
    rejected = (
        db_session.query(Notification)
        .filter(
            Notification.type == NotificationType.LEAVE_REQUEST_REJECTED,
            Notification.recipient_user_id == employee.user_id,
        )
        .count()
    )
    assert rejected == 1



def test_leave_calendar_and_current_work_status(client, db_session):
    from app.tests.helpers import create_department
    from app.tests.integration.test_organization import _create_linked_employee

    headers = auth_header(client)
    leave_type = _create_type(client, headers, name="Annual Leave Cal")
    _create_policy(client, headers, leave_type_id=leave_type["id"], days=30)

    _a, _j, emp_headers, _h, body = _hire(client, db_session, email="leave.cal@test.com")
    employee_id = body["hired_employee_id"]
    today = date.today()
    assert today.year == CURRENT_YEAR

    pending = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": f"{CURRENT_YEAR}-03-10",
            "end_date": f"{CURRENT_YEAR}-03-12",
        },
        headers=emp_headers,
    )
    assert pending.status_code == 201, pending.text

    calendar = client.get(
        f"/api/v1/me/leave/calendar?year={CURRENT_YEAR}&month=3",
        headers=emp_headers,
    )
    assert calendar.status_code == 200, calendar.text
    periods = calendar.json()["periods"]
    assert len(periods) == 1
    assert periods[0]["status"] == "pending"
    assert periods[0]["start_date"] == f"{CURRENT_YEAR}-03-10"

    other = create_candidate_user(
        db_session, email="leave.cal.other@test.com", password="otherpass123"
    )
    other_headers = auth_header(client, other.email, "otherpass123")
    assert (
        client.get(
            f"/api/v1/me/leave/calendar?year={CURRENT_YEAR}&month=3",
            headers=other_headers,
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/employees/{employee_id}/leave/calendar?year={CURRENT_YEAR}&month=3",
            headers=other_headers,
        ).status_code
        == 403
    )

    hr_cal = client.get(
        f"/api/v1/employees/{employee_id}/leave/calendar?year={CURRENT_YEAR}&month=3",
        headers=headers,
    )
    assert hr_cal.status_code == 200
    assert len(hr_cal.json()["periods"]) == 1

    assert (
        client.patch(
            f"/api/v1/me/leave/requests/{pending.json()['id']}/cancel",
            headers=emp_headers,
        ).status_code
        == 200
    )

    day = min(max(today.day, 2), 26)
    start = date(CURRENT_YEAR, today.month, day - 1)
    end = date(CURRENT_YEAR, today.month, day + 1)
    covering = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        headers=emp_headers,
    )
    assert covering.status_code == 201, covering.text
    covering_id = covering.json()["id"]
    assert (
        client.patch(
            f"/api/v1/leave/requests/{covering_id}/approve",
            headers=headers,
        ).status_code
        == 200
    )

    emp = client.get(f"/api/v1/employees/{employee_id}", headers=headers)
    assert emp.status_code == 200
    assert emp.json()["current_work_status"] == "ON_LEAVE"
    assert emp.json()["current_leave"]["leave_type"] == "Annual Leave Cal"
    assert emp.json()["employment_status"] == "active"

    profile = client.get("/api/v1/me/profile", headers=emp_headers)
    assert profile.status_code == 200
    assert profile.json()["current_work_status"] == "ON_LEAVE"

    cal2 = client.get(
        f"/api/v1/me/leave/calendar?year={CURRENT_YEAR}&month={today.month}",
        headers=emp_headers,
    )
    assert cal2.status_code == 200
    assert any(p["status"] == "approved" for p in cal2.json()["periods"])

    dept = create_department(client, name="LeaveStatusDept")
    _mgr_user, manager = _create_linked_employee(
        db_session,
        email="leave.status.mgr@test.com",
        password="mgrpass123",
        department_id=dept["id"],
        first_name="Mgr",
        last_name="Status",
        position="Manager",
    )
    _emp_user, report = _create_linked_employee(
        db_session,
        email="leave.status.emp@test.com",
        password="emppass123",
        department_id=dept["id"],
        first_name="Rep",
        last_name="Status",
        manager_id=manager.id,
    )
    detail = client.get(f"/api/v1/employees/{report.id}", headers=headers)
    assert detail.json()["current_work_status"] == "ACTIVE"
    assert detail.json()["current_leave"] is None


def test_manager_approval_admin_override_and_no_manager(client, db_session):
    from app.modules.employees.models import Employee, EmploymentStatus
    from app.modules.identity.models import User
    from app.tests.helpers import create_department
    from app.tests.integration.test_organization import _create_linked_employee

    headers = auth_header(client)
    leave_type = _create_type(client, headers, name="Annual Leave Appr")
    _create_policy(client, headers, leave_type_id=leave_type["id"], days=20)
    dept = create_department(client, name="LeaveApprDept")

    _mgr_user, manager = _create_linked_employee(
        db_session,
        email="leave.mgr@test.com",
        password="mgrpass123",
        department_id=dept["id"],
        first_name="Direct",
        last_name="Manager",
        position="Team Lead",
    )
    mgr_headers = auth_header(client, "leave.mgr@test.com", "mgrpass123")

    _peer_user, _peer = _create_linked_employee(
        db_session,
        email="leave.peer@test.com",
        password="peerpass123",
        department_id=dept["id"],
        first_name="Other",
        last_name="Manager",
        position="Other Lead",
    )
    peer_headers = auth_header(client, "leave.peer@test.com", "peerpass123")

    _emp_user, _report = _create_linked_employee(
        db_session,
        email="leave.report@test.com",
        password="emppass123",
        department_id=dept["id"],
        first_name="Report",
        last_name="Emp",
        manager_id=manager.id,
    )
    emp_headers = auth_header(client, "leave.report@test.com", "emppass123")

    create_user_with_role(
        db_session, email="leave.hronly@test.com", password="hrpass123", role_name="hr"
    )
    hr_only = auth_header(client, "leave.hronly@test.com", "hrpass123")

    created = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": f"{CURRENT_YEAR}-04-01",
            "end_date": f"{CURRENT_YEAR}-04-03",
        },
        headers=emp_headers,
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    assert created.json()["manager_approval"] == "pending"
    assert created.json()["hr_approval"] == "pending"

    team = client.get("/api/v1/me/leave/team-requests", headers=mgr_headers)
    assert team.status_code == 200
    assert any(item["id"] == request_id for item in team.json())

    assert (
        client.patch(
            f"/api/v1/leave/requests/{request_id}/approve",
            headers=peer_headers,
        ).status_code
        == 403
    )
    # HR cannot approve before manager when manager is available
    early_hr = client.patch(
        f"/api/v1/leave/requests/{request_id}/approve",
        headers=hr_only,
    )
    assert early_hr.status_code == 400
    assert "manager approval is required" in early_hr.json()["detail"].lower()
    assert (
        client.patch(
            f"/api/v1/leave/requests/{request_id}/approve",
            headers=emp_headers,
        ).status_code
        == 403
    )

    mgr_approved = client.patch(
        f"/api/v1/leave/requests/{request_id}/approve",
        headers=mgr_headers,
    )
    assert mgr_approved.status_code == 200, mgr_approved.text
    assert mgr_approved.json()["status"] == "pending"
    assert mgr_approved.json()["manager_approval"] == "approved"
    assert mgr_approved.json()["hr_approval"] == "pending"

    # Duplicate manager approval rejected
    assert (
        client.patch(
            f"/api/v1/leave/requests/{request_id}/approve",
            headers=mgr_headers,
        ).status_code
        == 400
    )

    hr_approved = client.patch(
        f"/api/v1/leave/requests/{request_id}/approve",
        headers=hr_only,
    )
    assert hr_approved.status_code == 200, hr_approved.text
    assert hr_approved.json()["status"] == "approved"
    assert hr_approved.json()["hr_approval"] == "approved"

    # --- HR employee self-leave: manager only ---
    _hr_mgr_user, hr_manager = _create_linked_employee(
        db_session,
        email="leave.hrmgr@test.com",
        password="hrmgrpass",
        department_id=dept["id"],
        first_name="HR",
        last_name="Boss",
        position="HR Manager",
    )
    hr_mgr_headers = auth_header(client, "leave.hrmgr@test.com", "hrmgrpass")
    create_user_with_role(
        db_session, email="leave.hrspec@test.com", password="hrspecpass", role_name="hr"
    )
    hr_spec_user = db_session.query(User).filter(User.email == "leave.hrspec@test.com").one()
    hr_spec_emp = Employee(
        employee_number="PENDING",
        first_name="HR",
        last_name="Spec",
        email="leave.hrspec@test.com",
        phone="+21620999888",
        department_id=dept["id"],
        position="HR Specialist",
        manager_id=hr_manager.id,
        hire_date=date(2024, 1, 1),
        employment_status=EmploymentStatus.ACTIVE,
        user_id=hr_spec_user.id,
    )
    db_session.add(hr_spec_emp)
    db_session.flush()
    hr_spec_emp.employee_number = f"EMP-{hr_spec_emp.id:06d}"
    db_session.commit()
    hr_spec_headers = auth_header(client, "leave.hrspec@test.com", "hrspecpass")
    hr_req = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": f"{CURRENT_YEAR}-05-01",
            "end_date": f"{CURRENT_YEAR}-05-02",
        },
        headers=hr_spec_headers,
    )
    assert hr_req.status_code == 201, hr_req.text
    assert (
        client.patch(
            f"/api/v1/leave/requests/{hr_req.json()['id']}/approve",
            headers=hr_spec_headers,
        ).status_code
        == 403
    )
    # Peer HR cannot approve HR specialist leave
    assert (
        client.patch(
            f"/api/v1/leave/requests/{hr_req.json()['id']}/approve",
            headers=hr_only,
        ).status_code
        == 403
    )
    hr_mgr_ok = client.patch(
        f"/api/v1/leave/requests/{hr_req.json()['id']}/approve",
        headers=hr_mgr_headers,
    )
    assert hr_mgr_ok.status_code == 200, hr_mgr_ok.text
    assert hr_mgr_ok.json()["status"] == "approved"

    _orphan_user, _orphan = _create_linked_employee(
        db_session,
        email="leave.orphan@test.com",
        password="orphanpass",
        department_id=dept["id"],
        first_name="No",
        last_name="Manager",
        manager_id=None,
    )
    orphan_headers = auth_header(client, "leave.orphan@test.com", "orphanpass")
    orphan_req = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": f"{CURRENT_YEAR}-06-10",
            "end_date": f"{CURRENT_YEAR}-06-11",
        },
        headers=orphan_headers,
    )
    assert orphan_req.status_code == 201, orphan_req.text
    # Unrelated manager cannot approve
    no_mgr = client.patch(
        f"/api/v1/leave/requests/{orphan_req.json()['id']}/approve",
        headers=mgr_headers,
    )
    assert no_mgr.status_code == 403

    # With no manager, available HR can approve alone
    orphan_hr = client.patch(
        f"/api/v1/leave/requests/{orphan_req.json()['id']}/approve",
        headers=hr_only,
    )
    assert orphan_hr.status_code == 200, orphan_hr.text
    assert orphan_hr.json()["status"] == "approved"

    orphan2 = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": f"{CURRENT_YEAR}-06-20",
            "end_date": f"{CURRENT_YEAR}-06-21",
        },
        headers=orphan_headers,
    )
    assert orphan2.status_code == 201, orphan2.text
    override = client.patch(
        f"/api/v1/leave/requests/{orphan2.json()['id']}/approve",
        headers=headers,
    )
    assert override.status_code == 200, override.text
    assert override.json()["admin_override"] == "approved"
    assert override.json()["status"] == "approved"


def test_dual_approval_unavailable_approvers_and_security(client, db_session):
    """Manager/HR ON_LEAVE shortcuts, admin when both away, reject/cancel guards."""
    from app.modules.employees.models import Employee, EmploymentStatus
    from app.modules.identity.models import User
    from app.modules.leave.models import LeaveRequest, LeaveRequestStatus
    from app.tests.helpers import create_department
    from app.tests.integration.test_organization import _create_linked_employee

    headers = auth_header(client)
    leave_type = _create_type(client, headers, name="Annual Leave Dual")
    _create_policy(client, headers, leave_type_id=leave_type["id"], days=40)
    dept = create_department(client, name="LeaveDualDept")
    today = date.today()

    _mgr_user, manager = _create_linked_employee(
        db_session,
        email="leave.dual.mgr@test.com",
        password="mgrpass123",
        department_id=dept["id"],
        first_name="Dual",
        last_name="Mgr",
    )
    mgr_headers = auth_header(client, "leave.dual.mgr@test.com", "mgrpass123")

    create_user_with_role(
        db_session, email="leave.dual.hr@test.com", password="hrpass123", role_name="hr"
    )
    hr_user = db_session.query(User).filter(User.email == "leave.dual.hr@test.com").one()
    hr_emp = Employee(
        employee_number="PENDING",
        first_name="Dual",
        last_name="HR",
        email="leave.dual.hr@test.com",
        phone="+21620111222",
        department_id=dept["id"],
        position="HR Officer",
        hire_date=date(2024, 1, 1),
        employment_status=EmploymentStatus.ACTIVE,
        user_id=hr_user.id,
    )
    db_session.add(hr_emp)
    db_session.flush()
    hr_emp.employee_number = f"EMP-{hr_emp.id:06d}"
    db_session.commit()
    hr_headers = auth_header(client, "leave.dual.hr@test.com", "hrpass123")

    _emp_user, report = _create_linked_employee(
        db_session,
        email="leave.dual.emp@test.com",
        password="emppass123",
        department_id=dept["id"],
        first_name="Dual",
        last_name="Emp",
        manager_id=manager.id,
    )
    emp_headers = auth_header(client, "leave.dual.emp@test.com", "emppass123")

    # Put manager on approved leave covering today
    mgr_leave = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": (today - timedelta(days=1)).isoformat(),
            "end_date": (today + timedelta(days=1)).isoformat(),
        },
        headers=mgr_headers,
    )
    assert mgr_leave.status_code == 201, mgr_leave.text
    assert (
        client.patch(
            f"/api/v1/leave/requests/{mgr_leave.json()['id']}/approve",
            headers=headers,
        ).status_code
        == 200
    )

    # Employee request: manager ON_LEAVE → HR alone sufficient
    emp_req = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": f"{CURRENT_YEAR}-07-01",
            "end_date": f"{CURRENT_YEAR}-07-02",
        },
        headers=emp_headers,
    )
    assert emp_req.status_code == 201, emp_req.text
    hr_alone = client.patch(
        f"/api/v1/leave/requests/{emp_req.json()['id']}/approve",
        headers=hr_headers,
    )
    assert hr_alone.status_code == 200, hr_alone.text
    assert hr_alone.json()["status"] == "approved"
    assert hr_alone.json()["hr_approval"] == "approved"

    # HR ON_LEAVE → manager alone sufficient
    hr_own = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": (today - timedelta(days=1)).isoformat(),
            "end_date": (today + timedelta(days=2)).isoformat(),
        },
        headers=hr_headers,
    )
    # HR has no manager → admin must approve their leave first so they are ON_LEAVE
    assert hr_own.status_code == 201, hr_own.text
    assert (
        client.patch(
            f"/api/v1/leave/requests/{hr_own.json()['id']}/approve",
            headers=headers,
        ).status_code
        == 200
    )

    # End manager leave so manager is ACTIVE again for next check
    mgr_req_row = (
        db_session.query(LeaveRequest).filter(LeaveRequest.id == mgr_leave.json()["id"]).one()
    )
    mgr_req_row.end_date = today - timedelta(days=2)
    mgr_req_row.start_date = today - timedelta(days=3)
    db_session.commit()

    emp_req2 = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": f"{CURRENT_YEAR}-08-01",
            "end_date": f"{CURRENT_YEAR}-08-02",
        },
        headers=emp_headers,
    )
    assert emp_req2.status_code == 201, emp_req2.text
    mgr_alone = client.patch(
        f"/api/v1/leave/requests/{emp_req2.json()['id']}/approve",
        headers=mgr_headers,
    )
    assert mgr_alone.status_code == 200, mgr_alone.text
    assert mgr_alone.json()["status"] == "approved"
    assert mgr_alone.json()["manager_approval"] == "approved"

    # Reject then cannot approve
    emp_req3 = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": f"{CURRENT_YEAR}-09-01",
            "end_date": f"{CURRENT_YEAR}-09-02",
        },
        headers=emp_headers,
    ).json()
    assert (
        client.patch(
            f"/api/v1/leave/requests/{emp_req3['id']}/reject",
            json={"rejection_reason": "Coverage"},
            headers=mgr_headers,
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/leave/requests/{emp_req3['id']}/approve",
            headers=headers,
        ).status_code
        == 400
    )

    # Cancel then cannot approve
    emp_req4 = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": f"{CURRENT_YEAR}-10-01",
            "end_date": f"{CURRENT_YEAR}-10-02",
        },
        headers=emp_headers,
    ).json()
    assert (
        client.patch(
            f"/api/v1/me/leave/requests/{emp_req4['id']}/cancel",
            headers=emp_headers,
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/leave/requests/{emp_req4['id']}/approve",
            headers=headers,
        ).status_code
        == 400
    )

    # Both manager and HR on leave → admin
    # Put manager back on leave for today
    mgr_req_row.start_date = today - timedelta(days=1)
    mgr_req_row.end_date = today + timedelta(days=1)
    mgr_req_row.status = LeaveRequestStatus.APPROVED
    db_session.commit()

    emp_req5 = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": f"{CURRENT_YEAR}-11-01",
            "end_date": f"{CURRENT_YEAR}-11-02",
        },
        headers=emp_headers,
    )
    assert emp_req5.status_code == 201, emp_req5.text
    assert (
        client.patch(
            f"/api/v1/leave/requests/{emp_req5.json()['id']}/approve",
            headers=mgr_headers,
        ).status_code
        == 400
    )
    assert (
        client.patch(
            f"/api/v1/leave/requests/{emp_req5.json()['id']}/approve",
            headers=hr_headers,
        ).status_code
        == 400
    )
    both = client.patch(
        f"/api/v1/leave/requests/{emp_req5.json()['id']}/approve",
        headers=headers,
    )
    assert both.status_code == 200, both.text
    assert both.json()["admin_override"] == "approved"

    # HR manager ON_LEAVE → admin can approve HR specialist leave
    _hr_boss_user, hr_boss = _create_linked_employee(
        db_session,
        email="leave.dual.hrboss@test.com",
        password="bossPass1",
        department_id=dept["id"],
        first_name="HR",
        last_name="Boss2",
    )
    create_user_with_role(
        db_session, email="leave.dual.hrspec2@test.com", password="specPass1", role_name="hr"
    )
    spec2 = db_session.query(User).filter(User.email == "leave.dual.hrspec2@test.com").one()
    spec2_emp = Employee(
        employee_number="PENDING",
        first_name="Spec",
        last_name="Two",
        email="leave.dual.hrspec2@test.com",
        phone="+21620333444",
        department_id=dept["id"],
        position="HR Spec",
        manager_id=hr_boss.id,
        hire_date=date(2024, 1, 1),
        employment_status=EmploymentStatus.ACTIVE,
        user_id=spec2.id,
    )
    db_session.add(spec2_emp)
    db_session.flush()
    spec2_emp.employee_number = f"EMP-{spec2_emp.id:06d}"
    db_session.commit()
    hr_boss_headers = auth_header(client, "leave.dual.hrboss@test.com", "bossPass1")
    # Put HR boss on leave
    boss_leave = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": (today - timedelta(days=1)).isoformat(),
            "end_date": (today + timedelta(days=1)).isoformat(),
        },
        headers=hr_boss_headers,
    )
    assert boss_leave.status_code == 201, boss_leave.text
    assert (
        client.patch(
            f"/api/v1/leave/requests/{boss_leave.json()['id']}/approve",
            headers=headers,
        ).status_code
        == 200
    )
    spec2_headers = auth_header(client, "leave.dual.hrspec2@test.com", "specPass1")
    spec_req = client.post(
        "/api/v1/me/leave/requests",
        json={
            "leave_type_id": leave_type["id"],
            "start_date": f"{CURRENT_YEAR}-12-01",
            "end_date": f"{CURRENT_YEAR}-12-02",
        },
        headers=spec2_headers,
    )
    assert spec_req.status_code == 201, spec_req.text
    assert (
        client.patch(
            f"/api/v1/leave/requests/{spec_req.json()['id']}/approve",
            headers=headers,
        ).status_code
        == 200
    )