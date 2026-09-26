from app.modules.employees.models import Employee
from app.modules.identity.models import Candidate
from app.modules.interviews.models import Interview, InterviewStatus
from app.modules.onboarding.models import Onboarding, OnboardingStatus
from app.modules.recruitment.models import Application, ApplicationStatus
from app.tests.helpers import auth_header, create_user_with_role
from app.tests.integration.test_application_review import _submit_application
from app.tests.integration.test_interview_invitations import (
    PRIMARY_HEADERS_BY_INTERVIEW,
    _create_invitation,
    _create_linked_panelist,
    _invite_payload,
)
from uuid import uuid4


def _complete_payload(**overrides):
    payload = {
        "tech_knowledge": 4,
        "communication": 4,
        "problem_solving": 4,
        "relevant_experience": 4,
        "strengths": "Strong technical foundation.",
        "weaknesses": "Could improve system design depth.",
        "additional_comments": "Strong communication skills.",
        "recommendation": "proceed",
    }
    payload.update(overrides)
    return payload


def _schedule_interview(client, db_session, *, email: str):
    application, job, candidate_headers, _storage = _submit_application(
        client, db_session, email=email
    )
    interview, headers, primary_headers = _create_invitation(client, db_session, application["id"])
    slot_id = interview["slots"][0]["id"]
    confirmed = client.post(
        f"/api/v1/careers/interviews/{interview['id']}/confirm",
        json={"slot_id": slot_id},
        headers=candidate_headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "scheduled"
    body = confirmed.json()
    PRIMARY_HEADERS_BY_INTERVIEW[body["id"]] = primary_headers
    return application, job, candidate_headers, headers, body


def _complete(client, _headers, interview_id: int, **overrides):
    primary_headers = PRIMARY_HEADERS_BY_INTERVIEW.get(interview_id, _headers)
    response = client.post(
        f"/api/v1/me/interviews/{interview_id}/complete",
        json=_complete_payload(**overrides),
        headers=primary_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_primary_can_complete_scheduled_interview(client, db_session):
    _application, _job, _candidate_headers, headers, interview = _schedule_interview(
        client, db_session, email="outcome.complete@test.com"
    )
    body = _complete(
        client,
        headers,
        interview["id"],
        additional_comments="Good technical answers.",
    )
    assert body["status"] == "completed"
    assert body["feedback"] == "Good technical answers."
    assert body["evaluation"]["additional_comments"] == "Good technical answers."
    assert body["evaluation"]["recommendation"] == "proceed"
    assert body["completed_at"] is not None
    assert body["outcome"] is None

    row = db_session.query(Interview).filter(Interview.id == interview["id"]).one()
    assert row.status == InterviewStatus.COMPLETED
    assert row.feedback == "Good technical answers."
    assert row.recommendation.value == "proceed"

    hr_attempt = client.patch(
        f"/api/v1/interviews/{interview['id']}/complete",
        json={"feedback": "Nope"},
        headers=headers,
    )
    assert hr_attempt.status_code == 403


def test_primary_cannot_complete_proposed_interview(client, db_session):
    application, _job, _candidate_headers, _storage = _submit_application(
        client, db_session, email="outcome.proposed@test.com"
    )
    interview, _headers, primary_headers = _create_invitation(client, db_session, application["id"])

    response = client.post(
        f"/api/v1/me/interviews/{interview['id']}/complete",
        json=_complete_payload(),
        headers=primary_headers,
    )
    assert response.status_code == 400


def test_primary_cannot_complete_already_completed_interview(client, db_session):
    _application, _job, _candidate_headers, headers, interview = _schedule_interview(
        client, db_session, email="outcome.twice@test.com"
    )
    _complete(client, headers, interview["id"])
    primary_headers = PRIMARY_HEADERS_BY_INTERVIEW[interview["id"]]
    second = client.post(
        f"/api/v1/me/interviews/{interview['id']}/complete",
        json=_complete_payload(additional_comments="Again"),
        headers=primary_headers,
    )
    assert second.status_code == 400


def test_unauthorized_cannot_complete_interview(client, db_session):
    _application, _job, _candidate_headers, _headers, interview = _schedule_interview(
        client, db_session, email="outcome.unauth@test.com"
    )
    response = client.post(
        f"/api/v1/me/interviews/{interview['id']}/complete",
        json=_complete_payload(),
    )
    assert response.status_code == 401


def test_candidate_cannot_complete_interview(client, db_session):
    _application, _job, candidate_headers, _headers, interview = _schedule_interview(
        client, db_session, email="outcome.cand.complete@test.com"
    )
    response = client.post(
        f"/api/v1/me/interviews/{interview['id']}/complete",
        json=_complete_payload(),
        headers=candidate_headers,
    )
    assert response.status_code in (403, 404)


def test_feedback_is_persisted(client, db_session):
    _application, _job, _candidate_headers, headers, interview = _schedule_interview(
        client, db_session, email="outcome.feedback@test.com"
    )
    _complete(
        client,
        headers,
        interview["id"],
        additional_comments="Clear and concise answers.",
        strengths="Clear answers.",
    )
    detail = client.get(f"/api/v1/interviews/{interview['id']}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["feedback"] == "Clear and concise answers."
    assert body["evaluation"]["additional_comments"] == "Clear and concise answers."
    assert body["evaluation"]["tech_knowledge"] == 4
    assert body["evaluation"]["recommendation"] == "proceed"


def test_hr_can_record_rejected_outcome(client, db_session):
    application, _job, _candidate_headers, headers, interview = _schedule_interview(
        client, db_session, email="outcome.reject@test.com"
    )
    completed = _complete(client, headers, interview["id"])
    response = client.post(
        f"/api/v1/interviews/{completed['id']}/outcome",
        json={"outcome": "rejected"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["outcome"] == "rejected"

    app_row = db_session.query(Application).filter(Application.id == application["id"]).one()
    assert app_row.status == ApplicationStatus.REJECTED


def test_hr_can_record_another_interview_without_creating_interview(client, db_session):
    application, _job, _candidate_headers, headers, interview = _schedule_interview(
        client, db_session, email="outcome.another@test.com"
    )
    completed = _complete(client, headers, interview["id"])
    before_count = db_session.query(Interview).filter(Interview.application_id == application["id"]).count()

    response = client.post(
        f"/api/v1/interviews/{completed['id']}/outcome",
        json={"outcome": "another_interview"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["outcome"] == "another_interview"

    app_row = db_session.query(Application).filter(Application.id == application["id"]).one()
    assert app_row.status == ApplicationStatus.SHORTLISTED
    after_count = db_session.query(Interview).filter(Interview.application_id == application["id"]).count()
    assert after_count == before_count

    primary_id, _ = _create_linked_panelist(
        client, db_session, email=f"another.primary.{uuid4().hex[:8]}@test.com"
    )
    invite_again = client.post(
        f"/api/v1/interviews/applications/{application['id']}",
        json=_invite_payload(primary_employee_id=primary_id),
        headers=headers,
    )
    assert invite_again.status_code == 201, invite_again.text


def test_hr_can_record_hired_outcome_and_create_employee(client, db_session):
    application, job, _candidate_headers, headers, interview = _schedule_interview(
        client, db_session, email="outcome.hire@test.com"
    )
    completed = _complete(client, headers, interview["id"])
    response = client.post(
        f"/api/v1/interviews/{completed['id']}/outcome",
        json={"outcome": "hired"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcome"] == "hired"
    assert body["hired_employee_id"] is not None

    app_row = db_session.query(Application).filter(Application.id == application["id"]).one()
    assert app_row.status == ApplicationStatus.HIRED

    employee = db_session.query(Employee).filter(Employee.id == body["hired_employee_id"]).one()
    assert employee.email == "outcome.hire@test.com"
    assert employee.user_id is not None
    assert employee.position == job["title"]
    assert employee.department_id == job["department_id"]

    onboarding = (
        db_session.query(Onboarding)
        .filter(Onboarding.employee_id == employee.id)
        .one()
    )
    assert onboarding.status == OnboardingStatus.IN_PROGRESS
    assert onboarding.started_at is not None


def test_hiring_twice_does_not_create_duplicate_employees(client, db_session):
    application, _job, _candidate_headers, headers, interview = _schedule_interview(
        client, db_session, email="outcome.hire.twice@test.com"
    )
    completed = _complete(client, headers, interview["id"])
    first = client.post(
        f"/api/v1/interviews/{completed['id']}/outcome",
        json={"outcome": "hired"},
        headers=headers,
    )
    assert first.status_code == 200, first.text
    employee_id = first.json()["hired_employee_id"]

    second = client.post(
        f"/api/v1/interviews/{completed['id']}/outcome",
        json={"outcome": "hired"},
        headers=headers,
    )
    assert second.status_code == 409

    count = (
        db_session.query(Employee)
        .filter(Employee.email == "outcome.hire.twice@test.com")
        .count()
    )
    assert count == 1
    assert db_session.query(Employee).filter(Employee.id == employee_id).one()


def test_candidate_cannot_set_outcome(client, db_session):
    _application, _job, candidate_headers, headers, interview = _schedule_interview(
        client, db_session, email="outcome.cand.outcome@test.com"
    )
    completed = _complete(client, headers, interview["id"])
    response = client.post(
        f"/api/v1/interviews/{completed['id']}/outcome",
        json={"outcome": "hired"},
        headers=candidate_headers,
    )
    assert response.status_code == 403


def test_invalid_outcome_is_rejected(client, db_session):
    _application, _job, _candidate_headers, headers, interview = _schedule_interview(
        client, db_session, email="outcome.invalid@test.com"
    )
    completed = _complete(client, headers, interview["id"])
    response = client.post(
        f"/api/v1/interviews/{completed['id']}/outcome",
        json={"outcome": "maybe"},
        headers=headers,
    )
    assert response.status_code == 422


def test_outcome_cannot_be_recorded_before_completion(client, db_session):
    _application, _job, _candidate_headers, headers, interview = _schedule_interview(
        client, db_session, email="outcome.before@test.com"
    )
    response = client.post(
        f"/api/v1/interviews/{interview['id']}/outcome",
        json={"outcome": "rejected"},
        headers=headers,
    )
    assert response.status_code == 400


def test_hire_rolls_back_when_employee_creation_fails(client, db_session):
    application, _job, _candidate_headers, headers, interview = _schedule_interview(
        client, db_session, email="outcome.rollback@test.com"
    )
    completed = _complete(client, headers, interview["id"])

    candidate = (
        db_session.query(Candidate)
        .join(Application, Application.candidate_id == Candidate.id)
        .filter(Application.id == application["id"])
        .one()
    )
    candidate.phone = None
    db_session.commit()

    response = client.post(
        f"/api/v1/interviews/{completed['id']}/outcome",
        json={"outcome": "hired"},
        headers=headers,
    )
    assert response.status_code == 400

    db_session.expire_all()
    app_row = db_session.query(Application).filter(Application.id == application["id"]).one()
    assert app_row.status == ApplicationStatus.SHORTLISTED
    interview_row = db_session.query(Interview).filter(Interview.id == interview["id"]).one()
    assert interview_row.outcome is None
    assert db_session.query(Employee).filter(Employee.email == "outcome.rollback@test.com").count() == 0


def test_cannot_invite_while_completed_without_outcome(client, db_session):
    application, _job, _candidate_headers, headers, interview = _schedule_interview(
        client, db_session, email="outcome.block.invite@test.com"
    )
    _complete(client, headers, interview["id"])
    primary_id, _ = _create_linked_panelist(
        client, db_session, email=f"block.primary.{uuid4().hex[:8]}@test.com"
    )
    response = client.post(
        f"/api/v1/interviews/applications/{application['id']}",
        json=_invite_payload(primary_employee_id=primary_id),
        headers=headers,
    )
    assert response.status_code == 409


def test_non_primary_panel_cannot_complete_interview(client, db_session):
    _application, _job, _candidate_headers, headers, interview = _schedule_interview(
        client, db_session, email="outcome.nonprimary@test.com"
    )
    _panel_id, panel_headers = _create_linked_panelist(
        client, db_session, email=f"panel.complete.{uuid4().hex[:8]}@test.com"
    )
    response = client.post(
        f"/api/v1/me/interviews/{interview['id']}/complete",
        json=_complete_payload(),
        headers=panel_headers,
    )
    assert response.status_code in (403, 404)

    hr_attempt = client.patch(
        f"/api/v1/interviews/{interview['id']}/complete",
        json={"feedback": "No"},
        headers=headers,
    )
    assert hr_attempt.status_code == 403

    create_user_with_role(
        db_session,
        email="employee.outcome@test.com",
        password="emppass123",
        role_name="employee",
    )
    emp_headers = auth_header(client, "employee.outcome@test.com", "emppass123")
    emp_attempt = client.post(
        f"/api/v1/me/interviews/{interview['id']}/complete",
        json=_complete_payload(),
        headers=emp_headers,
    )
    assert emp_attempt.status_code in (403, 404)
