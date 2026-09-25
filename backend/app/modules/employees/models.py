from datetime import date, datetime
from enum import Enum

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.recruitment.models import EmploymentType


class DepartmentStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class EmploymentStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on_leave"


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    status: Mapped[DepartmentStatus] = mapped_column(
        SAEnum(
            DepartmentStatus,
            name="department_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=DepartmentStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    employees: Mapped[list["Employee"]] = relationship(back_populates="department")
    positions: Mapped[list["Position"]] = relationship(back_populates="department")


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("title", name="uq_positions_title"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    department: Mapped["Department | None"] = relationship(back_populates="positions")
    employees: Mapped[list["Employee"]] = relationship(back_populates="org_position")


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (UniqueConstraint("user_id", name="uq_employee_user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False
    )
    position: Mapped[str] = mapped_column(String(120), nullable=False)
    position_id: Mapped[int | None] = mapped_column(
        ForeignKey("positions.id", ondelete="RESTRICT"), nullable=True
    )
    manager_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    employment_type: Mapped[EmploymentType] = mapped_column(
        SAEnum(
            EmploymentType,
            name="employment_type",
            values_callable=lambda enum: [item.value for item in enum],
            create_constraint=False,
        ),
        nullable=False,
        default=EmploymentType.FULL_TIME,
        index=True,
    )
    employment_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    employment_status: Mapped[EmploymentStatus] = mapped_column(
        SAEnum(
            EmploymentStatus,
            name="employment_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=EmploymentStatus.ACTIVE,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    profile_picture_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    profile_picture_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    profile_picture_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_picture_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    department: Mapped["Department"] = relationship(back_populates="employees")
    org_position: Mapped["Position | None"] = relationship(
        back_populates="employees", foreign_keys=[position_id]
    )
    manager: Mapped["Employee | None"] = relationship(
        remote_side="Employee.id",
        foreign_keys=[manager_id],
        back_populates="direct_reports",
    )
    direct_reports: Mapped[list["Employee"]] = relationship(
        back_populates="manager",
        foreign_keys=[manager_id],
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
