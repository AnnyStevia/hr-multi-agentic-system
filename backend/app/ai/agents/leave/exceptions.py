"""Leave Agent exceptions."""


class LeaveAgentError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class LeaveAgentValidationError(LeaveAgentError):
    pass
