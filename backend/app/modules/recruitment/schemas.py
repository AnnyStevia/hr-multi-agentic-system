from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.recruitment.models import (
    ApplicationStatus,
    DocumentKind,
    EmploymentType,
    JobStatus,
    QuestionType,
)


class JobQuestionInput(BaseModel):
    model_config = {"extra": "forbid"}

    prompt: str = Field(min_length=1, max_length=500)
    question_type: QuestionType
    required: bool = True
    display_order: int | None = Field(default=None, ge=0)


class JobQuestionResponse(BaseModel):
    id: int
    prompt: str
    question_type: QuestionType
    required: bool
    display_order: int

    model_config = {"from_attributes": True}


class JobCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    department_id: int | None = None
    position: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=120)
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    requirements: str | None = None
    questions: list[JobQuestionInput] = Field(default_factory=list)


class JobUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1)
    department_id: int | None = None
    position: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=120)
    employment_type: EmploymentType | None = None
    requirements: str | None = None
    questions: list[JobQuestionInput] | None = None


class JobResponse(BaseModel):
    id: int
    title: str
    description: str
    department_id: int | None = None
    department: str | None
    position: str | None
    location: str | None
    employment_type: EmploymentType
    requirements: str | None
    status: JobStatus
    published_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    created_by_user_id: int
    questions: list[JobQuestionResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class EducationInput(BaseModel):
    model_config = {"extra": "forbid"}

    institution: str = Field(min_length=1, max_length=200)
    degree: str | None = Field(default=None, max_length=120)
    field_of_study: str | None = Field(default=None, max_length=120)
    start_year: int | None = Field(default=None, ge=1950, le=2100)
    end_year: int | None = Field(default=None, ge=1950, le=2100)


class ExperienceInput(BaseModel):
    model_config = {"extra": "forbid"}

    company: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=120)
    start_year: int | None = Field(default=None, ge=1950, le=2100)
    end_year: int | None = Field(default=None, ge=1950, le=2100)
    description: str | None = None


class AnswerInput(BaseModel):
    model_config = {"extra": "forbid"}

    question_id: int
    value: str = Field(min_length=1, max_length=4000)


class ApplicationPayload(BaseModel):
    model_config = {"extra": "forbid"}

    phone: str = Field(min_length=1, max_length=30)
    education: list[EducationInput] = Field(min_length=1)
    experience: list[ExperienceInput] = Field(min_length=1)
    answers: list[AnswerInput] = Field(default_factory=list)


class CandidateSummary(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    full_name: str
    email: str
    phone: str | None = None


class JobSummary(BaseModel):
    id: int
    title: str
    department: str | None
    department_id: int | None = None
    status: JobStatus


class EducationResponse(BaseModel):
    id: int
    institution: str
    degree: str | None
    field_of_study: str | None
    start_year: int | None
    end_year: int | None

    model_config = {"from_attributes": True}


class ExperienceResponse(BaseModel):
    id: int
    company: str
    title: str
    start_year: int | None
    end_year: int | None
    description: str | None

    model_config = {"from_attributes": True}


class AnswerResponse(BaseModel):
    question_id: int
    prompt: str
    question_type: QuestionType
    required: bool
    value: str


class DocumentResponse(BaseModel):
    id: int
    kind: DocumentKind
    original_filename: str
    content_type: str
    size_bytes: int

    model_config = {"from_attributes": True}


class ApplicationListItem(BaseModel):
    id: int
    status: ApplicationStatus
    submitted_at: datetime
    candidate: CandidateSummary
    has_cv: bool
    has_cover_letter: bool


class ApplicationStatusUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    status: ApplicationStatus


class ApplicationDetail(BaseModel):
    id: int
    status: ApplicationStatus
    submitted_at: datetime
    created_at: datetime
    updated_at: datetime
    candidate: CandidateSummary
    job: JobSummary
    education: list[EducationResponse]
    experience: list[ExperienceResponse]
    answers: list[AnswerResponse]
    documents: list[DocumentResponse]


class PresignedDocumentResponse(BaseModel):
    url: str
    filename: str
    content_type: str
    expires_in: int
    download: bool
