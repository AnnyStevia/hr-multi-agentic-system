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
from app.modules.offboarding.models import OffboardingReason

if TYPE_CHECKING:
    from app.modules.employees.models import Employee
    from app.modules.identity.models import User
    from app.modules.offboarding.models import OffboardingCase


class OffboardingRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class OffboardingRequest(Base):
    __tablename__ = "offboarding_requests"
    __table_args__ = (
        Index(
            "uq_offboarding_requests_one_pending_per_employee",
            "employee_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
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
            create_constraint=False,
        ),
        nullable=False,
    )
    reason_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_last_working_day: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[OffboardingRequestStatus] = mapped_column(
        SAEnum(
            OffboardingRequestStatus,
            name="offboarding_request_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=OffboardingRequestStatus.PENDING,
        index=True,
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    offboarding_case_id: Mapped[int | None] = mapped_column(
        ForeignKey("offboarding_cases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    employee: Mapped[Employee] = relationship()
    reviewed_by: Mapped[User | None] = relationship(foreign_keys=[reviewed_by_user_id])
    offboarding_case: Mapped[OffboardingCase | None] = relationship()
