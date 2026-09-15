from app.modules.recruitment.models import ApplicationStatus
from app.shared.exceptions import AppException

ALLOWED_APPLICATION_STATUS_TRANSITIONS: dict[ApplicationStatus, frozenset[ApplicationStatus]] = {
    ApplicationStatus.SUBMITTED: frozenset(
        {ApplicationStatus.SCREENING, ApplicationStatus.REJECTED}
    ),
    ApplicationStatus.SCREENING: frozenset(
        {ApplicationStatus.SHORTLISTED, ApplicationStatus.REJECTED}
    ),
    ApplicationStatus.SHORTLISTED: frozenset(
        {ApplicationStatus.REJECTED, ApplicationStatus.HIRED}
    ),
    ApplicationStatus.REJECTED: frozenset(),
    ApplicationStatus.HIRED: frozenset(),
}


def validate_application_status_transition(
    current: ApplicationStatus,
    target: ApplicationStatus,
) -> None:
    if current == target:
        raise AppException("Application is already in this status", status_code=400)

    allowed = ALLOWED_APPLICATION_STATUS_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise AppException(
            f"Cannot change status from {current.value} to {target.value}",
            status_code=400,
        )
