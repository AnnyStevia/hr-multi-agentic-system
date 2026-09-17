from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class OnboardingTrainingStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"


class Training(Base):
    __tablename__ = "trainings"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    assignments: Mapped[list["OnboardingTraining"]] = relationship(
        back_populates="training",
        cascade="all, delete-orphan",
    )


class OnboardingTraining(Base):
    __tablename__ = "onboarding_trainings"
    __table_args__ = (
        UniqueConstraint("onboarding_id", "training_id", name="uq_onboarding_training"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    onboarding_id: Mapped[int] = mapped_column(
        ForeignKey("onboardings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    training_id: Mapped[int] = mapped_column(
        ForeignKey("trainings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[OnboardingTrainingStatus] = mapped_column(
        SAEnum(
            OnboardingTrainingStatus,
            name="onboarding_training_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=OnboardingTrainingStatus.PENDING,
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    training: Mapped[Training] = relationship(back_populates="assignments")
    onboarding: Mapped["Onboarding"] = relationship()  # noqa: F821
