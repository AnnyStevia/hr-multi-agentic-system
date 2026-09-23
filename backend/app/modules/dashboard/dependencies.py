from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.dashboard.service import DashboardService
from app.modules.employees.repository import EmployeeRepository
from app.modules.interviews.repository import InterviewRepository
from app.modules.leave.repository import LeaveRepository
from app.modules.onboarding.repository import OnboardingRepository
from app.modules.recruitment.repository import ApplicationRepository, JobRepository


def get_dashboard_service(db: Session = Depends(get_db)) -> DashboardService:
    return DashboardService(
        employees=EmployeeRepository(db),
        leave=LeaveRepository(db),
        onboarding=OnboardingRepository(db),
        jobs=JobRepository(db),
        applications=ApplicationRepository(db),
        interviews=InterviewRepository(db),
    )
