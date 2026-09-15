from fastapi import APIRouter, Depends, HTTPException

from app.modules.identity.dependencies import require_roles
from app.modules.identity.models import User
from app.modules.recruitment.application_service import (
    ApplicationService,
    build_application_detail,
)
from app.modules.recruitment.dependencies import get_application_service
from app.modules.recruitment.schemas import ApplicationDetail
from app.shared.exceptions import AppException

router = APIRouter(prefix="/careers/applications", tags=["Careers"])


@router.get("/{application_id}", response_model=ApplicationDetail)
def get_own_application(
    application_id: int,
    current_user: User = Depends(require_roles("candidate")),
    application_service: ApplicationService = Depends(get_application_service),
) -> ApplicationDetail:
    try:
        application = application_service.get_own(current_user, application_id)
        return build_application_detail(application)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
