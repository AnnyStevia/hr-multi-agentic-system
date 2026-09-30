"""Offboarding completion deactivates the linked application account."""

from app.modules.employees.models import Employee, EmploymentStatus
from app.modules.identity.models import User
from app.tests.helpers import auth_header, create_department, create_user_with_role
from app.tests.integration.test_offboarding_finalization import (
    _create_case,
    _emp,
    _prepare_ready_case,
    _to_pending_clearance,
)


def test_complete_deactivates_employee_account(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Deact Complete")
    user, emp = _emp(db_session, dept["id"], "deact.complete@test.com")
    case = _prepare_ready_case(client, headers, emp.id)

    done = client.post(f"/api/v1/offboarding/{case['id']}/complete", headers=headers)
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "completed"

    db_session.refresh(user)
    db_session.refresh(emp)
    assert user.is_active is False
    assert emp.employment_status == EmploymentStatus.INACTIVE


def test_incomplete_complete_does_not_deactivate(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Deact Incomplete")
    user, emp = _emp(db_session, dept["id"], "deact.incomplete@test.com")
    case = _create_case(client, headers, emp.id)
    _to_pending_clearance(client, headers, case["id"])
    # Clearance left pending; checklist incomplete

    blocked = client.post(f"/api/v1/offboarding/{case['id']}/complete", headers=headers)
    assert blocked.status_code == 400

    db_session.refresh(user)
    db_session.refresh(emp)
    assert user.is_active is True
    assert emp.employment_status == EmploymentStatus.ACTIVE


def test_employee_cannot_complete_own_offboarding(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Deact Emp Forbid")
    _user, emp = _emp(db_session, dept["id"], "deact.self@test.com")
    case = _prepare_ready_case(client, headers, emp.id)

    emp_headers = auth_header(client, email="deact.self@test.com", password="emppass123")
    denied = client.post(
        f"/api/v1/offboarding/{case['id']}/complete",
        headers=emp_headers,
    )
    assert denied.status_code == 403


def test_unauthenticated_cannot_complete(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Deact Unauth")
    _user, emp = _emp(db_session, dept["id"], "deact.unauth@test.com")
    case = _prepare_ready_case(client, headers, emp.id)

    denied = client.post(f"/api/v1/offboarding/{case['id']}/complete")
    assert denied.status_code == 401


def test_candidate_cannot_trigger_deactivation(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Deact Cand")
    _user, emp = _emp(db_session, dept["id"], "deact.cand.target@test.com")
    case = _prepare_ready_case(client, headers, emp.id)

    create_user_with_role(
        db_session,
        email="deact.cand@test.com",
        password="candpass123",
        role_name="candidate",
    )
    cand_headers = auth_header(client, email="deact.cand@test.com", password="candpass123")
    denied = client.post(
        f"/api/v1/offboarding/{case['id']}/complete",
        headers=cand_headers,
    )
    assert denied.status_code == 403


def test_only_case_employee_account_is_deactivated(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Deact Other Intact")
    target_user, target_emp = _emp(db_session, dept["id"], "deact.target@test.com")
    other_user, _other_emp = _emp(db_session, dept["id"], "deact.other@test.com")
    case = _prepare_ready_case(client, headers, target_emp.id)

    done = client.post(f"/api/v1/offboarding/{case['id']}/complete", headers=headers)
    assert done.status_code == 200, done.text

    db_session.refresh(target_user)
    db_session.refresh(other_user)
    assert target_user.is_active is False
    assert other_user.is_active is True


def test_historical_employee_and_user_rows_remain(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Deact History")
    user, emp = _emp(db_session, dept["id"], "deact.history@test.com")
    user_id, emp_id = user.id, emp.id
    case = _prepare_ready_case(client, headers, emp.id)

    assert client.post(
        f"/api/v1/offboarding/{case['id']}/complete", headers=headers
    ).status_code == 200

    assert db_session.get(User, user_id) is not None
    assert db_session.get(Employee, emp_id) is not None


def test_inactive_employee_cannot_login(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Deact Login")
    user, emp = _emp(db_session, dept["id"], "deact.login@test.com")
    case = _prepare_ready_case(client, headers, emp.id)
    assert client.post(
        f"/api/v1/offboarding/{case['id']}/complete", headers=headers
    ).status_code == 200

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "deact.login@test.com", "password": "emppass123"},
    )
    assert login.status_code == 401


def test_inactive_employee_cannot_use_self_service_or_ai(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Deact SelfSvc")
    user, emp = _emp(db_session, dept["id"], "deact.selfsvc@test.com")
    case = _prepare_ready_case(client, headers, emp.id)

    # Token issued while still active
    emp_headers = auth_header(client, email="deact.selfsvc@test.com", password="emppass123")

    assert client.post(
        f"/api/v1/offboarding/{case['id']}/complete", headers=headers
    ).status_code == 200

    me = client.get("/api/v1/me/offboarding", headers=emp_headers)
    assert me.status_code == 401

    ai = client.post(
        "/api/v1/ai/assistant/ask",
        json={"message": "What is my leave balance?"},
        headers=emp_headers,
    )
    assert ai.status_code == 401


def test_hr_can_still_read_completed_case(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Deact Hr Read")
    _user, emp = _emp(db_session, dept["id"], "deact.hrread@test.com")
    case = _prepare_ready_case(client, headers, emp.id)
    assert client.post(
        f"/api/v1/offboarding/{case['id']}/complete", headers=headers
    ).status_code == 200

    detail = client.get(f"/api/v1/offboarding/{case['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "completed"
    assert detail.json()["employee"]["full_name"]


def test_repeated_complete_rejected(client, db_session):
    headers = auth_header(client)
    dept = create_department(client, name="Deact Repeat")
    user, emp = _emp(db_session, dept["id"], "deact.repeat@test.com")
    case = _prepare_ready_case(client, headers, emp.id)

    first = client.post(f"/api/v1/offboarding/{case['id']}/complete", headers=headers)
    assert first.status_code == 200
    again = client.post(f"/api/v1/offboarding/{case['id']}/complete", headers=headers)
    assert again.status_code == 400

    db_session.refresh(user)
    assert user.is_active is False


def test_auth_service_deactivate_user_flush_only(db_session):
    from app.modules.identity.service import AuthService

    user = create_user_with_role(
        db_session,
        email="deact.auth.svc@test.com",
        password="pass12345",
        role_name="employee",
    )
    assert user.is_active is True

    AuthService(db_session).deactivate_user(user.id)
    db_session.refresh(user)
    assert user.is_active is False
