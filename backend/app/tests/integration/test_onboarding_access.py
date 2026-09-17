from app.modules.identity.models import User
from app.modules.onboarding.models import Onboarding, OnboardingStatus
from app.tests.helpers import auth_header, create_user_with_role
from app.tests.integration.test_onboarding import _hire


def test_hired_candidate_receives_employee_role_and_keeps_candidate(client, db_session):
    _application, _job, candidate_headers, _headers, body = _hire(
        client, db_session, email="access.hire.role@test.com"
    )
    me = client.get("/api/v1/auth/me", headers=candidate_headers)
    assert me.status_code == 200, me.text
    roles = {role["name"] for role in me.json()["roles"]}
    assert "employee" in roles
    assert "candidate" in roles
    assert me.json()["onboarding_status"] == "in_progress"

    user = db_session.query(User).filter(User.email == "access.hire.role@test.com").one()
    role_names = {ur.role.name for ur in user.user_roles}
    assert role_names >= {"employee", "candidate"}
    assert body["hired_employee_id"] is not None


def test_me_onboarding_status_unlocks_employee_portal_expectation(client, db_session):
    """Hired dual-role users must expose employee + onboarding_status for the portal gate."""
    _application, _job, candidate_headers, _headers, _body = _hire(
        client, db_session, email="access.portal.gate@test.com"
    )
    me = client.get("/api/v1/auth/me", headers=candidate_headers).json()
    assert me["onboarding_status"] == "in_progress"
    assert {role["name"] for role in me["roles"]} >= {"employee", "candidate"}


def test_hr_can_complete_onboarding_and_repeat_is_rejected(client, db_session):
    _application, _job, candidate_headers, headers, body = _hire(
        client, db_session, email="access.complete@test.com"
    )
    onboarding = (
        db_session.query(Onboarding)
        .filter(Onboarding.employee_id == body["hired_employee_id"])
        .one()
    )

    first = client.post(f"/api/v1/onboarding/{onboarding.id}/complete", headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "completed"
    assert first.json()["completed_at"] is not None

    second = client.post(f"/api/v1/onboarding/{onboarding.id}/complete", headers=headers)
    assert second.status_code == 400

    me = client.get("/api/v1/auth/me", headers=candidate_headers)
    assert me.json()["onboarding_status"] == "completed"


def test_unauthorized_cannot_complete_onboarding(client, db_session):
    _application, _job, candidate_headers, _headers, body = _hire(
        client, db_session, email="access.complete.unauth@test.com"
    )
    onboarding = (
        db_session.query(Onboarding)
        .filter(Onboarding.employee_id == body["hired_employee_id"])
        .one()
    )

    assert (
        client.post(
            f"/api/v1/onboarding/{onboarding.id}/complete",
            headers=candidate_headers,
        ).status_code
        == 403
    )

    create_user_with_role(
        db_session,
        email="access.plain.emp@test.com",
        password="emppass123",
        role_name="employee",
    )
    emp_headers = auth_header(client, email="access.plain.emp@test.com", password="emppass123")
    assert (
        client.post(
            f"/api/v1/onboarding/{onboarding.id}/complete",
            headers=emp_headers,
        ).status_code
        == 403
    )


def test_in_progress_employee_is_restricted_to_onboarding(client, db_session):
    _application, _job, candidate_headers, _headers, _body = _hire(
        client, db_session, email="access.gate.inprogress@test.com"
    )

    assert client.get("/api/v1/me/onboarding", headers=candidate_headers).status_code == 200
    assert client.get("/api/v1/careers/jobs", headers=candidate_headers).status_code == 403
    assert client.get("/api/v1/me/employee-home", headers=candidate_headers).status_code == 403


def test_completed_employee_regains_normal_access(client, db_session):
    _application, _job, candidate_headers, headers, body = _hire(
        client, db_session, email="access.gate.done@test.com"
    )
    onboarding = (
        db_session.query(Onboarding)
        .filter(Onboarding.employee_id == body["hired_employee_id"])
        .one()
    )
    assert (
        client.post(f"/api/v1/onboarding/{onboarding.id}/complete", headers=headers).status_code
        == 200
    )

    assert client.get("/api/v1/careers/jobs", headers=candidate_headers).status_code == 200
    assert client.get("/api/v1/me/employee-home", headers=candidate_headers).status_code == 200
    assert (
        db_session.query(Onboarding).filter(Onboarding.id == onboarding.id).one().status
        == OnboardingStatus.COMPLETED
    )


def test_pure_candidate_careers_unaffected(client, db_session):
    create_user_with_role(
        db_session,
        email="access.pure.cand@test.com",
        password="candpass123",
        role_name="candidate",
    )
    headers = auth_header(client, email="access.pure.cand@test.com", password="candpass123")
    response = client.get("/api/v1/careers/jobs", headers=headers)
    assert response.status_code == 200
