"""Onboarding Agent exceptions."""


class OnboardingAgentError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class OnboardingAgentValidationError(OnboardingAgentError):
    pass
