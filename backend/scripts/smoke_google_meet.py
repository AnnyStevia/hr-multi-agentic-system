"""Optional live Google Meet smoke (opt-in via GOOGLE_MEET_LIVE_SMOKE=1).

Creates a short-lived Calendar event with Meet, verifies get_meeting, then deletes.
Never prints tokens or secrets. Success requires a real meet.google.com URL.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta

# Ensure backend package imports work when run as a script.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.shared.meetings import MeetingRequest, get_meeting_provider
from app.shared.meetings.google_calendar import GoogleCalendarMeetProvider


def main() -> int:
    if os.environ.get("GOOGLE_MEET_LIVE_SMOKE", "").strip() != "1":
        print("Refusing to run: set GOOGLE_MEET_LIVE_SMOKE=1 to opt in.")
        return 2

    missing: list[str] = []
    if (settings.meeting_provider or "").strip().lower() != "google":
        missing.append(
            "MEETING_PROVIDER=google (current=%r)" % (settings.meeting_provider or "")
        )
    if not (settings.google_meet_client_id or "").strip():
        missing.append("GOOGLE_MEET_CLIENT_ID")
    if not (settings.google_meet_client_secret or "").strip():
        missing.append("GOOGLE_MEET_CLIENT_SECRET")
    if not (settings.google_meet_refresh_token or "").strip():
        missing.append("GOOGLE_MEET_REFRESH_TOKEN")
    if missing:
        print("STOP: live Google Meet credentials incomplete. Missing / incorrect:")
        for name in missing:
            print(f"  - {name}")
        print("Checklist:")
        print("  1. GCP project + enable Google Calendar API")
        print("  2. OAuth consent (Testing + test user) + Desktop OAuth client")
        print("  3. Run scripts/obtain_google_meet_refresh_token.py")
        print("  4. Paste GOOGLE_MEET_* + MEETING_PROVIDER=google into backend/.env")
        print("See docs/google-meet-integration.md")
        return 2

    provider = get_meeting_provider(settings)
    if not isinstance(provider, GoogleCalendarMeetProvider):
        print(
            "STOP: provider is %s — refuse fake/noop. "
            "Check MEETING_PROVIDER=google and complete GOOGLE_MEET_* credentials."
            % type(provider).__name__
        )
        return 2

    start = datetime.now(UTC) + timedelta(minutes=20)
    end = start + timedelta(minutes=15)
    stamp = int(start.timestamp())
    title = f"[HR-SMOKE] Meet validation {stamp}"

    conference_status = "unknown"
    external_id: str | None = None
    meeting_url: str | None = None
    cleanup = "SKIPPED"

    try:
        result = provider.create_meeting(
            MeetingRequest(
                title=title,
                starts_at=start,
                ends_at=end,
                description="Automated HR-SMOKE — safe to delete.",
                idempotency_key=f"hr-smoke-{stamp}",
            )
        )
        external_id = result.external_id
        meeting_url = result.meeting_url

        # Best-effort status from a follow-up get (create already polled pending).
        fetched = provider.get_meeting(external_id)
        if fetched is None:
            print("STOP: get_meeting returned None after create.")
            cleanup = _cleanup(provider, external_id)
            _print_summary(conference_status, meeting_url, cleanup, ok=False)
            return 1
        if fetched.meeting_url != meeting_url:
            print(
                "STOP: get_meeting URL mismatch "
                f"(create={meeting_url!r} get={fetched.meeting_url!r})."
            )
            cleanup = _cleanup(provider, external_id)
            _print_summary(conference_status, meeting_url, cleanup, ok=False)
            return 1
        if "meet.google.com" not in (meeting_url or "").lower():
            print("STOP: meeting_url is not a meet.google.com link:", meeting_url)
            cleanup = _cleanup(provider, external_id)
            _print_summary(conference_status, meeting_url, cleanup, ok=False)
            return 1

        conference_status = "success"
        cleanup = _cleanup(provider, external_id)
        _print_summary(conference_status, meeting_url, cleanup, ok=True)
        if cleanup != "OK":
            print(f"Manual delete needed for event id: {external_id}")
            return 1
        print("ok")
        return 0
    except Exception as exc:
        # Sanitized message only — never dump raw SDK / token details.
        name = type(exc).__name__
        msg = getattr(exc, "message", None) or str(exc)
        print(f"STOP: {name}: {msg}")
        if external_id:
            cleanup = _cleanup(provider, external_id)
        _print_summary(conference_status, meeting_url, cleanup, ok=False)
        return 1


def _cleanup(provider: GoogleCalendarMeetProvider, external_id: str) -> str:
    if provider.delete_meeting(external_id):
        return "OK"
    print(f"Cleanup FAILED — delete manually in Google Calendar. event_id={external_id}")
    return "FAILED"


def _print_summary(
    conference_status: str,
    meeting_url: str | None,
    cleanup: str,
    *,
    ok: bool,
) -> None:
    has_url = "YES" if meeting_url and "meet.google.com" in meeting_url.lower() else "NO"
    print("--- smoke summary ---")
    print(f"conference_status: {conference_status}")
    print(f"meet_url: {has_url}")
    if meeting_url and has_url == "YES":
        print(f"meeting_url: {meeting_url}")
    print(f"cleanup: {cleanup}")
    print(f"result: {'PASS' if ok and cleanup == 'OK' else 'FAIL'}")
    print("--- end ---")


if __name__ == "__main__":
    raise SystemExit(main())
