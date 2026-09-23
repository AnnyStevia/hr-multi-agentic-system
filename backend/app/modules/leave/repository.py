from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.modules.leave.models import LeavePolicy, LeaveRequest, LeaveRequestStatus, LeaveType


class LeaveRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- Leave types ---

    def list_types(self, *, active_only: bool = False) -> list[LeaveType]:
        query = self.db.query(LeaveType)
        if active_only:
            query = query.filter(LeaveType.is_active.is_(True))
        return query.order_by(LeaveType.name.asc(), LeaveType.id.asc()).all()

    def get_type(self, leave_type_id: int) -> LeaveType | None:
        return self.db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()

    def get_type_by_name(self, name: str) -> LeaveType | None:
        return self.db.query(LeaveType).filter(LeaveType.name == name).first()

    def add_type(self, leave_type: LeaveType) -> LeaveType:
        self.db.add(leave_type)
        self.db.commit()
        self.db.refresh(leave_type)
        return leave_type

    def save_type(self, leave_type: LeaveType) -> LeaveType:
        self.db.commit()
        self.db.refresh(leave_type)
        return leave_type

    def delete_type(self, leave_type: LeaveType) -> None:
        self.db.delete(leave_type)
        self.db.commit()

    def type_has_dependencies(self, leave_type_id: int) -> bool:
        if (
            self.db.query(LeavePolicy.id)
            .filter(LeavePolicy.leave_type_id == leave_type_id)
            .first()
            is not None
        ):
            return True
        return (
            self.db.query(LeaveRequest.id)
            .filter(LeaveRequest.leave_type_id == leave_type_id)
            .first()
            is not None
        )

    # --- Policies ---

    def list_policies(
        self,
        *,
        leave_type_id: int | None = None,
        year: int | None = None,
    ) -> list[LeavePolicy]:
        query = self.db.query(LeavePolicy).options(joinedload(LeavePolicy.leave_type))
        if leave_type_id is not None:
            query = query.filter(LeavePolicy.leave_type_id == leave_type_id)
        if year is not None:
            query = query.filter(LeavePolicy.year == year)
        return query.order_by(LeavePolicy.year.desc(), LeavePolicy.id.asc()).all()

    def get_policy(self, policy_id: int) -> LeavePolicy | None:
        return (
            self.db.query(LeavePolicy)
            .options(joinedload(LeavePolicy.leave_type))
            .filter(LeavePolicy.id == policy_id)
            .first()
        )

    def get_policy_for_type_year(self, leave_type_id: int, year: int) -> LeavePolicy | None:
        return (
            self.db.query(LeavePolicy)
            .options(joinedload(LeavePolicy.leave_type))
            .filter(
                LeavePolicy.leave_type_id == leave_type_id,
                LeavePolicy.year == year,
            )
            .first()
        )

    def add_policy(self, policy: LeavePolicy) -> LeavePolicy:
        self.db.add(policy)
        self.db.commit()
        self.db.refresh(policy)
        return self.get_policy(policy.id) or policy

    def save_policy(self, policy: LeavePolicy) -> LeavePolicy:
        self.db.commit()
        self.db.refresh(policy)
        return self.get_policy(policy.id) or policy

    def delete_policy(self, policy: LeavePolicy) -> None:
        self.db.delete(policy)
        self.db.commit()

    # --- Requests ---

    def list_requests(
        self,
        *,
        employee_id: int | None = None,
        leave_type_id: int | None = None,
        status: LeaveRequestStatus | None = None,
    ) -> list[LeaveRequest]:
        query = (
            self.db.query(LeaveRequest)
            .options(
                joinedload(LeaveRequest.leave_type),
                joinedload(LeaveRequest.employee),
            )
        )
        if employee_id is not None:
            query = query.filter(LeaveRequest.employee_id == employee_id)
        if leave_type_id is not None:
            query = query.filter(LeaveRequest.leave_type_id == leave_type_id)
        if status is not None:
            query = query.filter(LeaveRequest.status == status)
        return query.order_by(LeaveRequest.created_at.desc(), LeaveRequest.id.desc()).all()

    def get_request(self, request_id: int) -> LeaveRequest | None:
        return (
            self.db.query(LeaveRequest)
            .options(
                joinedload(LeaveRequest.leave_type),
                joinedload(LeaveRequest.employee),
            )
            .filter(LeaveRequest.id == request_id)
            .first()
        )

    def add_request(self, request: LeaveRequest) -> LeaveRequest:
        self.db.add(request)
        self.db.commit()
        self.db.refresh(request)
        return self.get_request(request.id) or request

    def save_request(self, request: LeaveRequest) -> LeaveRequest:
        self.db.commit()
        self.db.refresh(request)
        return self.get_request(request.id) or request

    def find_overlapping(
        self,
        employee_id: int,
        start_date: date,
        end_date: date,
        *,
        exclude_request_id: int | None = None,
    ) -> LeaveRequest | None:
        active = [LeaveRequestStatus.PENDING, LeaveRequestStatus.APPROVED]
        query = self.db.query(LeaveRequest).filter(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status.in_(active),
            LeaveRequest.start_date <= end_date,
            LeaveRequest.end_date >= start_date,
        )
        if exclude_request_id is not None:
            query = query.filter(LeaveRequest.id != exclude_request_id)
        return query.first()

    def sum_requested_days(
        self,
        employee_id: int,
        leave_type_id: int,
        year: int,
        status: LeaveRequestStatus,
    ) -> int:
        total = (
            self.db.query(func.coalesce(func.sum(LeaveRequest.requested_days), 0))
            .filter(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.leave_type_id == leave_type_id,
                LeaveRequest.status == status,
                func.extract("year", LeaveRequest.start_date) == year,
            )
            .scalar()
        )
        return int(total or 0)

    def list_calendar_periods(
        self,
        employee_id: int,
        *,
        month_start: date,
        month_end: date,
    ) -> list[LeaveRequest]:
        active = [LeaveRequestStatus.PENDING, LeaveRequestStatus.APPROVED]
        return (
            self.db.query(LeaveRequest)
            .options(joinedload(LeaveRequest.leave_type))
            .filter(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.status.in_(active),
                LeaveRequest.start_date <= month_end,
                LeaveRequest.end_date >= month_start,
            )
            .order_by(LeaveRequest.start_date.asc(), LeaveRequest.id.asc())
            .all()
        )

    def find_approved_covering(
        self, employee_id: int, as_of: date
    ) -> LeaveRequest | None:
        return (
            self.db.query(LeaveRequest)
            .options(joinedload(LeaveRequest.leave_type))
            .filter(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.status == LeaveRequestStatus.APPROVED,
                LeaveRequest.start_date <= as_of,
                LeaveRequest.end_date >= as_of,
            )
            .order_by(LeaveRequest.start_date.asc(), LeaveRequest.id.asc())
            .first()
        )

    def count_requests(self, *, status: LeaveRequestStatus) -> int:
        return self.db.query(LeaveRequest).filter(LeaveRequest.status == status).count()

    def list_approved_covering(self, as_of: date) -> list[LeaveRequest]:
        return (
            self.db.query(LeaveRequest)
            .options(
                joinedload(LeaveRequest.leave_type),
                joinedload(LeaveRequest.employee),
            )
            .filter(
                LeaveRequest.status == LeaveRequestStatus.APPROVED,
                LeaveRequest.start_date <= as_of,
                LeaveRequest.end_date >= as_of,
            )
            .order_by(LeaveRequest.end_date.asc(), LeaveRequest.id.asc())
            .all()
        )

    def count_employees_on_leave(self, as_of: date) -> int:
        return (
            self.db.query(func.count(func.distinct(LeaveRequest.employee_id)))
            .filter(
                LeaveRequest.status == LeaveRequestStatus.APPROVED,
                LeaveRequest.start_date <= as_of,
                LeaveRequest.end_date >= as_of,
            )
            .scalar()
            or 0
        )

    def list_returning_soon(
        self, *, from_date: date, to_date: date, limit: int = 8
    ) -> list[LeaveRequest]:
        return (
            self.db.query(LeaveRequest)
            .options(
                joinedload(LeaveRequest.leave_type),
                joinedload(LeaveRequest.employee),
            )
            .filter(
                LeaveRequest.status == LeaveRequestStatus.APPROVED,
                LeaveRequest.end_date >= from_date,
                LeaveRequest.end_date <= to_date,
            )
            .order_by(LeaveRequest.end_date.asc(), LeaveRequest.id.asc())
            .limit(limit)
            .all()
        )

    def list_pending_for_dashboard(self, *, limit: int = 8) -> list[LeaveRequest]:
        return (
            self.db.query(LeaveRequest)
            .options(
                joinedload(LeaveRequest.leave_type),
                joinedload(LeaveRequest.employee),
            )
            .filter(LeaveRequest.status == LeaveRequestStatus.PENDING)
            .order_by(LeaveRequest.created_at.asc(), LeaveRequest.id.asc())
            .limit(limit)
            .all()
        )

    def list_requests_for_employees(
        self,
        employee_ids: list[int],
        *,
        status: LeaveRequestStatus | None = None,
    ) -> list[LeaveRequest]:
        if not employee_ids:
            return []
        query = (
            self.db.query(LeaveRequest)
            .options(
                joinedload(LeaveRequest.leave_type),
                joinedload(LeaveRequest.employee),
            )
            .filter(LeaveRequest.employee_id.in_(employee_ids))
        )
        if status is not None:
            query = query.filter(LeaveRequest.status == status)
        return query.order_by(LeaveRequest.created_at.desc(), LeaveRequest.id.desc()).all()
