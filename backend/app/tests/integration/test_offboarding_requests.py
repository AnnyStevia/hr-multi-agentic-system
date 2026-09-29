from datetime import date, timedelta

from app.modules.notifications.models import Notification, NotificationType
from app.tests.helpers import (
    auth_header,
    create_candidate_user,
    create_department,
    create_user_with_role,
)
from app.tests.integration.test_organization import _create_linked_employee


def _future_day(days: int = 30) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _past_day(days: int = 1) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def _emp(db_session, department_id: int, email: str, **kwargs):
    return _create_linked_employee(
        db_session,
        email=email,
        password="emppass123",
        department_id=department_id,
        **kwargs,
    )


def _submit(client, headers, **extra) -> dict:
    payload = {
        "reason": "resignation",
        "reason_details": "Moving abroad",
        "requested_last_working_day": _future_day(),
    }
    payload.update(extra)
    response = client.post("/api/v1/offboarding/requests", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_employee_can_submit_offboarding_request(client, db_session):
    dept = create_department(client, name="Off Req Submit Dept")
    _emp(db_session, dept["id"], "off.req2.submit@test.com")
    emp_headers = auth_header(client, "off.req2.submit@test.com", "emppass123")

    created = _submit(client, emp_headers)
    assert created["status"] == "pending"
    assert created["reason"] == "resignation"
    assert created["reason_details"] == "Moving abroad"
    assert created["offboarding_case_id"] is None

    listed = client.get("/api/v1/offboarding/requests/me", headers=emp_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == created["id"]


def test_employee_cannot_use_termination_reason(client, db_session):
    dept = create_department(client, name="Off Req Term Dept")
    _emp(db_session, dept["id"], "off.req2.term@test.com")
    emp_headers = auth_header(client, "off.req2.term@test.com", "emppass123")

    response = client.post(
        "/api/v1/offboarding/requests",
        json={
            "reason": "termination",
            "requested_last_working_day": _future_day(),
        },
        headers=emp_headers,
    )
    assert response.status_code == 422


def test_submit_notifies_hr_staff(client, db_session):
    dept = create_department(client, name="Off Req Notify Dept")
    create_user_with_role(
        db_session, email="hr.off.req2.notify@test.com", password="hrpass123", role_name="hr"
    )
    user, _emp_row = _emp(db_session, dept["id"], "off.req2.notify.emp@test.com")
    emp_headers = auth_header(client, "off.req2.notify.emp@test.com", "emppass123")

    created = _submit(client, emp_headers)
    notes = (
        db_session.query(Notification)
        .filter(
            Notification.type == NotificationType.OFFBOARDING_REQUEST_SUBMITTED,
            Notification.related_entity_type == "offboarding_request",
            Notification.related_entity_id == created["id"],
        )
        .all()
    )
    assert len(notes) >= 1
    assert all(n.recipient_user_id != user.id for n in notes)


def test_duplicate_pending_rejected(client, db_session):
    dept = create_department(client, name="Off Req Dup Dept")
    _emp(db_session, dept["id"], "off.req2.dup@test.com")
    emp_headers = auth_header(client, "off.req2.dup@test.com", "emppass123")
    _submit(client, emp_headers)

    second = client.post(
        "/api/v1/offboarding/requests",
        json={
            "reason": "resignation",
            "requested_last_working_day": _future_day(40),
        },
        headers=emp_headers,
    )
    assert second.status_code == 409


def test_submit_blocked_when_active_case_exists(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Off Req ActiveCase Dept")
    _user, emp = _emp(db_session, dept["id"], "off.req2.activecase@test.com")
    emp_headers = auth_header(client, "off.req2.activecase@test.com", "emppass123")

    case = client.post(
        "/api/v1/offboarding",
        json={
            "employee_id": emp.id,
            "reason": "resignation",
            "last_working_day": _future_day(),
        },
        headers=headers,
    )
    assert case.status_code == 201, case.text

    blocked = client.post(
        "/api/v1/offboarding/requests",
        json={
            "reason": "resignation",
            "requested_last_working_day": _future_day(45),
        },
        headers=emp_headers,
    )
    assert blocked.status_code == 409


def test_submit_rejects_past_date_and_requires_employee_profile(client, db_session):
    headers = auth_header(client)
    past = client.post(
        "/api/v1/offboarding/requests",
        json={
            "reason": "resignation",
            "requested_last_working_day": _past_day(),
        },
        headers=headers,
    )
    assert past.status_code in (400, 404)

    create_candidate_user(db_session, email="off.req2.cand@test.com", password="candpass123")
    cand = auth_header(client, "off.req2.cand@test.com", "candpass123")
    missing = client.post(
        "/api/v1/offboarding/requests",
        json={
            "reason": "resignation",
            "requested_last_working_day": _future_day(),
        },
        headers=cand,
    )
    assert missing.status_code == 404

    dept = create_department(client, name="Off Req Past Dept")
    _emp(db_session, dept["id"], "off.req2.past@test.com")
    emp_headers = auth_header(client, "off.req2.past@test.com", "emppass123")
    past_emp = client.post(
        "/api/v1/offboarding/requests",
        json={
            "reason": "resignation",
            "requested_last_working_day": _past_day(),
        },
        headers=emp_headers,
    )
    assert past_emp.status_code == 400


def test_employee_idor_and_cancel(client, db_session):
    dept = create_department(client, name="Off Req IDOR Dept")
    _emp(db_session, dept["id"], "off.req2.a@test.com")
    _emp(db_session, dept["id"], "off.req2.b@test.com")
    a = auth_header(client, "off.req2.a@test.com", "emppass123")
    b = auth_header(client, "off.req2.b@test.com", "emppass123")

    created = _submit(client, a)
    request_id = created["id"]

    forbidden = client.get(
        f"/api/v1/me/offboarding/requests/{request_id}",
        headers=b,
    )
    assert forbidden.status_code == 404

    cancelled = client.post(
        f"/api/v1/offboarding/requests/{request_id}/cancel",
        headers=a,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    cancel_again = client.post(
        f"/api/v1/offboarding/requests/{request_id}/cancel",
        headers=a,
    )
    assert cancel_again.status_code == 400


def test_hr_approve_reject_and_employee_notifications(client, db_session):
    from app.modules.offboarding.templates import DEFAULT_OFFBOARDING_TASK_TEMPLATES

    headers = auth_header(client)
    dept = create_department(client, name="Off Req Review Dept")
    user, emp = _emp(db_session, dept["id"], "off.req2.review@test.com")
    emp_headers = auth_header(client, "off.req2.review@test.com", "emppass123")

    pending = _submit(client, emp_headers)
    listed = client.get("/api/v1/offboarding/requests?status=pending", headers=headers)
    assert listed.status_code == 200
    assert any(item["id"] == pending["id"] for item in listed.json())

    approved = client.post(
        f"/api/v1/offboarding/requests/{pending['id']}/approve",
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    case = approved.json()
    assert case["status"] == "initiated"
    assert case["employee_id"] == emp.id
    assert case["reason"] == "resignation"
    assert case["last_working_day"] == pending["requested_last_working_day"]

    tasks = client.get(f"/api/v1/offboarding/{case['id']}/tasks", headers=headers)
    assert tasks.status_code == 200
    assert len(tasks.json()) == len(DEFAULT_OFFBOARDING_TASK_TEMPLATES)

    detail = client.get(f"/api/v1/offboarding/requests/{pending['id']}", headers=headers)
    assert detail.status_code == 200
    req_body = detail.json()
    assert req_body["status"] == "approved"
    assert req_body["offboarding_case_id"] == case["id"]
    assert req_body["reviewed_by"] is not None
    assert req_body["reviewed_at"] is not None

    approved_notes = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_user_id == user.id,
            Notification.type == NotificationType.OFFBOARDING_REQUEST_APPROVED,
            Notification.related_entity_id == pending["id"],
        )
        .all()
    )
    assert len(approved_notes) == 1

    user2, _emp2 = _emp(db_session, dept["id"], "off.req2.reject@test.com")
    emp2_headers = auth_header(client, "off.req2.reject@test.com", "emppass123")
    to_reject = _submit(client, emp2_headers)
    rejected = client.post(
        f"/api/v1/offboarding/requests/{to_reject['id']}/reject",
        json={"rejection_reason": "Not eligible yet"},
        headers=headers,
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["rejection_reason"] == "Not eligible yet"

    rejected_notes = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_user_id == user2.id,
            Notification.type == NotificationType.OFFBOARDING_REQUEST_REJECTED,
            Notification.related_entity_id == to_reject["id"],
        )
        .all()
    )
    assert len(rejected_notes) == 1


def test_employee_cannot_approve_request(client, db_session):
    dept = create_department(client, name="Off Req EmpApprove Dept")
    _emp(db_session, dept["id"], "off.req2.noapprove@test.com")
    emp_headers = auth_header(client, "off.req2.noapprove@test.com", "emppass123")
    created = _submit(client, emp_headers)

    forbidden = client.post(
        f"/api/v1/offboarding/requests/{created['id']}/approve",
        headers=emp_headers,
    )
    assert forbidden.status_code == 403


def test_approve_already_linked_create_case_is_conflict(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Off Req Link Dept")
    _emp(db_session, dept["id"], "off.req2.link@test.com")
    emp_headers = auth_header(client, "off.req2.link@test.com", "emppass123")

    created = _submit(client, emp_headers)
    request_id = created["id"]

    premature = client.patch(
        f"/api/v1/offboarding/requests/{request_id}/link-case",
        json={"offboarding_case_id": 1},
        headers=headers,
    )
    assert premature.status_code == 400

    approved = client.post(
        f"/api/v1/offboarding/requests/{request_id}/approve",
        headers=headers,
    )
    assert approved.status_code == 200
    case_id = approved.json()["id"]

    detail = client.get(f"/api/v1/offboarding/requests/{request_id}", headers=headers)
    assert detail.json()["offboarding_case_id"] == case_id

    again_link = client.patch(
        f"/api/v1/offboarding/requests/{request_id}/link-case",
        json={"offboarding_case_id": case_id},
        headers=headers,
    )
    assert again_link.status_code == 409

    again_create = client.post(
        f"/api/v1/offboarding/requests/{request_id}/create-case",
        headers=headers,
    )
    assert again_create.status_code == 409


def test_create_case_recovery_for_approved_unlinked_request(client, db_session):
    from datetime import UTC, datetime

    from app.modules.offboarding.templates import DEFAULT_OFFBOARDING_TASK_TEMPLATES
    from app.modules.offboarding_requests.models import (
        OffboardingRequest,
        OffboardingRequestStatus,
    )

    headers = auth_header(client)
    dept = create_department(client, name="Off Req CreateCase Dept")
    _user, emp = _emp(db_session, dept["id"], "off.req2.createcase@test.com")
    emp_headers = auth_header(client, "off.req2.createcase@test.com", "emppass123")

    created = _submit(
        client,
        emp_headers,
        reason="retirement",
        reason_details="Planned retirement",
    )
    request_id = created["id"]

    pending_create = client.post(
        f"/api/v1/offboarding/requests/{request_id}/create-case",
        headers=headers,
    )
    assert pending_create.status_code == 400

    # Simulate approved-but-unlinked recovery state.
    row = db_session.get(OffboardingRequest, request_id)
    assert row is not None
    row.status = OffboardingRequestStatus.APPROVED
    row.reviewed_at = datetime.now(UTC)
    row.offboarding_case_id = None
    db_session.commit()

    case_resp = client.post(
        f"/api/v1/offboarding/requests/{request_id}/create-case",
        headers=headers,
    )
    assert case_resp.status_code == 201, case_resp.text
    case = case_resp.json()
    assert case["status"] == "initiated"
    assert case["employee_id"] == emp.id
    assert case["reason"] == "retirement"
    assert case["reason_details"] == "Planned retirement"
    assert case["last_working_day"] == created["requested_last_working_day"]

    tasks = client.get(f"/api/v1/offboarding/{case['id']}/tasks", headers=headers)
    assert tasks.status_code == 200
    assert len(tasks.json()) == len(DEFAULT_OFFBOARDING_TASK_TEMPLATES)

    detail = client.get(f"/api/v1/offboarding/requests/{request_id}", headers=headers)
    assert detail.json()["offboarding_case_id"] == case["id"]

    duplicate = client.post(
        f"/api/v1/offboarding/requests/{request_id}/create-case",
        headers=headers,
    )
    assert duplicate.status_code == 409


def test_approve_blocked_when_active_case_exists_keeps_pending(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Off Req CreateCase Active Dept")
    _user, emp = _emp(db_session, dept["id"], "off.req2.createactive@test.com")
    emp_headers = auth_header(client, "off.req2.createactive@test.com", "emppass123")

    created = _submit(client, emp_headers)
    request_id = created["id"]

    existing = client.post(
        "/api/v1/offboarding",
        json={
            "employee_id": emp.id,
            "reason": "resignation",
            "last_working_day": _future_day(60),
        },
        headers=headers,
    )
    assert existing.status_code == 201, existing.text

    blocked = client.post(
        f"/api/v1/offboarding/requests/{request_id}/approve",
        headers=headers,
    )
    assert blocked.status_code == 409

    detail = client.get(f"/api/v1/offboarding/requests/{request_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "pending"
    assert detail.json()["offboarding_case_id"] is None


def test_employee_cannot_create_case_from_request(client, db_session):
    from datetime import UTC, datetime

    from app.modules.offboarding_requests.models import (
        OffboardingRequest,
        OffboardingRequestStatus,
    )

    headers = auth_header(client)
    dept = create_department(client, name="Off Req CreateCase Forbid Dept")
    _emp(db_session, dept["id"], "off.req2.createforbid@test.com")
    emp_headers = auth_header(client, "off.req2.createforbid@test.com", "emppass123")

    created = _submit(client, emp_headers)
    request_id = created["id"]

    row = db_session.get(OffboardingRequest, request_id)
    assert row is not None
    row.status = OffboardingRequestStatus.APPROVED
    row.reviewed_at = datetime.now(UTC)
    db_session.commit()

    forbidden = client.post(
        f"/api/v1/offboarding/requests/{request_id}/create-case",
        headers=emp_headers,
    )
    assert forbidden.status_code == 403
