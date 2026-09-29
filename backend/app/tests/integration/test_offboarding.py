from datetime import date, timedelta

from app.modules.employees.models import Employee, EmploymentStatus
from app.modules.identity.models import User
from app.tests.helpers import (
    auth_header,
    create_candidate_user,
    create_department,
    create_user_with_role,
)
from app.tests.integration.test_organization import _create_linked_employee


def _future_day(days: int = 30) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _create_case(client, headers, employee_id: int, **extra) -> dict:
    payload = {
        "employee_id": employee_id,
        "reason": "resignation",
        "reason_details": "Personal reasons",
        "last_working_day": _future_day(),
    }
    payload.update(extra)
    response = client.post("/api/v1/offboarding", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _emp(db_session, department_id: int, email: str, **kwargs):
    return _create_linked_employee(
        db_session,
        email=email,
        password="emppass123",
        department_id=department_id,
        **kwargs,
    )


def test_hr_and_admin_can_create_offboarding(client, db_session):
    dept = create_department(client, name="Offboarding Create Dept")
    create_user_with_role(
        db_session, email="hr.off.create@test.com", password="hrpass123", role_name="hr"
    )
    hr = auth_header(client, "hr.off.create@test.com", "hrpass123")
    admin = auth_header(client)

    _u1, emp1 = _emp(db_session, dept["id"], "off.hire.create@test.com")
    created = _create_case(client, hr, emp1.id)
    assert created["status"] == "initiated"
    assert created["employee_id"] == emp1.id
    assert created["reason"] == "resignation"
    assert created["employee"]["full_name"]
    assert created["created_by"] is not None
    assert created["completed_at"] is None

    db_session.refresh(emp1)
    assert emp1.employment_status == EmploymentStatus.ACTIVE

    _u2, emp2 = _emp(db_session, dept["id"], "off.hire.admin@test.com")
    admin_created = _create_case(
        client,
        admin,
        emp2.id,
        reason="retirement",
        reason_details=None,
    )
    assert admin_created["reason"] == "retirement"
    assert admin_created["status"] == "initiated"


def test_create_rejects_nonexistent_inactive_and_past_date(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Offboarding Reject Dept")

    missing = client.post(
        "/api/v1/offboarding",
        json={
            "employee_id": 999999,
            "reason": "resignation",
            "last_working_day": _future_day(),
        },
        headers=headers,
    )
    assert missing.status_code == 404

    _u, emp = _emp(db_session, dept["id"], "off.inactive@test.com")
    deactivated = client.patch(
        f"/api/v1/employees/{emp.id}/deactivate",
        headers=headers,
    )
    assert deactivated.status_code == 200, deactivated.text

    inactive = client.post(
        "/api/v1/offboarding",
        json={
            "employee_id": emp.id,
            "reason": "termination",
            "last_working_day": _future_day(),
        },
        headers=headers,
    )
    assert inactive.status_code == 400

    _u2, emp2 = _emp(db_session, dept["id"], "off.pastday@test.com")
    past = client.post(
        "/api/v1/offboarding",
        json={
            "employee_id": emp2.id,
            "reason": "resignation",
            "last_working_day": (date.today() - timedelta(days=1)).isoformat(),
        },
        headers=headers,
    )
    assert past.status_code == 400


def test_duplicate_active_rejected_historical_allowed(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Offboarding Dup Dept")
    _u, emp = _emp(db_session, dept["id"], "off.dup@test.com")

    first = _create_case(client, headers, emp.id)
    dup = client.post(
        "/api/v1/offboarding",
        json={
            "employee_id": emp.id,
            "reason": "other",
            "last_working_day": _future_day(45),
        },
        headers=headers,
    )
    assert dup.status_code == 409

    cancelled = client.post(
        f"/api/v1/offboarding/{first['id']}/cancel",
        headers=headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    second = _create_case(client, headers, emp.id, reason="end_of_contract")
    assert second["status"] == "initiated"

    client.post(f"/api/v1/offboarding/{second['id']}/start", headers=headers)
    client.post(f"/api/v1/offboarding/{second['id']}/pending-clearance", headers=headers)
    completed = client.post(f"/api/v1/offboarding/{second['id']}/complete", headers=headers)
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["completed_at"] is not None

    third = _create_case(client, headers, emp.id, reason="other")
    assert third["status"] == "initiated"


def test_lifecycle_transitions_and_rejects(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Offboarding Life Dept")
    _u, emp = _emp(db_session, dept["id"], "off.life@test.com")
    case = _create_case(client, headers, emp.id)
    case_id = case["id"]

    assert (
        client.post(f"/api/v1/offboarding/{case_id}/pending-clearance", headers=headers).status_code
        == 400
    )
    assert client.post(f"/api/v1/offboarding/{case_id}/complete", headers=headers).status_code == 400

    started = client.post(f"/api/v1/offboarding/{case_id}/start", headers=headers)
    assert started.status_code == 200
    assert started.json()["status"] == "in_progress"

    assert client.post(f"/api/v1/offboarding/{case_id}/complete", headers=headers).status_code == 400

    pending = client.post(f"/api/v1/offboarding/{case_id}/pending-clearance", headers=headers)
    assert pending.status_code == 200
    assert pending.json()["status"] == "pending_clearance"

    back = client.post(f"/api/v1/offboarding/{case_id}/start", headers=headers)
    assert back.status_code == 200
    assert back.json()["status"] == "in_progress"

    client.post(f"/api/v1/offboarding/{case_id}/pending-clearance", headers=headers)
    done = client.post(f"/api/v1/offboarding/{case_id}/complete", headers=headers)
    assert done.status_code == 200
    assert done.json()["status"] == "completed"

    for action in ("start", "pending-clearance", "complete", "cancel"):
        assert (
            client.post(f"/api/v1/offboarding/{case_id}/{action}", headers=headers).status_code
            == 400
        )


def test_cancel_from_each_active_status(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Offboarding Cancel Dept")

    def _case(email: str) -> int:
        _u, emp = _emp(db_session, dept["id"], email)
        return _create_case(client, headers, emp.id)["id"]

    initiated_id = _case("off.cancel.init@test.com")
    assert (
        client.post(f"/api/v1/offboarding/{initiated_id}/cancel", headers=headers).json()["status"]
        == "cancelled"
    )

    progress_id = _case("off.cancel.prog@test.com")
    client.post(f"/api/v1/offboarding/{progress_id}/start", headers=headers)
    assert (
        client.post(f"/api/v1/offboarding/{progress_id}/cancel", headers=headers).json()["status"]
        == "cancelled"
    )

    clearance_id = _case("off.cancel.clear@test.com")
    client.post(f"/api/v1/offboarding/{clearance_id}/start", headers=headers)
    client.post(f"/api/v1/offboarding/{clearance_id}/pending-clearance", headers=headers)
    assert (
        client.post(f"/api/v1/offboarding/{clearance_id}/cancel", headers=headers).json()["status"]
        == "cancelled"
    )

    assert (
        client.post(f"/api/v1/offboarding/{clearance_id}/start", headers=headers).status_code == 400
    )


def test_authorization_matrix(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Offboarding Auth Dept")
    emp_user, emp = _emp(db_session, dept["id"], "off.auth.emp@test.com")
    emp_headers = auth_header(client, "off.auth.emp@test.com", "emppass123")
    case = _create_case(client, headers, emp.id)

    create_user_with_role(
        db_session, email="mgr.off@test.com", password="mgrpass123", role_name="manager"
    )
    mgr = auth_header(client, "mgr.off@test.com", "mgrpass123")
    create_candidate_user(db_session, email="cand.off@test.com", password="candpass123")
    cand = auth_header(client, "cand.off@test.com", "candpass123")

    payload = {
        "employee_id": emp.id,
        "reason": "resignation",
        "last_working_day": _future_day(),
    }
    for blocked in (emp_headers, mgr, cand):
        assert client.post("/api/v1/offboarding", json=payload, headers=blocked).status_code == 403
        assert client.get("/api/v1/offboarding", headers=blocked).status_code == 403
        assert client.get(f"/api/v1/offboarding/{case['id']}", headers=blocked).status_code == 403
        assert (
            client.post(f"/api/v1/offboarding/{case['id']}/start", headers=blocked).status_code
            == 403
        )
        assert (
            client.post(f"/api/v1/offboarding/{case['id']}/cancel", headers=blocked).status_code
            == 403
        )


def test_employee_self_access_and_idor(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Offboarding Self Dept")
    _u1, emp = _emp(db_session, dept["id"], "off.self@test.com")
    emp_headers = auth_header(client, "off.self@test.com", "emppass123")
    case = _create_case(client, headers, emp.id)

    _u2, other = _emp(db_session, dept["id"], "off.other@test.com")
    other_headers = auth_header(client, "off.other@test.com", "emppass123")
    other_case = _create_case(client, headers, other.id)

    mine = client.get("/api/v1/me/offboarding", headers=emp_headers)
    assert mine.status_code == 200, mine.text
    assert len(mine.json()) == 1
    item = mine.json()[0]
    assert item["id"] == case["id"]
    assert item["status"] == "initiated"
    assert item["reason"] == "resignation"
    assert "reason_details" not in item
    assert "created_by" not in item

    other_mine = client.get("/api/v1/me/offboarding", headers=other_headers)
    assert other_mine.status_code == 200
    assert other_mine.json()[0]["id"] == other_case["id"]
    assert other_mine.json()[0]["id"] != case["id"]

    assert client.get(f"/api/v1/offboarding/{case['id']}", headers=emp_headers).status_code == 403
    assert (
        client.post(f"/api/v1/offboarding/{case['id']}/cancel", headers=emp_headers).status_code
        == 403
    )


def test_hr_list_filters_and_detail(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Offboarding List Dept")
    _u1, emp1 = _emp(db_session, dept["id"], "off.list1@test.com")
    _u2, emp2 = _emp(db_session, dept["id"], "off.list2@test.com")
    case1 = _create_case(client, headers, emp1.id)
    case2 = _create_case(client, headers, emp2.id, reason="termination")
    client.post(f"/api/v1/offboarding/{case2['id']}/start", headers=headers)

    listing = client.get("/api/v1/offboarding", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()) >= 2

    by_status = client.get("/api/v1/offboarding?status=initiated", headers=headers)
    assert by_status.status_code == 200
    assert all(item["status"] == "initiated" for item in by_status.json())
    assert any(item["id"] == case1["id"] for item in by_status.json())

    by_emp = client.get(
        f"/api/v1/offboarding?employee_id={emp1.id}",
        headers=headers,
    )
    assert by_emp.status_code == 200
    assert len(by_emp.json()) == 1
    assert by_emp.json()[0]["id"] == case1["id"]

    detail = client.get(f"/api/v1/offboarding/{case1['id']}", headers=headers)
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["reason_details"] == "Personal reasons"
    assert payload["employee"]["email"]
    assert payload["created_by"]["email"]


def test_no_status_patch_and_create_preserves_employment(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Offboarding Patch Dept")
    _u, emp = _emp(db_session, dept["id"], "off.nopath@test.com")
    case = _create_case(client, headers, emp.id)

    patched = client.patch(
        f"/api/v1/offboarding/{case['id']}",
        json={"status": "completed"},
        headers=headers,
    )
    assert patched.status_code in {404, 405, 422}

    db_session.refresh(emp)
    assert emp.employment_status == EmploymentStatus.ACTIVE
    user = db_session.query(User).filter(User.id == emp.user_id).one()
    assert user.is_active is True
