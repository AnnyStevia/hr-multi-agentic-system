from sqlalchemy.orm import Session, joinedload

from app.modules.employees.models import Employee
from app.modules.offboarding.models import (
    ACTIVE_OFFBOARDING_STATUSES,
    OffboardingCase,
    OffboardingStatus,
)


class OffboardingRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, case_id: int) -> OffboardingCase | None:
        return (
            self.db.query(OffboardingCase)
            .options(
                joinedload(OffboardingCase.employee),
                joinedload(OffboardingCase.created_by),
            )
            .filter(OffboardingCase.id == case_id)
            .first()
        )

    def get_active_for_employee(self, employee_id: int) -> OffboardingCase | None:
        return (
            self.db.query(OffboardingCase)
            .filter(
                OffboardingCase.employee_id == employee_id,
                OffboardingCase.status.in_(tuple(ACTIVE_OFFBOARDING_STATUSES)),
            )
            .first()
        )

    def list_for_hr(
        self,
        *,
        status: OffboardingStatus | None = None,
        employee_id: int | None = None,
    ) -> list[OffboardingCase]:
        query = (
            self.db.query(OffboardingCase)
            .options(joinedload(OffboardingCase.employee))
            .join(Employee, OffboardingCase.employee_id == Employee.id)
        )
        if status is not None:
            query = query.filter(OffboardingCase.status == status)
        if employee_id is not None:
            query = query.filter(OffboardingCase.employee_id == employee_id)
        return (
            query.order_by(OffboardingCase.initiated_at.desc(), OffboardingCase.id.desc()).all()
        )

    def list_for_employee(self, employee_id: int) -> list[OffboardingCase]:
        return (
            self.db.query(OffboardingCase)
            .filter(OffboardingCase.employee_id == employee_id)
            .order_by(OffboardingCase.initiated_at.desc(), OffboardingCase.id.desc())
            .all()
        )

    def add(self, case: OffboardingCase) -> OffboardingCase:
        self.db.add(case)
        self.db.commit()
        self.db.refresh(case)
        return case

    def save(self, case: OffboardingCase) -> OffboardingCase:
        self.db.commit()
        self.db.refresh(case)
        return case
