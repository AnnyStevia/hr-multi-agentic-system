from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class NotificationType(str, Enum):
    APPLICATION_STATUS_CHANGED = "application_status_changed"
    APPLICATION_SUBMITTED = "application_submitted"
    INTERVIEW_INVITATION = "interview_invitation"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEW_REMINDER = "interview_reminder"
    ONBOARDING_TASK_ASSIGNED = "onboarding_task_assigned"
    ONBOARDING_STARTED = "onboarding_started"
    ONBOARDING_TASK_COMPLETED = "onboarding_task_completed"
    ONBOARDING_TRAINING_ASSIGNED = "onboarding_training_assigned"
    ONBOARDING_TRAINING_COMPLETED = "onboarding_training_completed"
    ONBOARDING_COMPLETED = "onboarding_completed"
    LEAVE_REQUEST_SUBMITTED = "leave_request_submitted"
    LEAVE_REQUEST_MANAGER_APPROVED = "leave_request_manager_approved"
    LEAVE_REQUEST_APPROVED = "leave_request_approved"
    LEAVE_REQUEST_REJECTED = "leave_request_rejected"
    LEAVE_REQUEST_CANCELLED = "leave_request_cancelled"
    LEAVE_CANCELLATION_REQUESTED = "leave_cancellation_requested"
    LEAVE_CANCELLATION_APPROVED = "leave_cancellation_approved"
    LEAVE_CANCELLATION_REJECTED = "leave_cancellation_rejected"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipient_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[NotificationType] = mapped_column(
        SAEnum(
            NotificationType,
            name="notification_type",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    related_entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    recipient: Mapped["User"] = relationship()  # noqa: F821
