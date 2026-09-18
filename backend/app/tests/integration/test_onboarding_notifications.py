from app.modules.identity.models import Candidate, User
from app.modules.notifications.models import Notification, NotificationType
from app.modules.onboarding.models import Onboarding
from app.tests.helpers import auth_header, create_candidate_user
from app.tests.integration.test_interview_outcomes import _complete, _schedule_interview
from app.tests.integration.test_onboarding import _hire


def _onboarding_id(db_session, employee_id: int) -> int:
    return db_session.query(Onboarding).filter(Onboarding.employee_id == employee_id).one().id


def _count_type(db_session, *, notification_type: NotificationType, recipient_user_id: int | None = None) -> int:
    query = db_session.query(Notification).filter(Notification.type == notification_type)
    if recipient_user_id is not None:
        query = query.filter(Notification.recipient_user_id == recipient_user_id)
    return query.count()


def test_hire_notifies_employee_onboarding_started(client, db_session):
    _application, _job, candidate_headers, _headers, body = _hire(
        client, db_session, email="notif.start@test.com"
    )
    user = db_session.query(User).filter(User.email == "notif.start@test.com").one()
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])

    rows = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_user_id == user.id,
            Notification.type == NotificationType.ONBOARDING_STARTED,
        )
        .all()
    )
    assert len(rows) == 1
    assert rows[0].related_entity_type == "onboarding"
    assert rows[0].related_entity_id == onboarding_id
    assert "started" in rows[0].message.lower()

    listed = client.get("/api/v1/notifications", headers=candidate_headers)
    assert listed.status_code == 200
    assert any(item["type"] == "onboarding_started" for item in listed.json())


def test_employee_task_complete_notifies_hr(client, db_session):
    _application, _job, candidate_headers, headers, body = _hire(
        client, db_session, email="notif.taskdone@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    employee = client.get(f"/api/v1/employees/{body['hired_employee_id']}", headers=headers).json()

    created = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Sign handbook"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    before = _count_type(db_session, notification_type=NotificationType.ONBOARDING_TASK_COMPLETED)
    done = client.patch(
        f"/api/v1/me/onboarding/tasks/{task_id}/complete",
        headers=candidate_headers,
    )
    assert done.status_code == 200, done.text

    rows = (
        db_session.query(Notification)
        .filter(
            Notification.type == NotificationType.ONBOARDING_TASK_COMPLETED,
            Notification.related_entity_id == task_id,
        )
        .all()
    )
    assert len(rows) >= 1
    assert all("Sign handbook" in row.message for row in rows)
    assert all(employee["full_name"] in row.message for row in rows)
    assert _count_type(db_session, notification_type=NotificationType.ONBOARDING_TASK_COMPLETED) > before

    hr_list = client.get("/api/v1/notifications", headers=headers)
    assert hr_list.status_code == 200
    assert any(item["type"] == "onboarding_task_completed" for item in hr_list.json())


def test_training_assign_and_complete_notifications(client, db_session):
    _application, _job, candidate_headers, headers, body = _hire(
        client, db_session, email="notif.train@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    employee = client.get(f"/api/v1/employees/{body['hired_employee_id']}", headers=headers).json()
    user = db_session.query(User).filter(User.email == "notif.train@test.com").one()

    training = client.post(
        "/api/v1/trainings",
        json={"title": "Safety 101"},
        headers=headers,
    ).json()
    assignment = client.post(
        f"/api/v1/onboarding/{onboarding_id}/trainings",
        json={"training_id": training["id"]},
        headers=headers,
    )
    assert assignment.status_code == 201, assignment.text
    assignment_id = assignment.json()["id"]

    assigned_rows = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_user_id == user.id,
            Notification.type == NotificationType.ONBOARDING_TRAINING_ASSIGNED,
            Notification.related_entity_id == assignment_id,
        )
        .all()
    )
    assert len(assigned_rows) == 1
    assert "Safety 101" in assigned_rows[0].message

    completed = client.patch(
        f"/api/v1/me/onboarding/trainings/{assignment_id}/complete",
        headers=candidate_headers,
    )
    assert completed.status_code == 200, completed.text

    done_rows = (
        db_session.query(Notification)
        .filter(
            Notification.type == NotificationType.ONBOARDING_TRAINING_COMPLETED,
            Notification.related_entity_id == assignment_id,
        )
        .all()
    )
    assert len(done_rows) >= 1
    assert all("Safety 101" in row.message for row in done_rows)
    assert all(employee["full_name"] in row.message for row in done_rows)


def test_final_task_notifies_employee_and_hr_onboarding_completed(client, db_session):
    _application, _job, candidate_headers, headers, body = _hire(
        client, db_session, email="notif.done@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    user = db_session.query(User).filter(User.email == "notif.done@test.com").one()
    employee = client.get(f"/api/v1/employees/{body['hired_employee_id']}", headers=headers).json()

    task = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Final step"},
        headers=headers,
    ).json()

    assert (
        client.patch(
            f"/api/v1/me/onboarding/tasks/{task['id']}/complete",
            headers=candidate_headers,
        ).status_code
        == 200
    )

    employee_rows = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_user_id == user.id,
            Notification.type == NotificationType.ONBOARDING_COMPLETED,
            Notification.related_entity_id == onboarding_id,
        )
        .all()
    )
    assert len(employee_rows) == 1

    hr_rows = (
        db_session.query(Notification)
        .filter(
            Notification.type == NotificationType.ONBOARDING_COMPLETED,
            Notification.related_entity_id == onboarding_id,
            Notification.recipient_user_id != user.id,
        )
        .all()
    )
    assert len(hr_rows) >= 1
    assert all(employee["full_name"] in row.message for row in hr_rows)


def test_retry_complete_does_not_duplicate_notifications(client, db_session):
    _application, _job, candidate_headers, headers, body = _hire(
        client, db_session, email="notif.dedupe@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])

    task = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Only once"},
        headers=headers,
    ).json()
    training = client.post(
        "/api/v1/trainings",
        json={"title": "Once course"},
        headers=headers,
    ).json()
    assignment = client.post(
        f"/api/v1/onboarding/{onboarding_id}/trainings",
        json={"training_id": training["id"]},
        headers=headers,
    ).json()

    assert (
        client.patch(
            f"/api/v1/me/onboarding/tasks/{task['id']}/complete",
            headers=candidate_headers,
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/me/onboarding/trainings/{assignment['id']}/complete",
            headers=candidate_headers,
        ).status_code
        == 200
    )

    task_count = _count_type(db_session, notification_type=NotificationType.ONBOARDING_TASK_COMPLETED)
    train_count = _count_type(
        db_session, notification_type=NotificationType.ONBOARDING_TRAINING_COMPLETED
    )
    done_count = _count_type(db_session, notification_type=NotificationType.ONBOARDING_COMPLETED)

    assert (
        client.patch(
            f"/api/v1/me/onboarding/tasks/{task['id']}/complete",
            headers=candidate_headers,
        ).status_code
        == 400
    )
    assert (
        client.patch(
            f"/api/v1/me/onboarding/trainings/{assignment['id']}/complete",
            headers=candidate_headers,
        ).status_code
        == 400
    )

    assert _count_type(db_session, notification_type=NotificationType.ONBOARDING_TASK_COMPLETED) == task_count
    assert (
        _count_type(db_session, notification_type=NotificationType.ONBOARDING_TRAINING_COMPLETED)
        == train_count
    )
    assert _count_type(db_session, notification_type=NotificationType.ONBOARDING_COMPLETED) == done_count


def test_failed_hire_does_not_create_onboarding_started(client, db_session):
    application, _job, _candidate_headers, headers, interview = _schedule_interview(
        client, db_session, email="notif.failhire@test.com"
    )
    completed = _complete(client, headers, interview["id"])

    candidate = (
        db_session.query(Candidate)
        .join(User, User.id == Candidate.user_id)
        .filter(User.email == "notif.failhire@test.com")
        .one()
    )
    candidate.phone = None
    db_session.commit()

    before = _count_type(db_session, notification_type=NotificationType.ONBOARDING_STARTED)
    response = client.post(
        f"/api/v1/interviews/{completed['id']}/outcome",
        json={"outcome": "hired"},
        headers=headers,
    )
    assert response.status_code == 400, response.text
    assert _count_type(db_session, notification_type=NotificationType.ONBOARDING_STARTED) == before
    assert application["id"] is not None


def test_other_employee_cannot_trigger_task_complete_notification(client, db_session):
    _application, _job, _candidate_headers, headers, body = _hire(
        client, db_session, email="notif.owner@test.com"
    )
    onboarding_id = _onboarding_id(db_session, body["hired_employee_id"])
    task = client.post(
        f"/api/v1/onboarding/{onboarding_id}/tasks",
        json={"title": "Private task"},
        headers=headers,
    ).json()

    other = create_candidate_user(
        db_session, email="notif.intruder@test.com", password="otherpass123"
    )
    other_headers = auth_header(client, email=other.email, password="otherpass123")

    before = _count_type(db_session, notification_type=NotificationType.ONBOARDING_TASK_COMPLETED)
    assert (
        client.patch(
            f"/api/v1/me/onboarding/tasks/{task['id']}/complete",
            headers=other_headers,
        ).status_code
        == 404
    )
    assert _count_type(db_session, notification_type=NotificationType.ONBOARDING_TASK_COMPLETED) == before
