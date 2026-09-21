from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

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


class PositionCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    department_id: int | None = None


class PositionUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    department_id: int | None = None


class PositionResponse(BaseModel):
    id: int
    title: str
    description: str | None
    department_id: int | None
    department: str | None
    created_at: datetime
    updated_at: datetime


class EmployeeCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailAddress
    phone: str = Field(min_length=8, max_length=30)
    department_id: int
    position: str | None = Field(default=None, min_length=1, max_length=120)
    position_id: int | None = None
    manager_id: int | None = None
    hire_date: date

    @model_validator(mode="after")
    def require_position(self) -> "EmployeeCreateRequest":
        if self.position_id is None and (self.position is None or not self.position.strip()):
            raise ValueError("Either position_id or position is required")
        return self


class EmployeeUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailAddress | None = None
    phone: str | None = Field(default=None, min_length=8, max_length=30)
    department_id: int | None = None
    position: str | None = Field(default=None, min_length=1, max_length=120)
    position_id: int | None = None
    manager_id: int | None = None
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
    position_id: int | None
    manager_id: int | None
    hire_date: date
    employment_status: EmploymentStatus
    user_id: int | None
    created_at: datetime
    updated_at: datetime


class EmployeeListResponse(BaseModel):
    items: list[EmployeeResponse]
    total: int


class OrgPersonSummary(BaseModel):
    employee_id: int
    full_name: str
    position: str | None
    department: str | None
    has_profile_picture: bool = False


class EmployeeOrganizationResponse(BaseModel):
    employee: OrgPersonSummary
    position: PositionResponse | None
    department: DepartmentResponse | None
    manager: OrgPersonSummary | None


class HierarchyNode(BaseModel):
    employee_id: int
    name: str
    position: str | None
    department: str | None
    children: list["HierarchyNode"] = []


class HierarchyResponse(BaseModel):
    employees: list[HierarchyNode]


class DirectoryEntry(BaseModel):
    employee_id: int
    full_name: str
    position: str | None
    department: str | None
    manager: str | None
    has_profile_picture: bool
    profile_picture_url: str | None = None


class DirectoryResponse(BaseModel):
    items: list[DirectoryEntry]
    total: int
