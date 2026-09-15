from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.identity.models import Candidate

from app.core.database import Base


class JobStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"


class EmploymentType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True
    )
    position: Mapped[str | None] = mapped_column(String(120), nullable=True)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    employment_type: Mapped[EmploymentType] = mapped_column(
        SAEnum(
            EmploymentType,
            name="employment_type",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=EmploymentType.FULL_TIME,
    )
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(
            JobStatus,
            name="job_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=JobStatus.DRAFT,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    created_by = relationship("User")
    department_rel = relationship("Department")
    questions: Mapped[list["JobQuestion"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobQuestion.display_order",
    )
    applications: Mapped[list["Application"]] = relationship(back_populates="job")


class QuestionType(str, Enum):
    SHORT_TEXT = "short_text"
    LONG_TEXT = "long_text"
    NUMBER = "number"
    YES_NO = "yes_no"


class ApplicationStatus(str, Enum):
    SUBMITTED = "submitted"
    SCREENING = "screening"
    SHORTLISTED = "shortlisted"
    REJECTED = "rejected"


class DocumentKind(str, Enum):
    CV = "cv"
    COVER_LETTER = "cover_letter"


class JobQuestion(Base):
    __tablename__ = "job_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[QuestionType] = mapped_column(
        SAEnum(
            QuestionType,
            name="question_type",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    required: Mapped[bool] = mapped_column(default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(nullable=False, default=0)

    job: Mapped["Job"] = relationship(back_populates="questions")
    answers: Mapped[list["ApplicationAnswer"]] = relationship(back_populates="question")


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("candidate_id", "job_id", name="uq_application_candidate_job"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[ApplicationStatus] = mapped_column(
        SAEnum(
            ApplicationStatus,
            name="application_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=ApplicationStatus.SUBMITTED,
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    candidate: Mapped["Candidate"] = relationship()
    job: Mapped["Job"] = relationship(back_populates="applications")
    answers: Mapped[list["ApplicationAnswer"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    education: Mapped[list["ApplicationEducation"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    experience: Mapped[list["ApplicationExperience"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    documents: Mapped[list["ApplicationDocument"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )


class ApplicationAnswer(Base):
    __tablename__ = "application_answers"
    __table_args__ = (UniqueConstraint("application_id", "question_id", name="uq_application_question"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("job_questions.id", ondelete="RESTRICT"), nullable=False
    )
    value: Mapped[str] = mapped_column(Text, nullable=False)

    application: Mapped["Application"] = relationship(back_populates="answers")
    question: Mapped["JobQuestion"] = relationship(back_populates="answers")


class ApplicationEducation(Base):
    __tablename__ = "application_education"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    institution: Mapped[str] = mapped_column(String(200), nullable=False)
    degree: Mapped[str | None] = mapped_column(String(120), nullable=True)
    field_of_study: Mapped[str | None] = mapped_column(String(120), nullable=True)
    start_year: Mapped[int | None] = mapped_column(nullable=True)
    end_year: Mapped[int | None] = mapped_column(nullable=True)


    application: Mapped["Application"] = relationship(back_populates="education")


class ApplicationExperience(Base):
    __tablename__ = "application_experience"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    start_year: Mapped[int | None] = mapped_column(nullable=True)
    end_year: Mapped[int | None] = mapped_column(nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    application: Mapped["Application"] = relationship(back_populates="experience")


class ApplicationDocument(Base):
    __tablename__ = "application_documents"
    __table_args__ = (UniqueConstraint("application_id", "kind", name="uq_application_document_kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[DocumentKind] = mapped_column(
        SAEnum(
            DocumentKind,
            name="document_kind",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    application: Mapped["Application"] = relationship(back_populates="documents")
