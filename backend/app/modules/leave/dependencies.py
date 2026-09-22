from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.employees.repository import EmployeeRepository
from app.modules.leave.repository import LeaveRepository
from app.modules.leave.service import LeaveService
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import NotificationService


def get_leave_service(db: Session = Depends(get_db)) -> LeaveService:
    return LeaveService(
        LeaveRepository(db),
        EmployeeRepository(db),
        NotificationService(NotificationRepository(db)),
    )
