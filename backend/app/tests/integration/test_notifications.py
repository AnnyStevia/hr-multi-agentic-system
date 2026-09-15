from app.modules.notifications.models import Notification, NotificationType
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import NotificationService
from app.tests.helpers import auth_header, create_candidate_user, create_user_with_role


def _create_notification_for_user(db_session, user_id: int, *, title: str = "Hello") -> Notification:
    return NotificationService(NotificationRepository(db_session)).create_notification(
        recipient_user_id=user_id,
        type=NotificationType.APPLICATION_STATUS_CHANGED,
        title=title,
        message="Test body",
        related_entity_type="application",
        related_entity_id=99,
    )


def test_candidate_lists_own_notifications(client, db_session):
    user = create_candidate_user(db_session, email="notif.list@test.com", password="pass12345")
    _create_notification_for_user(db_session, user.id, title="Your update")

    response = client.get(
        "/api/v1/notifications",
        headers=auth_header(client, "notif.list@test.com", "pass12345"),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Your update"
    assert data[0]["type"] == "application_status_changed"
    assert data[0]["is_read"] is False


def test_unread_count_endpoint(client, db_session):
    user = create_candidate_user(db_session, email="notif.unread@test.com", password="pass12345")
    _create_notification_for_user(db_session, user.id)
    _create_notification_for_user(db_session, user.id, title="Second")

    response = client.get(
        "/api/v1/notifications/unread-count",
        headers=auth_header(client, "notif.unread@test.com", "pass12345"),
    )
    assert response.status_code == 200
    assert response.json()["count"] == 2


def test_mark_notification_read(client, db_session):
    user = create_candidate_user(db_session, email="notif.mark@test.com", password="pass12345")
    notification = _create_notification_for_user(db_session, user.id)
    headers = auth_header(client, "notif.mark@test.com", "pass12345")

    response = client.patch(f"/api/v1/notifications/{notification.id}/read", headers=headers)
    assert response.status_code == 200
    assert response.json()["is_read"] is True
    assert response.json()["read_at"] is not None

    count = client.get("/api/v1/notifications/unread-count", headers=headers)
    assert count.json()["count"] == 0


def test_mark_all_notifications_read(client, db_session):
    user = create_candidate_user(db_session, email="notif.markall@test.com", password="pass12345")
    _create_notification_for_user(db_session, user.id)
    _create_notification_for_user(db_session, user.id, title="Two")
    headers = auth_header(client, "notif.markall@test.com", "pass12345")

    response = client.patch("/api/v1/notifications/read-all", headers=headers)
    assert response.status_code == 200
    assert response.json()["updated"] == 2

    count = client.get("/api/v1/notifications/unread-count", headers=headers)
    assert count.json()["count"] == 0


def test_unauthenticated_access_is_rejected(client):
    assert client.get("/api/v1/notifications").status_code == 401
    assert client.get("/api/v1/notifications/unread-count").status_code == 401
    assert client.patch("/api/v1/notifications/1/read").status_code == 401
    assert client.patch("/api/v1/notifications/read-all").status_code == 401


def test_candidate_cannot_access_another_users_notification(client, db_session):
    owner = create_candidate_user(db_session, email="notif.owner2@test.com", password="pass12345")
    other = create_candidate_user(db_session, email="notif.other2@test.com", password="pass12345")
    notification = _create_notification_for_user(db_session, owner.id)
    other_headers = auth_header(client, "notif.other2@test.com", "pass12345")

    mark = client.patch(f"/api/v1/notifications/{notification.id}/read", headers=other_headers)
    assert mark.status_code == 404

    listing = client.get("/api/v1/notifications", headers=other_headers)
    assert listing.status_code == 200
    assert listing.json() == []


def test_hr_user_only_sees_own_notifications(client, db_session):
    hr = create_user_with_role(
        db_session,
        email="notif.hr@test.com",
        password="pass12345",
        role_name="hr",
    )
    candidate = create_candidate_user(db_session, email="notif.candidate.hr@test.com", password="pass12345")
    _create_notification_for_user(db_session, candidate.id, title="Candidate only")
    _create_notification_for_user(db_session, hr.id, title="HR only")

    hr_headers = auth_header(client, "notif.hr@test.com", "pass12345")
    response = client.get("/api/v1/notifications", headers=hr_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "HR only"
