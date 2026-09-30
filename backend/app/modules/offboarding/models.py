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
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.modules.employees.models import Employee
    from app.modules.identity.models import User


class OffboardingReason(str, Enum):
    RESIGNATION = "resignation"
    END_OF_CONTRACT = "end_of_contract"
    TERMINATION = "termination"
    RETIREMENT = "retirement"
    OTHER = "other"


class OffboardingStatus(str, Enum):
    INITIATED = "initiated"
    IN_PROGRESS = "in_progress"
    PENDING_CLEARANCE = "pending_clearance"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OffboardingTaskCategory(str, Enum):
    DOCUMENTS = "documents"
    HANDOVER = "handover"
    EQUIPMENT = "equipment"
    ACCESS = "access"
    ADMINISTRATION = "administration"
    OTHER = "other"


class OffboardingTaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class OffboardingClearanceCategory(str, Enum):
    EQUIPMENT = "equipment"
    ACCESS = "access"


class OffboardingClearanceStatus(str, Enum):
    PENDING = "pending"
    CLEARED = "cleared"
    NOT_APPLICABLE = "not_applicable"


class ExitInterviewStatus(str, Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


ACTIVE_EXIT_INTERVIEW_STATUSES = frozenset(
    {
        ExitInterviewStatus.SCHEDULED,
        ExitInterviewStatus.COMPLETED,
    }
)


ACTIVE_OFFBOARDING_STATUSES = frozenset(
    {
        OffboardingStatus.INITIATED,
        OffboardingStatus.IN_PROGRESS,
        OffboardingStatus.PENDING_CLEARANCE,
    }
)

TERMINAL_TASK_STATUSES = frozenset(
    {
        OffboardingTaskStatus.COMPLETED,
        OffboardingTaskStatus.SKIPPED,
    }
)


class OffboardingCase(Base):
    __tablename__ = "offboarding_cases"
    __table_args__ = (
        Index(
            "uq_offboarding_cases_one_active_per_employee",
            "employee_id",
            unique=True,
            postgresql_where=text(
                "status IN ('initiated', 'in_progress', 'pending_clearance')"
            ),
            sqlite_where=text(
                "status IN ('initiated', 'in_progress', 'pending_clearance')"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    reason: Mapped[OffboardingReason] = mapped_column(
        SAEnum(
            OffboardingReason,
            name="offboarding_reason",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    reason_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_working_day: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[OffboardingStatus] = mapped_column(
        SAEnum(
            OffboardingStatus,
            name="offboarding_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=OffboardingStatus.INITIATED,
        index=True,
    )
    initiated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    employee: Mapped[Employee] = relationship()
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_user_id])
    tasks: Mapped[list[OffboardingTask]] = relationship(
        back_populates="offboarding_case",
        cascade="all, delete-orphan",
    )
    clearance_items: Mapped[list[OffboardingClearanceItem]] = relationship(
        back_populates="offboarding_case",
        cascade="all, delete-orphan",
    )
    exit_interviews: Mapped[list[ExitInterview]] = relationship(
        back_populates="offboarding_case",
        cascade="all, delete-orphan",
    )


class OffboardingTask(Base):
    __tablename__ = "offboarding_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    offboarding_case_id: Mapped[int] = mapped_column(
        ForeignKey("offboarding_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[OffboardingTaskCategory] = mapped_column(
        SAEnum(
            OffboardingTaskCategory,
            name="offboarding_task_category",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    status: Mapped[OffboardingTaskStatus] = mapped_column(
        SAEnum(
            OffboardingTaskStatus,
            name="offboarding_task_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=OffboardingTaskStatus.PENDING,
        index=True,
    )
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    assigned_to_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    offboarding_case: Mapped[OffboardingCase] = relationship(back_populates="tasks")
    assigned_to: Mapped[Employee | None] = relationship(foreign_keys=[assigned_to_employee_id])
    completed_by: Mapped[User | None] = relationship(foreign_keys=[completed_by_user_id])


class OffboardingClearanceItem(Base):
    __tablename__ = "offboarding_clearance_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    offboarding_case_id: Mapped[int] = mapped_column(
        ForeignKey("offboarding_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[OffboardingClearanceCategory] = mapped_column(
        SAEnum(
            OffboardingClearanceCategory,
            name="offboarding_clearance_category",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    item: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[OffboardingClearanceStatus] = mapped_column(
        SAEnum(
            OffboardingClearanceStatus,
            name="offboarding_clearance_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=OffboardingClearanceStatus.PENDING,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    offboarding_case: Mapped[OffboardingCase] = relationship(back_populates="clearance_items")
    completed_by: Mapped[User | None] = relationship(foreign_keys=[completed_by_user_id])


class ExitInterview(Base):
    __tablename__ = "exit_interviews"
    __table_args__ = (
        Index(
            "uq_exit_interviews_one_active_per_case",
            "offboarding_case_id",
            unique=True,
            postgresql_where=text("status IN ('scheduled', 'completed')"),
            sqlite_where=text("status IN ('scheduled', 'completed')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    offboarding_case_id: Mapped[int] = mapped_column(
        ForeignKey("offboarding_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    interviewer_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    meeting_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    meeting_external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ExitInterviewStatus] = mapped_column(
        SAEnum(
            ExitInterviewStatus,
            name="exit_interview_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=ExitInterviewStatus.SCHEDULED,
        index=True,
    )
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    offboarding_case: Mapped[OffboardingCase] = relationship(back_populates="exit_interviews")
    interviewer: Mapped[Employee | None] = relationship(foreign_keys=[interviewer_employee_id])
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_user_id])
