from app.modules.recruitment.models import ApplicationStatus
from app.modules.recruitment.status_transitions import validate_application_status_transition
from app.shared.exceptions import AppException
import pytest


def test_submitted_can_move_to_screening_or_rejected():
    validate_application_status_transition(ApplicationStatus.SUBMITTED, ApplicationStatus.SCREENING)
    validate_application_status_transition(ApplicationStatus.SUBMITTED, ApplicationStatus.REJECTED)


def test_screening_can_move_to_shortlisted_or_rejected():
    validate_application_status_transition(ApplicationStatus.SCREENING, ApplicationStatus.SHORTLISTED)
    validate_application_status_transition(ApplicationStatus.SCREENING, ApplicationStatus.REJECTED)


def test_shortlisted_can_move_to_rejected_or_hired():
    validate_application_status_transition(ApplicationStatus.SHORTLISTED, ApplicationStatus.REJECTED)
    validate_application_status_transition(ApplicationStatus.SHORTLISTED, ApplicationStatus.HIRED)


@pytest.mark.parametrize(
    "current,target",
    [
        (ApplicationStatus.SUBMITTED, ApplicationStatus.SHORTLISTED),
        (ApplicationStatus.SUBMITTED, ApplicationStatus.SUBMITTED),
        (ApplicationStatus.SCREENING, ApplicationStatus.SUBMITTED),
        (ApplicationStatus.SHORTLISTED, ApplicationStatus.SUBMITTED),
        (ApplicationStatus.SHORTLISTED, ApplicationStatus.SCREENING),
        (ApplicationStatus.REJECTED, ApplicationStatus.SCREENING),
        (ApplicationStatus.REJECTED, ApplicationStatus.SHORTLISTED),
        (ApplicationStatus.REJECTED, ApplicationStatus.SUBMITTED),
        (ApplicationStatus.HIRED, ApplicationStatus.SHORTLISTED),
        (ApplicationStatus.HIRED, ApplicationStatus.REJECTED),
    ],
)
def test_disallowed_status_transitions_are_rejected(current, target):
    with pytest.raises(AppException) as exc:
        validate_application_status_transition(current, target)
    assert exc.value.status_code == 400
