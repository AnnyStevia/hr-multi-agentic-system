from datetime import date, datetime

from pydantic import BaseModel, Field

from app.modules.employees.models import DepartmentStatus, EmploymentStatus
from app.shared.email import EmailAddress


class DepartmentCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(min_length=1, max_length=120)


class DepartmentUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(min_length=1, max_length=120)


class DepartmentResponse(BaseModel):
    id: int
    name: str
    status: DepartmentStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EmployeeCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailAddress
    phone: str = Field(min_length=8, max_length=30)
    department_id: int
    position: str = Field(min_length=1, max_length=120)
    hire_date: date


class EmployeeUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailAddress | None = None
    phone: str | None = Field(default=None, min_length=8, max_length=30)
    department_id: int | None = None
    position: str | None = Field(default=None, min_length=1, max_length=120)
    hire_date: date | None = None


class EmployeeResponse(BaseModel):
    id: int
    employee_number: str
    first_name: str
    last_name: str
    full_name: str
    email: str
    phone: str
    department_id: int
    department: str
    position: str
    hire_date: date
    employment_status: EmploymentStatus
    user_id: int | None
    created_at: datetime
    updated_at: datetime


class EmployeeListResponse(BaseModel):
    items: list[EmployeeResponse]
    total: int
