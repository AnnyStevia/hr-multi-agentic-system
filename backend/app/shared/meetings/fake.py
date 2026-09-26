from hashlib import sha1

from app.shared.meetings.base import MeetingProvider, MeetingRequest, MeetingResult


class FakeMeetingProvider(MeetingProvider):
    """Deterministic provider for tests and local development without Google."""

    def create_meeting(self, request: MeetingRequest) -> MeetingResult:
        seed = request.idempotency_key or f"{request.title}:{request.starts_at.isoformat()}"
        digest = sha1(seed.encode("utf-8")).hexdigest()[:12]
        return MeetingResult(
            meeting_url=f"https://meet.example.test/{digest}",
            external_id=f"fake-event-{digest}",
        )

    def get_meeting(self, external_id: str) -> MeetingResult | None:
        if not external_id.startswith("fake-event-"):
            return None
        digest = external_id.removeprefix("fake-event-")
        return MeetingResult(
            meeting_url=f"https://meet.example.test/{digest}",
            external_id=external_id,
        )
