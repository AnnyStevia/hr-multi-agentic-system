from fastapi import APIRouter, Depends

from app.modules.dashboard.dependencies import get_dashboard_service
from app.modules.dashboard.schemas import HrDashboardResponse
from app.modules.dashboard.service import DashboardService
from app.modules.identity.hr_access import require_hr_staff
from app.modules.identity.models import User

router = APIRouter(prefix="/hr/dashboard", tags=["HR Dashboard"])


@router.get("", response_model=HrDashboardResponse)
def get_hr_dashboard(
    _user: User = Depends(require_hr_staff()),
    service: DashboardService = Depends(get_dashboard_service),
) -> HrDashboardResponse:
    return service.get_hr_dashboard()
