from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from app.shared.email import EmailAddress


def strip_non_empty(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("This field cannot be empty")
    return stripped


PersonName = Annotated[str, AfterValidator(strip_non_empty), Field(max_length=100)]


class LoginRequest(BaseModel):
    email: EmailAddress
    password: str = Field(min_length=1)


class CreateHRRequest(BaseModel):
    model_config = {"extra": "forbid"}

    first_name: PersonName
    last_name: PersonName
    email: EmailAddress
    password: str = Field(min_length=8, max_length=72)
    phone: str = Field(min_length=8, max_length=30)
    department_id: int
    position: str = Field(min_length=1, max_length=120)
    hire_date: date


class CandidateRegisterRequest(BaseModel):
    model_config = {"extra": "forbid"}

    first_name: PersonName
    last_name: PersonName
    email: EmailAddress
    password: str = Field(min_length=8, max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RoleResponse(BaseModel):
    id: int
    name: str
    description: str | None = None

    model_config = {"from_attributes": True}


class PermissionResponse(BaseModel):
    id: int
    name: str
    resource: str
    action: str
    description: str | None = None

    model_config = {"from_attributes": True}


class UserListItem(BaseModel):
    id: int
    email: EmailAddress
    first_name: str
    last_name: str
    full_name: str
    is_active: bool
    roles: list[RoleResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: int
    email: EmailAddress
    first_name: str
    last_name: str
    full_name: str
    is_active: bool
    roles: list[RoleResponse] = []
    permissions: list[str] = []
    phone: str | None = None

    model_config = {"from_attributes": True}
