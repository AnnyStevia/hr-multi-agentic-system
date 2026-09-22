from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.documents.models import DocumentType

if TYPE_CHECKING:
    from app.modules.employees.models import Employee
    from app.modules.training.models import Training


class OnboardingStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class OnboardingTaskStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"


class OnboardingTaskType(str, Enum):
    PROFILE_PERSONAL_INFO = "profile_personal_info"
    PROFILE_PICTURE = "profile_picture"
    EDUCATION = "education"
    EXPERIENCE = "experience"
    DOCUMENT = "document"
    TRAINING = "training"
    ACKNOWLEDGEMENT = "acknowledgement"
    MANUAL = "manual"


class Onboarding(Base):
    __tablename__ = "onboardings"
    __table_args__ = (UniqueConstraint("employee_id", name="uq_onboarding_employee_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[OnboardingStatus] = mapped_column(
        SAEnum(
            OnboardingStatus,
            name="onboarding_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=OnboardingStatus.IN_PROGRESS,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    employee: Mapped[Employee] = relationship()
    tasks: Mapped[list[OnboardingTask]] = relationship(
        back_populates="onboarding",
        cascade="all, delete-orphan",
    )


class OnboardingTaskTemplate(Base):
    __tablename__ = "onboarding_task_templates"
    __table_args__ = (UniqueConstraint("title", name="uq_onboarding_task_templates_title"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_type: Mapped[OnboardingTaskType] = mapped_column(
        SAEnum(
            OnboardingTaskType,
            name="onboarding_task_type",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    document_type: Mapped[DocumentType | None] = mapped_column(
        SAEnum(
            DocumentType,
            name="employee_document_type",
            values_callable=lambda enum: [item.value for item in enum],
            create_type=False,
        ),
        nullable=True,
    )
    training_id: Mapped[int | None] = mapped_column(
        ForeignKey("trainings.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tasks: Mapped[list[OnboardingTask]] = relationship(back_populates="template")
    training: Mapped[Training | None] = relationship()


class OnboardingTask(Base):
    __tablename__ = "onboarding_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    onboarding_id: Mapped[int] = mapped_column(
        ForeignKey("onboardings.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("onboarding_task_templates.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_type: Mapped[OnboardingTaskType] = mapped_column(
        SAEnum(
            OnboardingTaskType,
            name="onboarding_task_type",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=OnboardingTaskType.MANUAL,
    )
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    document_type: Mapped[DocumentType | None] = mapped_column(
        SAEnum(
            DocumentType,
            name="employee_document_type",
            values_callable=lambda enum: [item.value for item in enum],
            create_type=False,
        ),
        nullable=True,
    )
    training_id: Mapped[int | None] = mapped_column(
        ForeignKey("trainings.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[OnboardingTaskStatus] = mapped_column(
        SAEnum(
            OnboardingTaskStatus,
            name="onboarding_task_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=OnboardingTaskStatus.PENDING,
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    onboarding: Mapped[Onboarding] = relationship(back_populates="tasks")
    template: Mapped[OnboardingTaskTemplate | None] = relationship(back_populates="tasks")
    training: Mapped[Training | None] = relationship()
