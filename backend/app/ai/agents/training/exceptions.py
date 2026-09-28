"""Training Agent exceptions."""


class TrainingAgentError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class TrainingAgentValidationError(TrainingAgentError):
    pass
