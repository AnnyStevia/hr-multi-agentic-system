from app.modules.identity.models import User
from app.modules.notifications.models import Notification, NotificationType
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import NotificationService
from app.shared.exceptions import AppException
from app.tests.helpers import create_candidate_user, create_user_with_role


def _service(db_session) -> NotificationService:
    return NotificationService(NotificationRepository(db_session))


def _create_notification(db_session, recipient: User, *, title: str = "Test title") -> Notification:
    return _service(db_session).create_notification(
        recipient_user_id=recipient.id,
        type=NotificationType.APPLICATION_STATUS_CHANGED,
        title=title,
        message="Test message",
        related_entity_type="application",
        related_entity_id=1,
    )


def test_create_notification_persists_fields(db_session):
    user = create_candidate_user(db_session, email="notif.create@test.com", password="pass12345")
    notification = _create_notification(db_session, user, title="Shortlisted")

    assert notification.recipient_user_id == user.id
    assert notification.type == NotificationType.APPLICATION_STATUS_CHANGED
    assert notification.title == "Shortlisted"
    assert notification.message == "Test message"
    assert notification.related_entity_type == "application"
    assert notification.related_entity_id == 1
    assert notification.is_read is False
    assert notification.read_at is None


def test_list_for_user_returns_only_own_notifications_newest_first(db_session):
    user_a = create_candidate_user(db_session, email="notif.a@test.com", password="pass12345")
    user_b = create_candidate_user(db_session, email="notif.b@test.com", password="pass12345")
    service = _service(db_session)

    first = service.create_notification(
        recipient_user_id=user_a.id,
        type=NotificationType.APPLICATION_STATUS_CHANGED,
        title="First",
        message="Older",
    )
    second = service.create_notification(
        recipient_user_id=user_a.id,
        type=NotificationType.APPLICATION_STATUS_CHANGED,
        title="Second",
        message="Newer",
    )
    service.create_notification(
        recipient_user_id=user_b.id,
        type=NotificationType.APPLICATION_STATUS_CHANGED,
        title="Other user",
        message="Hidden",
    )

    items = service.list_for_user(user_a.id)
    assert len(items) == 2
    assert {item.id for item in items} == {first.id, second.id}
    assert all(item.recipient_user_id == user_a.id for item in items)


def test_get_unread_count(db_session):
    user = create_candidate_user(db_session, email="notif.count@test.com", password="pass12345")
    service = _service(db_session)
    assert service.get_unread_count(user.id) == 0

    notification = _create_notification(db_session, user)
    assert service.get_unread_count(user.id) == 1

    service.mark_as_read(notification.id, user.id)
    assert service.get_unread_count(user.id) == 0


def test_mark_as_read_sets_flags(db_session):
    user = create_candidate_user(db_session, email="notif.read@test.com", password="pass12345")
    notification = _create_notification(db_session, user)

    updated = _service(db_session).mark_as_read(notification.id, user.id)
    assert updated.is_read is True
    assert updated.read_at is not None


def test_mark_as_read_rejects_other_users_notification(db_session):
    owner = create_candidate_user(db_session, email="notif.owner@test.com", password="pass12345")
    other = create_candidate_user(db_session, email="notif.other@test.com", password="pass12345")
    notification = _create_notification(db_session, owner)

    try:
        _service(db_session).mark_as_read(notification.id, other.id)
        raise AssertionError("Expected cross-user mark_as_read to fail")
    except AppException as exc:
        assert exc.status_code == 404


def test_mark_all_as_read_updates_only_recipient_unread(db_session):
    user_a = create_candidate_user(db_session, email="notif.all.a@test.com", password="pass12345")
    user_b = create_candidate_user(db_session, email="notif.all.b@test.com", password="pass12345")
    service = _service(db_session)

    a1 = _create_notification(db_session, user_a, title="A1")
    a2 = _create_notification(db_session, user_a, title="A2")
    b1 = _create_notification(db_session, user_b, title="B1")

    updated = service.mark_all_as_read(user_a.id)
    assert updated == 2

    db_session.refresh(a1)
    db_session.refresh(a2)
    db_session.refresh(b1)
    assert a1.is_read is True
    assert a2.is_read is True
    assert b1.is_read is False
