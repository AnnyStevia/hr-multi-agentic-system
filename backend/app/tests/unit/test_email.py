import pytest

from app.shared.email import normalize_email


def test_normalize_email_accepts_local_domain():
    assert normalize_email("Admin@hr-platform.local") == "admin@hr-platform.local"


def test_normalize_email_rejects_invalid():
    with pytest.raises(ValueError):
        normalize_email("not-an-email")
