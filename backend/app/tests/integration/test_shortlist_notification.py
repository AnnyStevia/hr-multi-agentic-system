from app.modules.notifications.models import Notification
from app.tests.integration.test_application_review import _hr_headers, _submit_application
from app.tests.integration.test_applications import _candidate_headers


def _shortlist_application(client, db_session, application_id: int):
    headers = _hr_headers(client, db_session)
    screening = client.patch(
        f"/api/v1/applications/{application_id}/status",
        json={"status": "screening"},
        headers=headers,
    )
    assert screening.status_code == 200, screening.text
    shortlisted = client.patch(
        f"/api/v1/applications/{application_id}/status",
        json={"status": "shortlisted"},
        headers=headers,
    )
    assert shortlisted.status_code == 200, shortlisted.text
    return headers


def test_shortlisting_creates_candidate_notification(client, db_session):
    application, job, candidate_headers, _storage = _submit_application(
        client,
        db_session,
        email="shortlist.notif@test.com",
    )
    _shortlist_application(client, db_session, application["id"])

    response = client.get("/api/v1/notifications", headers=candidate_headers)
    assert response.status_code == 200
    notifications = response.json()
    assert len(notifications) == 1
    item = notifications[0]
    assert item["type"] == "application_status_changed"
    assert item["title"] == "You've been shortlisted!"
    assert job["title"] in item["message"]
    assert item["related_entity_type"] == "application"
    assert item["related_entity_id"] == application["id"]
    assert item["is_read"] is False


def test_resaving_shortlisted_does_not_create_duplicate(client, db_session):
    application, _job, candidate_headers, _storage = _submit_application(
        client,
        db_session,
        email="shortlist.dup@test.com",
    )
    headers = _shortlist_application(client, db_session, application["id"])

    retry = client.patch(
        f"/api/v1/applications/{application['id']}/status",
        json={"status": "shortlisted"},
        headers=headers,
    )
    assert retry.status_code == 400

    response = client.get("/api/v1/notifications", headers=candidate_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1

    count = db_session.query(Notification).count()
    assert count == 1
