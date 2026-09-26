"""Unit tests for InterviewMeetingService (mocked provider)."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.interviews.meeting_service import InterviewMeetingService
from app.modules.interviews.models import InterviewStatus
from app.shared.exceptions import AppException
from app.shared.meetings.exceptions import MeetingProviderError, MeetingSkipped
from app.shared.meetings.fake import FakeMeetingProvider


def _interview(*, status=InterviewStatus.SCHEDULED, meeting_url=None, external_id=None):
    start = datetime.now(UTC) + timedelta(days=3)
    end = start + timedelta(minutes=30)
    slot = SimpleNamespace(id=1, starts_at=start, ends_at=end)
    user = SimpleNamespace(id=10, email="cand@test.com", full_name="Cand Date")
    candidate = SimpleNamespace(user=user, user_id=10)
    job = SimpleNamespace(title="Engineer")
    application = SimpleNamespace(candidate=candidate, job=job)
    employee = SimpleNamespace(id=5, email="panel@test.com", full_name="Panel", user_id=20)
    assignment = SimpleNamespace(employee=employee, is_primary=True)
    return SimpleNamespace(
        id=42,
        status=status,
        meeting_url=meeting_url,
        meeting_external_id=external_id,
        selected_slot=slot,
        application=application,
        panel_assignments=[assignment],
    )


def test_ensure_reuses_existing_meeting_url():
    interview = _interview(meeting_url="https://meet.example.test/existing")
    repo = MagicMock()
    repo.get_by_id.return_value = interview
    provider = MagicMock()
    service = InterviewMeetingService(repo, provider=provider)
    result = service.ensure_meeting(42)
    assert result.meeting_url == "https://meet.example.test/existing"
    provider.create_meeting.assert_not_called()


def test_ensure_rejects_non_scheduled():
    interview = _interview(status=InterviewStatus.PROPOSED)
    repo = MagicMock()
    repo.get_by_id.return_value = interview
    service = InterviewMeetingService(repo, provider=FakeMeetingProvider())
    with pytest.raises(AppException) as exc:
        service.ensure_meeting(42)
    assert exc.value.status_code == 400


def test_ensure_creates_and_persists_with_fake_provider():
    interview = _interview()
    repo = MagicMock()
    repo.get_by_id.return_value = interview
    repo.save.side_effect = lambda item: item
    notifications = MagicMock()
    service = InterviewMeetingService(
        repo,
        notifications=notifications,
        provider=FakeMeetingProvider(),
    )
    result = service.ensure_meeting(42)
    assert result.meeting_url.startswith("https://meet.example.test/")
    assert result.meeting_external_id.startswith("fake-event-")
    repo.save.assert_called()
    assert notifications.create_if_absent.call_count >= 2


def test_provider_failure_leaves_scheduled_without_url():
    interview = _interview()
    repo = MagicMock()
    repo.get_by_id.return_value = interview
    provider = MagicMock()
    provider.create_meeting.side_effect = MeetingProviderError("Failed to create Google Meet link")
    service = InterviewMeetingService(repo, provider=provider)
    result = service.ensure_meeting(42)
    assert result.status == InterviewStatus.SCHEDULED
    assert result.meeting_url is None
    repo.save.assert_not_called()


def test_noop_skip_leaves_scheduled_without_url():
    interview = _interview()
    repo = MagicMock()
    repo.get_by_id.return_value = interview
    provider = MagicMock()
    provider.create_meeting.side_effect = MeetingSkipped()
    service = InterviewMeetingService(repo, provider=provider)
    result = service.ensure_meeting(42)
    assert result.meeting_url is None


def test_second_ensure_is_idempotent_after_url_set():
    interview = _interview()
    repo = MagicMock()
    repo.get_by_id.return_value = interview
    repo.save.side_effect = lambda item: item
    provider = FakeMeetingProvider()
    service = InterviewMeetingService(repo, notifications=MagicMock(), provider=provider)
    first = service.ensure_meeting(42)
    interview.meeting_url = first.meeting_url
    interview.meeting_external_id = first.meeting_external_id
    second = service.ensure_meeting(42)
    assert second.meeting_url == first.meeting_url
