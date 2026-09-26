"""Unit tests for MeetingProvider factory and Fake/Google providers (mocked)."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.shared.meetings import (
    MeetingRequest,
    MeetingResult,
    get_meeting_provider,
)
from app.shared.meetings.exceptions import MeetingProviderError, MeetingSkipped
from app.shared.meetings.fake import FakeMeetingProvider
from app.shared.meetings.google_calendar import GoogleCalendarMeetProvider
from app.shared.meetings.noop import NoopMeetingProvider


def _request(**overrides) -> MeetingRequest:
    start = datetime.now(UTC) + timedelta(days=2)
    end = start + timedelta(minutes=30)
    base = {
        "title": "Interview: Ada — Engineer",
        "starts_at": start,
        "ends_at": end,
        "idempotency_key": "interview-42",
    }
    base.update(overrides)
    return MeetingRequest(**base)


def test_factory_defaults_to_noop():
    provider = get_meeting_provider(Settings(meeting_provider="noop"))
    assert isinstance(provider, NoopMeetingProvider)


def test_factory_returns_fake():
    provider = get_meeting_provider(Settings(meeting_provider="fake"))
    assert isinstance(provider, FakeMeetingProvider)


def test_factory_google_incomplete_falls_back_to_noop():
    provider = get_meeting_provider(
        Settings(
            meeting_provider="google",
            google_meet_client_id="",
            google_meet_client_secret="",
            google_meet_refresh_token="",
        )
    )
    assert isinstance(provider, NoopMeetingProvider)


def test_noop_skips_creation():
    with pytest.raises(MeetingSkipped):
        NoopMeetingProvider().create_meeting(_request())


def test_fake_is_deterministic():
    provider = FakeMeetingProvider()
    first = provider.create_meeting(_request(idempotency_key="interview-7"))
    second = provider.create_meeting(_request(idempotency_key="interview-7"))
    assert first.meeting_url == second.meeting_url
    assert first.external_id == second.external_id
    assert first.meeting_url.startswith("https://meet.example.test/")


def test_google_create_meeting_success_with_mocked_service():
    events = MagicMock()
    events.insert.return_value.execute.return_value = {
        "id": "evt-123",
        "hangoutLink": "https://meet.google.com/abc-defg-hij",
        "conferenceData": {"status": {"statusCode": "success"}},
    }
    service = MagicMock()
    service.events.return_value = events
    provider = GoogleCalendarMeetProvider(
        calendar_service=service,
        calendar_id="primary",
        poll_delay_seconds=0,
    )

    result = provider.create_meeting(_request())
    assert result == MeetingResult(
        meeting_url="https://meet.google.com/abc-defg-hij",
        external_id="evt-123",
    )
    events.insert.assert_called_once()
    kwargs = events.insert.call_args.kwargs
    assert kwargs["conferenceDataVersion"] == 1
    events.get.assert_not_called()


def test_google_create_meeting_polls_while_pending_then_succeeds():
    events = MagicMock()
    events.insert.return_value.execute.return_value = {
        "id": "evt-pending",
        "conferenceData": {"status": {"statusCode": "pending"}},
    }
    events.get.return_value.execute.side_effect = [
        {
            "id": "evt-pending",
            "conferenceData": {"status": {"statusCode": "pending"}},
        },
        {
            "id": "evt-pending",
            "hangoutLink": "https://meet.google.com/ready-now",
            "conferenceData": {"status": {"statusCode": "success"}},
        },
    ]
    service = MagicMock()
    service.events.return_value = events
    sleeps: list[float] = []
    provider = GoogleCalendarMeetProvider(
        calendar_service=service,
        poll_attempts=5,
        poll_delay_seconds=0.01,
        sleep_fn=sleeps.append,
    )

    result = provider.create_meeting(_request())
    assert result.meeting_url == "https://meet.google.com/ready-now"
    assert result.external_id == "evt-pending"
    assert events.get.call_count >= 1
    assert len(sleeps) >= 1


def test_google_create_meeting_pending_timeout():
    events = MagicMock()
    pending = {
        "id": "evt-stuck",
        "conferenceData": {"status": {"statusCode": "pending"}},
    }
    events.insert.return_value.execute.return_value = pending
    events.get.return_value.execute.return_value = pending
    service = MagicMock()
    service.events.return_value = events
    provider = GoogleCalendarMeetProvider(
        calendar_service=service,
        poll_attempts=3,
        poll_delay_seconds=0,
        sleep_fn=lambda _s: None,
    )

    with pytest.raises(MeetingProviderError) as exc:
        provider.create_meeting(_request())
    assert "pending" in exc.value.message.lower()


def test_google_create_meeting_failure_is_sanitized():
    events = MagicMock()
    events.insert.return_value.execute.side_effect = RuntimeError("secret token xyz")
    service = MagicMock()
    service.events.return_value = events
    provider = GoogleCalendarMeetProvider(calendar_service=service, poll_delay_seconds=0)

    with pytest.raises(MeetingProviderError) as exc:
        provider.create_meeting(_request())
    assert "secret" not in str(exc.value).lower()
    assert "token" not in str(exc.value).lower()
    assert "Failed to create Google Meet link" in exc.value.message


def test_google_get_meeting_repairs_url_from_entry_points():
    events = MagicMock()
    events.get.return_value.execute.return_value = {
        "id": "evt-9",
        "conferenceData": {
            "entryPoints": [{"entryPointType": "video", "uri": "https://meet.google.com/zz"}],
        },
    }
    service = MagicMock()
    service.events.return_value = events
    provider = GoogleCalendarMeetProvider(calendar_service=service)
    result = provider.get_meeting("evt-9")
    assert result is not None
    assert result.meeting_url == "https://meet.google.com/zz"
