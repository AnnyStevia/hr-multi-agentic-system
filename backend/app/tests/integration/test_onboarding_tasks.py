from app.modules.onboarding.models import Onboarding
from app.tests.helpers import auth_header, create_candidate_user
from app.tests.integration.test_application_review import _submit_application
from app.tests.integration.test_interview_invitations import _create_invitation
from app.tests.integration.test_interview_outcomes import _complete
from app.tests.integration.test_onboarding import _hire


def _onboarding_id(db_session, employee_id: int) -> int:
    return (
        db_session.query(Onboarding).filter(Onboarding.employee_id == employee_id).one().id
    )


def test_hr_can_crud_onboarding_tasks(client, db_session):
    _application, _job, _candidate_headers, headers, body = _hire(
        client, db_session, email="tasks.hr.crud@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])

    created = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={
            "title": "Sign employment contract",
            "description": "Return signed PDF",
            "due_date": "2026-10-01",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    task = created.json()
    assert task["title"] == "Sign employment contract"
    assert task["status"] == "pending"
    assert task["completed_at"] is None
    task_id = task["id"]

    listed = client.get(f"/api/v1/onboarding/{onboarding_id}/tasks", headers=headers)
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == 1

    updated = client.patch(
        f"/api/v1/onboarding/tasks/{task_id}",
        json={"title": "Sign and upload contract", "status": "completed"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "Sign and upload contract"
    assert updated.json()["status"] == "completed"
    assert updated.json()["completed_at"] is not None

    deleted = client.delete(f"/api/v1/onboarding/tasks/{task_id}", headers=headers)
    assert deleted.status_code == 204, deleted.text

    after_delete = client.get(f"/api/v1/onboarding/{onboarding_id}/tasks", headers=headers)
    assert after_delete.status_code == 200
    assert after_delete.json() == []


def test_admin_can_create_onboarding_task(client, db_session):
    _application, _job, _candidate_headers, _headers, body = _hire(
        client, db_session, email="tasks.admin@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    admin_headers = auth_header(client)

    created = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Collect laptop"},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "pending"


def test_employee_can_list_and_complete_own_tasks(client, db_session):
    _application, _job, candidate_headers, headers, body = _hire(
        client, db_session, email="tasks.own@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])

    created = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Complete IT setup"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    listed = client.get("/api/v1/me/onboarding/tasks", headers=candidate_headers)
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == task_id

    completed = client.patch(
        f"/api/v1/me/onboarding/tasks/{task_id}/complete",
        headers=candidate_headers,
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"
    assert completed.json()["completed_at"] is not None

    again = client.patch(
        f"/api/v1/me/onboarding/tasks/{task_id}/complete",
        headers=candidate_headers,
    )
    assert again.status_code == 400


def test_employee_cannot_view_another_employees_tasks(client, db_session):
    _application, _job, _candidate_headers, headers, body = _hire(
        client, db_session, email="tasks.owner@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    created = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Private task"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    other = create_candidate_user(
        db_session, email="tasks.other@test.com", password="otherpass123"
    )
    other_headers = auth_header(client, email=other.email, password="otherpass123")

    assert client.get("/api/v1/me/onboarding/tasks", headers=other_headers).status_code == 404
    assert (
        client.patch(
            f"/api/v1/me/onboarding/tasks/{task_id}/complete",
            headers=other_headers,
        ).status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/onboarding/{onboarding_id}/tasks", headers=other_headers).status_code
        == 403
    )


def test_employee_cannot_modify_or_delete_tasks(client, db_session):
    _application, _job, candidate_headers, headers, body = _hire(
        client, db_session, email="tasks.nomod@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    created = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "HR only edit"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    assert (
        client.post(
            f"/api/v1/onboarding/{onboarding_id}/tasks",
            json={"title": "Should fail"},
            headers=candidate_headers,
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/v1/onboarding/tasks/{task_id}",
            json={"title": "Hacked"},
            headers=candidate_headers,
        ).status_code
        == 403
    )
    assert (
        client.delete(f"/api/v1/onboarding/tasks/{task_id}", headers=candidate_headers).status_code
        == 403
    )


def test_invalid_onboarding_and_task_access_rejected(client, db_session):
    _application, _job, candidate_headers, headers, body = _hire(
        client, db_session, email="tasks.invalid@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])

    assert (
        client.get("/api/v1/onboarding/999999/tasks", headers=headers).status_code == 404
    )
    assert (
        client.post(
            "/api/v1/onboarding/999999/tasks",
            json={"title": "Missing parent"},
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.patch(
            "/api/v1/onboarding/tasks/999999",
            json={"title": "Missing"},
            headers=headers,
        ).status_code
        == 404
    )
    assert client.delete("/api/v1/onboarding/tasks/999999", headers=headers).status_code == 404
    assert (
        client.patch(
            "/api/v1/me/onboarding/tasks/999999/complete",
            headers=candidate_headers,
        ).status_code
        == 404
    )

    # Second hire reuses the same HR headers to avoid duplicate HR user
    application2, _job2, other_headers, _storage = _submit_application(
        client, db_session, email="tasks.invalid.other@test.com"
    )
    interview2, _ = _create_invitation(
        client, db_session, application2["id"], headers=headers
    )
    slot_id = interview2["slots"][0]["id"]
    confirmed = client.post(
        f"/api/v1/careers/interviews/{interview2['id']}/confirm",
        json={"slot_id": slot_id},
        headers=other_headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    completed2 = _complete(client, headers, confirmed.json()["id"])
    hired2 = client.post(
        f"/api/v1/interviews/{completed2['id']}/outcome",
        json={"outcome": "hired"},
        headers=headers,
    )
    assert hired2.status_code == 200, hired2.text

    created = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Owner task"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    assert (
        client.patch(
            f"/api/v1/me/onboarding/tasks/{task_id}/complete",
            headers=other_headers,
        ).status_code
        == 404
    )
    assert client.get("/api/v1/me/onboarding", headers=other_headers).status_code == 200
    assert hired2.json()["hired_employee_id"] != body["hired_employee_id"]


def test_creating_task_notifies_employee(client, db_session):
    from app.modules.identity.models import User
    from app.modules.notifications.models import Notification, NotificationType

    _application, _job, candidate_headers, headers, body = _hire(
        client, db_session, email="tasks.notify@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    user = db_session.query(User).filter(User.email == "tasks.notify@test.com").one()

    created = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Read company handbook"},
        headers=headers,
    )
    assert created.status_code == 201, created.text

    notification = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_user_id == user.id,
            Notification.type == NotificationType.ONBOARDING_TASK_ASSIGNED,
        )
        .one()
    )
    assert "Read company handbook" in notification.message
    assert notification.related_entity_type == "onboarding"
    assert notification.related_entity_id == onboarding_id

    listed = client.get("/api/v1/notifications", headers=candidate_headers)
    assert listed.status_code == 200
    assert any(item["type"] == "onboarding_task_assigned" for item in listed.json())


def test_completing_last_task_auto_completes_onboarding(client, db_session):
    from app.modules.onboarding.models import OnboardingStatus

    _application, _job, candidate_headers, headers, body = _hire(
        client, db_session, email="tasks.autodone@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])

    first = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Task A"},
        headers=headers,
    )
    second = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Task B"},
        headers=headers,
    )
    assert first.status_code == 201 and second.status_code == 201
    task_a = first.json()["id"]
    task_b = second.json()["id"]

    partial = client.patch(
        f"/api/v1/me/onboarding/tasks/{task_a}/complete",
        headers=candidate_headers,
    )
    assert partial.status_code == 200
    db_session.expire_all()
    onboarding = db_session.query(Onboarding).filter(Onboarding.id == onboarding_id).one()
    assert onboarding.status == OnboardingStatus.IN_PROGRESS
    assert client.get("/api/v1/careers/jobs", headers=candidate_headers).status_code == 403

    done = client.patch(
        f"/api/v1/me/onboarding/tasks/{task_b}/complete",
        headers=candidate_headers,
    )
    assert done.status_code == 200
    db_session.expire_all()
    onboarding = db_session.query(Onboarding).filter(Onboarding.id == onboarding_id).one()
    assert onboarding.status == OnboardingStatus.COMPLETED
    assert onboarding.completed_at is not None

    me = client.get("/api/v1/auth/me", headers=candidate_headers)
    assert me.json()["onboarding_status"] == "completed"
    assert client.get("/api/v1/careers/jobs", headers=candidate_headers).status_code == 200
    assert client.get("/api/v1/me/employee-home", headers=candidate_headers).status_code == 200


def test_cannot_add_task_to_completed_onboarding(client, db_session):
    _application, _job, _candidate_headers, headers, body = _hire(
        client, db_session, email="tasks.closed@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    assert (
        client.post(f"/api/v1/onboarding/{onboarding_id}/complete", headers=headers).status_code
        == 200
    )
    blocked = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Too late"},
        headers=headers,
    )
    assert blocked.status_code == 400


def test_hr_override_complete_works_with_zero_tasks(client, db_session):
    _application, _job, candidate_headers, headers, body = _hire(
        client, db_session, email="tasks.override@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    assert (
        client.post(f"/api/v1/onboarding/{onboarding_id}/complete", headers=headers).status_code
        == 200
    )
    me = client.get("/api/v1/auth/me", headers=candidate_headers)
    assert me.json()["onboarding_status"] == "completed"
