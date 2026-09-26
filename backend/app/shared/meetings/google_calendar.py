"""Google Calendar API provider that creates events with Meet conference data."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import timezone
from typing import Any

from app.core.config import Settings
from app.shared.meetings.base import MeetingProvider, MeetingRequest, MeetingResult
from app.shared.meetings.exceptions import MeetingConfigurationError, MeetingProviderError

logger = logging.getLogger(__name__)

CALENDAR_EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"
HTTP_TIMEOUT_SECONDS = 30

# Bounded poll when Google returns conferenceData status pending / no URI yet.
CONFERENCE_POLL_ATTEMPTS = 5
CONFERENCE_POLL_DELAY_SECONDS = 1.5


class GoogleCalendarMeetProvider(MeetingProvider):
    """Creates Meet links via Calendar events.insert + conferenceData."""

    def __init__(
        self,
        *,
        calendar_service: Any,
        calendar_id: str = "primary",
        poll_attempts: int = CONFERENCE_POLL_ATTEMPTS,
        poll_delay_seconds: float = CONFERENCE_POLL_DELAY_SECONDS,
        sleep_fn=time.sleep,
    ):
        self._service = calendar_service
        self._calendar_id = calendar_id or "primary"
        self._poll_attempts = max(1, poll_attempts)
        self._poll_delay_seconds = max(0.0, poll_delay_seconds)
        self._sleep = sleep_fn

    @classmethod
    def from_settings(cls, settings: Settings) -> "GoogleCalendarMeetProvider":
        client_id = (settings.google_meet_client_id or "").strip()
        client_secret = (settings.google_meet_client_secret or "").strip()
        refresh_token = (settings.google_meet_refresh_token or "").strip()
        if not client_id or not client_secret or not refresh_token:
            raise MeetingConfigurationError("Google Meet OAuth credentials are incomplete")

        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise MeetingConfigurationError(
                "Google Calendar client libraries are not installed"
            ) from exc

        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=[CALENDAR_EVENTS_SCOPE],
        )
        try:
            credentials.refresh(Request())
        except Exception as exc:
            logger.warning("Google Meet token refresh failed: %s", type(exc).__name__)
            raise MeetingProviderError("Failed to authorize Google Meet organizer") from exc

        service = build(
            "calendar",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )
        calendar_id = (settings.google_meet_calendar_id or "primary").strip() or "primary"
        return cls(calendar_service=service, calendar_id=calendar_id)

    def create_meeting(self, request: MeetingRequest) -> MeetingResult:
        starts = _as_utc_iso(request.starts_at)
        ends = _as_utc_iso(request.ends_at)
        body: dict[str, Any] = {
            "summary": request.title,
            "description": request.description or "",
            "start": {"dateTime": starts, "timeZone": "UTC"},
            "end": {"dateTime": ends, "timeZone": "UTC"},
            "conferenceData": {
                "createRequest": {
                    "requestId": (request.idempotency_key or uuid.uuid4().hex)[:64],
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
        }
        attendees = [
            {"email": item.email, **({"displayName": item.display_name} if item.display_name else {})}
            for item in request.attendees
            if item.email
        ]
        if attendees:
            body["attendees"] = attendees

        try:
            created = (
                self._service.events()
                .insert(
                    calendarId=self._calendar_id,
                    body=body,
                    conferenceDataVersion=1,
                    sendUpdates="none",
                )
                .execute(num_retries=0)
            )
        except Exception as exc:
            logger.warning("Google Calendar create_meeting failed: %s", type(exc).__name__)
            raise MeetingProviderError("Failed to create Google Meet link") from exc

        return self._resolve_meeting_result(created)

    def get_meeting(self, external_id: str) -> MeetingResult | None:
        if not external_id.strip():
            return None
        event = self._fetch_event(external_id)
        if event is None:
            return None
        try:
            return _result_from_event(event, require_url=True)
        except MeetingProviderError:
            return None

    def delete_meeting(self, external_id: str) -> bool:
        """Best-effort cleanup for smoke tests. Returns True if delete succeeded."""
        if not external_id.strip():
            return False
        try:
            (
                self._service.events()
                .delete(calendarId=self._calendar_id, eventId=external_id)
                .execute(num_retries=0)
            )
            return True
        except Exception as exc:
            logger.warning("Google Calendar delete_meeting failed: %s", type(exc).__name__)
            return False

    def _resolve_meeting_result(self, event: dict[str, Any]) -> MeetingResult:
        """Return Meet URL, polling briefly if conference creation is still pending."""
        try:
            return _result_from_event(event, require_url=True)
        except MeetingProviderError:
            if not _conference_pending_or_missing_url(event):
                raise

        external_id = (event.get("id") or "").strip()
        if not external_id:
            raise MeetingProviderError("Google Calendar event missing id")

        last_event = event
        for attempt in range(1, self._poll_attempts + 1):
            if attempt > 1 or _conference_pending_or_missing_url(last_event):
                if self._poll_delay_seconds > 0:
                    self._sleep(self._poll_delay_seconds)
            fetched = self._fetch_event(external_id)
            if fetched is None:
                continue
            last_event = fetched
            status = _conference_status(fetched)
            if status:
                logger.info(
                    "Google Meet conference status=%s attempt=%s event_id=%s",
                    status,
                    attempt,
                    external_id,
                )
            try:
                return _result_from_event(fetched, require_url=True)
            except MeetingProviderError:
                if not _conference_pending_or_missing_url(fetched):
                    raise
                continue

        raise MeetingProviderError("Google Meet conference is still pending")

    def _fetch_event(self, external_id: str) -> dict[str, Any] | None:
        try:
            return (
                self._service.events()
                .get(calendarId=self._calendar_id, eventId=external_id)
                .execute(num_retries=0)
            )
        except Exception as exc:
            logger.warning("Google Calendar get_meeting failed: %s", type(exc).__name__)
            return None


def _as_utc_iso(value) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def _conference_status(event: dict[str, Any]) -> str | None:
    status_obj = (event.get("conferenceData") or {}).get("status") or {}
    status = status_obj.get("statusCode") or status_obj.get("status")
    return str(status).lower() if status else None


def _extract_meeting_url(event: dict[str, Any]) -> str:
    meeting_url = (event.get("hangoutLink") or "").strip()
    if meeting_url:
        return meeting_url
    entry_points = (event.get("conferenceData") or {}).get("entryPoints") or []
    for entry in entry_points:
        if entry.get("entryPointType") == "video" and entry.get("uri"):
            return str(entry["uri"]).strip()
    return ""


def _conference_pending_or_missing_url(event: dict[str, Any]) -> bool:
    if _extract_meeting_url(event):
        return False
    status = _conference_status(event)
    if status in ("pending", "failure"):
        return status == "pending"
    # No URL yet and no terminal failure → treat as pending/async
    return True


def _result_from_event(event: dict[str, Any], *, require_url: bool = True) -> MeetingResult:
    external_id = (event.get("id") or "").strip()
    if not external_id:
        raise MeetingProviderError("Google Calendar event missing id")

    status = _conference_status(event)
    if status == "failure":
        raise MeetingProviderError("Google Meet conference creation failed")

    meeting_url = _extract_meeting_url(event)
    if require_url and not meeting_url:
        raise MeetingProviderError("Google Calendar event missing Meet join URL")

    return MeetingResult(meeting_url=meeting_url, external_id=external_id)
