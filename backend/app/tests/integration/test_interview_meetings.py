"""Integration: confirm schedules first; meeting provision is idempotent with Fake provider."""

from unittest.mock import patch

from app.modules.interviews.models import Interview, InterviewStatus
from app.modules.notifications.models import Notification, NotificationType
from app.shared.meetings.fake import FakeMeetingProvider
from app.tests.integration.test_application_review import _submit_application
from app.tests.integration.test_interview_invitations import _create_invitation


def test_confirm_schedules_even_when_meeting_provider_is_noop(client, db_session):
    application, _job, candidate_headers, _storage = _submit_application(
        client, db_session, email="meet.noop@test.com"
    )
    interview, _headers, _primary = _create_invitation(client, db_session, application["id"])
    slot_id = interview["slots"][0]["id"]

    with patch(
        "app.api.v1.career_interviews.run_interview_meeting_provision",
        side_effect=lambda _id: None,
    ):
        confirmed = client.post(
            f"/api/v1/careers/interviews/{interview['id']}/confirm",
            json={"slot_id": slot_id},
            headers=candidate_headers,
        )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "scheduled"
    row = db_session.query(Interview).filter(Interview.id == interview["id"]).one()
    assert row.status == InterviewStatus.SCHEDULED
    assert row.meeting_url is None


def test_hr_ensure_meeting_with_fake_provider(client, db_session):
    application, _job, candidate_headers, _storage = _submit_application(
        client, db_session, email="meet.fake2@test.com"
    )
    interview, headers, _primary = _create_invitation(client, db_session, application["id"])
    slot_id = interview["slots"][0]["id"]
    confirmed = client.post(
        f"/api/v1/careers/interviews/{interview['id']}/confirm",
        json={"slot_id": slot_id},
        headers=candidate_headers,
    )
    assert confirmed.status_code == 200

    with patch(
        "app.modules.interviews.dependencies.get_meeting_provider",
        return_value=FakeMeetingProvider(),
    ):
        response = client.post(
            f"/api/v1/interviews/{interview['id']}/meeting",
            headers=headers,
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "scheduled"
    assert body["meeting_url"]
    assert body["meeting_url"].startswith("https://meet.example.test/")

    row = db_session.query(Interview).filter(Interview.id == interview["id"]).one()
    assert row.meeting_external_id

    with patch(
        "app.modules.interviews.dependencies.get_meeting_provider",
        return_value=FakeMeetingProvider(),
    ):
        again = client.post(
            f"/api/v1/interviews/{interview['id']}/meeting",
            headers=headers,
        )
    assert again.status_code == 200
    assert again.json()["meeting_url"] == body["meeting_url"]

    ready = (
        db_session.query(Notification)
        .filter(
            Notification.type == NotificationType.INTERVIEW_MEETING_READY,
            Notification.related_entity_id == interview["id"],
        )
        .count()
    )
    assert ready >= 1


def test_candidate_sees_meeting_url_after_ensure(client, db_session):
    application, _job, candidate_headers, _storage = _submit_application(
        client, db_session, email="meet.cand.see@test.com"
    )
    interview, headers, _primary = _create_invitation(client, db_session, application["id"])
    slot_id = interview["slots"][0]["id"]
    assert (
        client.post(
            f"/api/v1/careers/interviews/{interview['id']}/confirm",
            json={"slot_id": slot_id},
            headers=candidate_headers,
        ).status_code
        == 200
    )

    with patch(
        "app.modules.interviews.dependencies.get_meeting_provider",
        return_value=FakeMeetingProvider(),
    ):
        ensured = client.post(
            f"/api/v1/interviews/{interview['id']}/meeting",
            headers=headers,
        )
    assert ensured.status_code == 200
    detail = client.get(
        f"/api/v1/careers/interviews/{interview['id']}",
        headers=candidate_headers,
    )
    assert detail.status_code == 200
    assert detail.json()["meeting_url"] == ensured.json()["meeting_url"]
    assert detail.json().get("evaluation") is None
