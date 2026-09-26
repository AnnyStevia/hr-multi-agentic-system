from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class InterviewStatus(str, Enum):
    PROPOSED = "proposed"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class InterviewOutcome(str, Enum):
    REJECTED = "rejected"
    ANOTHER_INTERVIEW = "another_interview"
    HIRED = "hired"


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    interviewer_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    meeting_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[InterviewStatus] = mapped_column(
        SAEnum(
            InterviewStatus,
            name="interview_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=InterviewStatus.PROPOSED,
    )
    selected_slot_id: Mapped[int | None] = mapped_column(
        ForeignKey("interview_slots.id", ondelete="SET NULL", use_alter=True, name="fk_interviews_selected_slot_id"),
        nullable=True,
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[InterviewOutcome | None] = mapped_column(
        SAEnum(
            InterviewOutcome,
            name="interview_outcome",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    application: Mapped["Application"] = relationship()  # noqa: F821
    interviewer: Mapped["Employee | None"] = relationship(foreign_keys=[interviewer_employee_id])  # noqa: F821
    panel_assignments: Mapped[list["InterviewInterviewer"]] = relationship(
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="InterviewInterviewer.id",
    )
    slots: Mapped[list["InterviewSlot"]] = relationship(
        back_populates="interview",
        cascade="all, delete-orphan",
        foreign_keys="InterviewSlot.interview_id",
    )
    selected_slot: Mapped["InterviewSlot | None"] = relationship(
        foreign_keys=[selected_slot_id],
        post_update=True,
    )


class InterviewInterviewer(Base):
    __tablename__ = "interview_interviewers"
    __table_args__ = (
        UniqueConstraint("interview_id", "employee_id", name="uq_interview_interviewers_interview_employee"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_id: Mapped[int] = mapped_column(
        ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    interview: Mapped["Interview"] = relationship(back_populates="panel_assignments")
    employee: Mapped["Employee"] = relationship()  # noqa: F821


class InterviewSlot(Base):
    __tablename__ = "interview_slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_id: Mapped[int] = mapped_column(
        ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_selected: Mapped[bool] = mapped_column(nullable=False, default=False)
    is_available: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    interview: Mapped["Interview"] = relationship(
        back_populates="slots",
        foreign_keys=[interview_id],
    )
