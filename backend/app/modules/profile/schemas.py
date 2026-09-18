from datetime import date, datetime

from pydantic import BaseModel, Field


class ProfileUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    phone: str | None = Field(default=None, min_length=8, max_length=30)
    date_of_birth: date | None = None
    address: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)


class EmployeeProfileResponse(BaseModel):
    employee_id: int
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
    date_of_birth: date | None
    address: str | None
    city: str | None
    country: str | None
    has_profile_picture: bool
    profile_picture_filename: str | None
    profile_picture_content_type: str | None


class PresignedProfilePictureUrlResponse(BaseModel):
    url: str
    filename: str
    content_type: str
    expires_in: int


class EducationCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    institution: str = Field(min_length=1, max_length=200)
    degree: str = Field(min_length=1, max_length=200)
    field_of_study: str = Field(min_length=1, max_length=200)
    start_date: date
    end_date: date | None = None
    description: str | None = None


class EducationUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    institution: str | None = Field(default=None, min_length=1, max_length=200)
    degree: str | None = Field(default=None, min_length=1, max_length=200)
    field_of_study: str | None = Field(default=None, min_length=1, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None


class EducationResponse(BaseModel):
    id: int
    employee_id: int
    institution: str
    degree: str
    field_of_study: str
    start_date: date
    end_date: date | None
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExperienceCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    company: str = Field(min_length=1, max_length=200)
    position: str = Field(min_length=1, max_length=200)
    description: str | None = None
    start_date: date
    end_date: date | None = None


class ExperienceUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    company: str | None = Field(default=None, min_length=1, max_length=200)
    position: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class ExperienceResponse(BaseModel):
    id: int
    employee_id: int
    company: str
    position: str
    description: str | None
    start_date: date
    end_date: date | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
