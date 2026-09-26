from app.shared.meetings.base import MeetingProvider, MeetingRequest, MeetingResult
from app.shared.meetings.exceptions import MeetingSkipped


class NoopMeetingProvider(MeetingProvider):
    """Default when Google Meet is not configured. Leaves interviews without a link."""

    def create_meeting(self, request: MeetingRequest) -> MeetingResult:
        raise MeetingSkipped("Meeting provider is disabled")

    def get_meeting(self, external_id: str) -> MeetingResult | None:
        return None
