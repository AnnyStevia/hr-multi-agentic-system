from app.modules.onboarding.models import Onboarding, OnboardingStatus
from app.modules.employees.repository import EmployeeRepository
from app.modules.onboarding.repository import OnboardingRepository
from app.modules.onboarding.service import OnboardingService
from app.shared.exceptions import AppException
from app.tests.helpers import auth_header, create_candidate_user, create_user_with_role
from app.tests.integration.test_interview_outcomes import _complete, _schedule_interview


def _hire(client, db_session, *, email: str):
    application, job, candidate_headers, headers, interview = _schedule_interview(
        client, db_session, email=email
    )
    completed = _complete(client, headers, interview["id"])
    response = client.post(
        f"/api/v1/interviews/{completed['id']}/outcome",
        json={"outcome": "hired"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["hired_employee_id"] is not None
    return application, job, candidate_headers, headers, body


def test_hired_employee_gets_in_progress_onboarding(client, db_session):
    _application, _job, candidate_headers, _headers, body = _hire(
        client, db_session, email="onboard.hire@test.com"
    )
    employee_id = body["hired_employee_id"]

    onboarding = (
        db_session.query(Onboarding).filter(Onboarding.employee_id == employee_id).one()
    )
    assert onboarding.status == OnboardingStatus.IN_PROGRESS
    assert onboarding.started_at is not None
    assert onboarding.completed_at is None

    me = client.get("/api/v1/me/onboarding", headers=candidate_headers)
    assert me.status_code == 200, me.text
    payload = me.json()
    assert payload["employee_id"] == employee_id
    assert payload["status"] == "in_progress"
    assert payload["started_at"] is not None


def test_duplicate_onboarding_is_prevented(client, db_session):
    _application, _job, _candidate_headers, _headers, body = _hire(
        client, db_session, email="onboard.dup@test.com"
    )
    employee_id = body["hired_employee_id"]
    service = OnboardingService(OnboardingRepository(db_session), EmployeeRepository(db_session))

    try:
        service.create_for_employee(employee_id)
        assert False, "Expected duplicate onboarding to raise"
    except AppException as exc:
        assert exc.status_code == 409

    count = db_session.query(Onboarding).filter(Onboarding.employee_id == employee_id).count()
    assert count == 1


def test_employee_cannot_access_another_employees_onboarding(client, db_session):
    _application, _job, candidate_headers, headers, body = _hire(
        client, db_session, email="onboard.owner@test.com"
    )
    employee_id = body["hired_employee_id"]
    onboarding = (
        db_session.query(Onboarding).filter(Onboarding.employee_id == employee_id).one()
    )

    other = create_candidate_user(
        db_session, email="onboard.other@test.com", password="otherpass123"
    )
    other_headers = auth_header(client, email=other.email, password="otherpass123")

    me = client.get("/api/v1/me/onboarding", headers=other_headers)
    assert me.status_code == 404

    staff = client.get(f"/api/v1/onboarding/{onboarding.id}", headers=other_headers)
    assert staff.status_code == 403

    by_employee = client.get(
        f"/api/v1/employees/{employee_id}/onboarding", headers=other_headers
    )
    assert by_employee.status_code == 403

    # Owner still reaches own record; other user never sees owner payload via /me
    owner = client.get("/api/v1/me/onboarding", headers=candidate_headers)
    assert owner.status_code == 200
    assert owner.json()["id"] == onboarding.id


def test_hr_and_admin_can_retrieve_onboarding(client, db_session):
    _application, _job, _candidate_headers, headers, body = _hire(
        client, db_session, email="onboard.hr@test.com"
    )
    employee_id = body["hired_employee_id"]
    onboarding = (
        db_session.query(Onboarding).filter(Onboarding.employee_id == employee_id).one()
    )

    by_id = client.get(f"/api/v1/onboarding/{onboarding.id}", headers=headers)
    assert by_id.status_code == 200, by_id.text
    assert by_id.json()["employee_id"] == employee_id

    by_employee = client.get(f"/api/v1/employees/{employee_id}/onboarding", headers=headers)
    assert by_employee.status_code == 200, by_employee.text
    assert by_employee.json()["id"] == onboarding.id

    admin_headers = auth_header(client)
    admin_resp = client.get(f"/api/v1/onboarding/{onboarding.id}", headers=admin_headers)
    assert admin_resp.status_code == 200, admin_resp.text


def test_role_employee_without_onboarding_perm_cannot_use_staff_routes(client, db_session):
    _application, _job, _candidate_headers, _headers, body = _hire(
        client, db_session, email="onboard.staffgate@test.com"
    )
    employee_id = body["hired_employee_id"]
    onboarding = (
        db_session.query(Onboarding).filter(Onboarding.employee_id == employee_id).one()
    )

    create_user_with_role(
        db_session,
        email="onboard.plain.employee@test.com",
        password="emppass123",
        role_name="employee",
    )
    emp_headers = auth_header(
        client, email="onboard.plain.employee@test.com", password="emppass123"
    )

    assert client.get(f"/api/v1/onboarding/{onboarding.id}", headers=emp_headers).status_code == 403
    assert (
        client.get(f"/api/v1/employees/{employee_id}/onboarding", headers=emp_headers).status_code
        == 403
    )


def test_unauthenticated_cannot_get_onboarding(client, db_session):
    response = client.get("/api/v1/me/onboarding")
    assert response.status_code == 401


def test_hr_can_list_onboardings_with_task_counts(client, db_session):
    _application, _job, _candidate_headers, headers, body = _hire(
        client, db_session, email="onboard.list@test.com"
    )
    onboarding = (
        db_session.query(Onboarding)
        .filter(Onboarding.employee_id == body["hired_employee_id"])
        .one()
    )

    created = client.post(
        f"/api/v1/onboarding/{onboarding.id}/tasks",
        json={"title": "Setup laptop"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    completed = client.patch(
        f"/api/v1/onboarding/tasks/{task_id}",
        json={"status": "completed"},
        headers=headers,
    )
    assert completed.status_code == 200, completed.text

    client.post(
        f"/api/v1/onboarding/{onboarding.id}/tasks",
        json={"title": "Sign contract"},
        headers=headers,
    )

    listing = client.get("/api/v1/onboarding", headers=headers)
    assert listing.status_code == 200, listing.text
    items = listing.json()
    assert len(items) == 1
    row = items[0]
    assert row["employee_name"]
    assert row["position"]
    assert row["status"] == "in_progress"
    assert row["completed_tasks_count"] == 1
    assert row["total_tasks_count"] == 2


def test_candidate_cannot_list_onboardings(client, db_session):
    _application, _job, candidate_headers, _headers, _body = _hire(
        client, db_session, email="onboard.list.cand@test.com"
    )
    response = client.get("/api/v1/onboarding", headers=candidate_headers)
    assert response.status_code == 403


def test_onboarding_list_is_empty_when_none_exist(client, db_session):
    headers = auth_header(client)
    response = client.get("/api/v1/onboarding", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == []
