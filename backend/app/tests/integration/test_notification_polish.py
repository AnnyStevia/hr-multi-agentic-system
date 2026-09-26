from datetime import UTC, datetime, timedelta

from app.modules.employees.models import Employee, EmploymentStatus
from app.modules.identity.models import User
from app.modules.interviews.models import Interview, InterviewStatus
from app.modules.interviews.reminders import send_upcoming_interview_reminders
from app.modules.notifications.models import Notification, NotificationType
from app.tests.helpers import create_department
from app.tests.integration.test_application_review import _submit_application
from app.tests.integration.test_interview_invitations import _create_invitation
from app.tests.integration.test_interview_outcomes import _complete, _schedule_interview


def test_hr_notification_uses_interviewer_when_created_by_missing(client, db_session):
    application, _job, candidate_headers, _storage = _submit_application(
        client,
        db_session,
        email="remind.fallback.cand@test.com",
    )
    interview, headers, _primary = _create_invitation(client, db_session, application["id"])

    hr_user = db_session.query(User).filter(User.email == "hr.review@test.com").one()
    department = create_department(client, name="Fallback Dept", headers=headers)
    employee = Employee(
        employee_number="PENDING",
        first_name="HR",
        last_name="Fallback",
        email="hr.fallback.employee@test.com",
        phone="+216 20 999 888",
        department_id=department["id"],
        position="HR Officer",
        hire_date=datetime.now(UTC).date(),
        employment_status=EmploymentStatus.ACTIVE,
        user_id=hr_user.id,
    )
    db_session.add(employee)
    db_session.flush()
    employee.employee_number = f"EMP-{employee.id:06d}"

    row = db_session.query(Interview).filter(Interview.id == interview["id"]).one()
    row.created_by_user_id = None
    row.interviewer_employee_id = employee.id
    for assignment in row.panel_assignments:
        assignment.employee_id = employee.id
        assignment.is_primary = True
    db_session.commit()

    confirmed = client.post(
        f"/api/v1/careers/interviews/{interview['id']}/confirm",
        json={"slot_id": interview["slots"][0]["id"]},
        headers=candidate_headers,
    )
    assert confirmed.status_code == 200, confirmed.text

    hr_notifications = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_user_id == hr_user.id,
            Notification.type == NotificationType.INTERVIEW_SCHEDULED,
            Notification.related_entity_id == interview["id"],
        )
        .all()
    )
    assert len(hr_notifications) == 1


def test_another_interview_notifies_candidate(client, db_session):
    application, _job, candidate_headers, headers, interview = _schedule_interview(
        client, db_session, email="outcome.another.notif@test.com"
    )
    completed = _complete(client, headers, interview["id"])
    response = client.post(
        f"/api/v1/interviews/{completed['id']}/outcome",
        json={"outcome": "another_interview"},
        headers=headers,
    )
    assert response.status_code == 200, response.text

    candidate_user = db_session.query(User).filter(User.email == "outcome.another.notif@test.com").one()
    notifs = (
        db_session.query(Notification)
        .filter(
            Notification.recipient_user_id == candidate_user.id,
            Notification.type == NotificationType.APPLICATION_STATUS_CHANGED,
            Notification.related_entity_id == application["id"],
        )
        .all()
    )
    another = [item for item in notifs if "another conversation" in item.message.lower()]
    assert len(another) == 1
    assert "next step" in another[0].title.lower()

    listing = client.get("/api/v1/notifications", headers=candidate_headers)
    assert any("another conversation" in item["message"].lower() for item in listing.json())


def test_interview_reminder_is_idempotent_and_within_window(client, db_session):
    application, job, candidate_headers, headers, interview = _schedule_interview(
        client, db_session, email="remind.window@test.com"
    )

    row = db_session.query(Interview).filter(Interview.id == interview["id"]).one()
    assert row.status == InterviewStatus.SCHEDULED
    selected = row.selected_slot
    assert selected is not None
    selected.starts_at = datetime.now(UTC) + timedelta(minutes=20)
    selected.ends_at = selected.starts_at + timedelta(minutes=30)
    db_session.commit()

    created_first = send_upcoming_interview_reminders(db_session)
    assert created_first >= 1

    candidate_user = db_session.query(User).filter(User.email == "remind.window@test.com").one()
    reminders = (
        db_session.query(Notification)
        .filter(
            Notification.type == NotificationType.INTERVIEW_REMINDER,
            Notification.related_entity_id == interview["id"],
        )
        .all()
    )
    assert any(item.recipient_user_id == candidate_user.id for item in reminders)

    created_second = send_upcoming_interview_reminders(db_session)
    assert created_second == 0
    assert (
        db_session.query(Notification)
        .filter(
            Notification.type == NotificationType.INTERVIEW_REMINDER,
            Notification.related_entity_id == interview["id"],
            Notification.recipient_user_id == candidate_user.id,
        )
        .count()
        == 1
    )


def test_candidate_can_list_my_applications(client, db_session):
    application, job, candidate_headers, _storage = _submit_application(
        client,
        db_session,
        email="my.apps@test.com",
    )
    response = client.get("/api/v1/careers/my-applications", headers=candidate_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == application["id"]
    assert body[0]["job_id"] == job["id"]
    assert body[0]["status"] == "submitted"
    assert body[0]["job_title"] == job["title"]
