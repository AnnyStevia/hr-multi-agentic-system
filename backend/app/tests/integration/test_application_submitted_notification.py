from app.modules.identity.hr_access import list_hr_staff_user_ids
from app.modules.notifications.models import Notification, NotificationType
from app.tests.helpers import auth_header, create_user_with_role
from app.tests.integration.test_application_review import _submit_application


def test_application_submit_notifies_hr_staff(client, db_session):
    create_user_with_role(
        db_session,
        email="hr.apply.notify@test.com",
        password="hrpass123",
        role_name="hr",
    )
    application, job, _candidate_headers, _storage = _submit_application(
        client, db_session, email="apply.notify.candidate@test.com"
    )

    hr_ids = set(list_hr_staff_user_ids(db_session))
    assert hr_ids

    rows = (
        db_session.query(Notification)
        .filter(
            Notification.type == NotificationType.APPLICATION_SUBMITTED,
            Notification.related_entity_type == "application",
            Notification.related_entity_id == application["id"],
        )
        .all()
    )
    assert {row.recipient_user_id for row in rows} == hr_ids
    assert all(job["title"] in row.message for row in rows)
    assert all(row.title == "New application" for row in rows)

    hr_headers = auth_header(client, "hr.apply.notify@test.com", "hrpass123")
    listed = client.get("/api/v1/notifications", headers=hr_headers)
    assert listed.status_code == 200
    assert any(
        item["type"] == "application_submitted" and item["related_entity_id"] == application["id"]
        for item in listed.json()
    )


def test_application_submit_notification_is_idempotent_per_application(client, db_session):
    application, _job, _candidate_headers, _storage = _submit_application(
        client, db_session, email="apply.notify.dedupe@test.com"
    )
    count = (
        db_session.query(Notification)
        .filter(
            Notification.type == NotificationType.APPLICATION_SUBMITTED,
            Notification.related_entity_id == application["id"],
        )
        .count()
    )
    assert count == len(list_hr_staff_user_ids(db_session))
