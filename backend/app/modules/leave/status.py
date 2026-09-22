"""Derived current work status from approved leave (read-time only)."""

from datetime import date

from sqlalchemy.orm import Session

from app.modules.leave.repository import LeaveRepository
from app.modules.leave.schemas import (
    CurrentLeaveSummary,
    CurrentWorkStatus,
    CurrentWorkStatusPayload,
)


def derive_current_work_status(
    db: Session, employee_id: int, *, as_of: date | None = None
) -> CurrentWorkStatusPayload:
    day = as_of or date.today()
    covering = LeaveRepository(db).find_approved_covering(employee_id, day)
    if covering is None:
        return CurrentWorkStatusPayload(
            current_work_status=CurrentWorkStatus.ACTIVE,
            current_leave=None,
        )
    return CurrentWorkStatusPayload(
        current_work_status=CurrentWorkStatus.ON_LEAVE,
        current_leave=CurrentLeaveSummary(
            leave_type=covering.leave_type.name if covering.leave_type else "",
            start_date=covering.start_date,
            end_date=covering.end_date,
        ),
    )
