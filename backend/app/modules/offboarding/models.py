from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
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


ACTIVE_OFFBOARDING_STATUSES = frozenset(
    {
        OffboardingStatus.INITIATED,
        OffboardingStatus.IN_PROGRESS,
        OffboardingStatus.PENDING_CLEARANCE,
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
