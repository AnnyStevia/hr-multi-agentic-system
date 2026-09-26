class MeetingProviderError(Exception):
    """Safe, user/server-facing meeting provider failure (no secrets)."""

    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class MeetingConfigurationError(MeetingProviderError):
    def __init__(self, message: str = "Meeting provider is not configured"):
        super().__init__(message, status_code=503)


class MeetingSkipped(MeetingProviderError):
    """Provider intentionally skipped meeting creation (e.g. noop)."""

    def __init__(self, message: str = "Meeting creation skipped"):
        super().__init__(message, status_code=200)
