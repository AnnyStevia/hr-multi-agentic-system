from sqlalchemy.orm import Session, joinedload

from app.modules.employees.models import Employee
from app.modules.offboarding_requests.models import (
    OffboardingRequest,
    OffboardingRequestStatus,
)


class OffboardingRequestRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, request_id: int) -> OffboardingRequest | None:
        return (
            self.db.query(OffboardingRequest)
            .options(
                joinedload(OffboardingRequest.employee),
                joinedload(OffboardingRequest.reviewed_by),
            )
            .filter(OffboardingRequest.id == request_id)
            .first()
        )

    def get_pending_for_employee(self, employee_id: int) -> OffboardingRequest | None:
        return (
            self.db.query(OffboardingRequest)
            .filter(
                OffboardingRequest.employee_id == employee_id,
                OffboardingRequest.status == OffboardingRequestStatus.PENDING,
            )
            .first()
        )

    def list_for_employee(self, employee_id: int) -> list[OffboardingRequest]:
        return (
            self.db.query(OffboardingRequest)
            .filter(OffboardingRequest.employee_id == employee_id)
            .order_by(OffboardingRequest.submitted_at.desc(), OffboardingRequest.id.desc())
            .all()
        )

    def list_for_hr(
        self,
        *,
        status: OffboardingRequestStatus | None = None,
        employee_id: int | None = None,
    ) -> list[OffboardingRequest]:
        query = (
            self.db.query(OffboardingRequest)
            .options(joinedload(OffboardingRequest.employee))
            .join(Employee, OffboardingRequest.employee_id == Employee.id)
        )
        if status is not None:
            query = query.filter(OffboardingRequest.status == status)
        if employee_id is not None:
            query = query.filter(OffboardingRequest.employee_id == employee_id)
        return (
            query.order_by(
                OffboardingRequest.submitted_at.desc(),
                OffboardingRequest.id.desc(),
            ).all()
        )

    def add(self, request: OffboardingRequest) -> OffboardingRequest:
        self.db.add(request)
        self.db.commit()
        self.db.refresh(request)
        return request

    def save(self, request: OffboardingRequest) -> OffboardingRequest:
        self.db.commit()
        self.db.refresh(request)
        return request
