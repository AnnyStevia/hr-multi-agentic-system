from app.core.config import Settings, settings as app_settings
from app.shared.meetings.base import MeetingAttendee, MeetingProvider, MeetingRequest, MeetingResult
from app.shared.meetings.exceptions import (
    MeetingConfigurationError,
    MeetingProviderError,
    MeetingSkipped,
)
from app.shared.meetings.fake import FakeMeetingProvider
from app.shared.meetings.noop import NoopMeetingProvider

__all__ = [
    "MeetingAttendee",
    "MeetingConfigurationError",
    "MeetingProvider",
    "MeetingProviderError",
    "MeetingRequest",
    "MeetingResult",
    "MeetingSkipped",
    "get_meeting_provider",
]


def get_meeting_provider(settings: Settings | None = None) -> MeetingProvider:
    """Return the configured meeting provider (noop when Google is not ready)."""
    cfg = settings or app_settings
    provider = (cfg.meeting_provider or "noop").strip().lower()

    if provider in ("", "noop", "none", "disabled"):
        return NoopMeetingProvider()

    if provider == "fake":
        return FakeMeetingProvider()

    if provider == "google":
        from app.shared.meetings.google_calendar import GoogleCalendarMeetProvider

        try:
            return GoogleCalendarMeetProvider.from_settings(cfg)
        except MeetingConfigurationError:
            return NoopMeetingProvider()

    raise MeetingConfigurationError(f"Unsupported MEETING_PROVIDER: {provider}")
