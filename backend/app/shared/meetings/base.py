from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class MeetingAttendee:
    email: str
    display_name: str | None = None


@dataclass(frozen=True)
class MeetingRequest:
    """Provider-agnostic request to create a timed video meeting."""

    title: str
    starts_at: datetime
    ends_at: datetime
    description: str | None = None
    attendees: tuple[MeetingAttendee, ...] = field(default_factory=tuple)
    idempotency_key: str | None = None


@dataclass(frozen=True)
class MeetingResult:
    meeting_url: str
    external_id: str


class MeetingProvider(ABC):
    """Reusable contract for creating interview video meetings."""

    @abstractmethod
    def create_meeting(self, request: MeetingRequest) -> MeetingResult:
        raise NotImplementedError

    def get_meeting(self, external_id: str) -> MeetingResult | None:
        """Optional lookup by external id. Default: not supported."""
        return None
