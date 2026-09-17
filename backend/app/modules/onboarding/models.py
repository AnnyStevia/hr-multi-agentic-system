from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.modules.employees.models import Employee


class OnboardingStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class OnboardingTaskStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"


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


class OnboardingTask(Base):
    __tablename__ = "onboarding_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    onboarding_id: Mapped[int] = mapped_column(
        ForeignKey("onboardings.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
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
