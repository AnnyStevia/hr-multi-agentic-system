import re
from typing import Annotated

from pydantic import AfterValidator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not _EMAIL_RE.match(email):
        raise ValueError("Invalid email address")
    return email


EmailAddress = Annotated[str, AfterValidator(normalize_email)]
