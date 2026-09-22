from datetime import date

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
