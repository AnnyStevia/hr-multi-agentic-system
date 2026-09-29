from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.modules.identity.dependencies import get_current_user
from app.modules.identity.hr_access import require_hr_staff
from app.modules.identity.models import User
from app.modules.offboarding.dependencies import get_offboarding_service
from app.modules.offboarding.models import OffboardingStatus
from app.modules.offboarding.schemas import (
    OffboardingCreateRequest,
    OffboardingDetailResponse,
    OffboardingEmployeeViewResponse,
    OffboardingListItemResponse,
)
from app.modules.offboarding.service import (
    OffboardingService,
    build_detail_response,
    build_employee_view_response,
)
from app.shared.exceptions import AppException

me_router = APIRouter(prefix="/me", tags=["Offboarding"])
router = APIRouter(prefix="/offboarding", tags=["Offboarding"])


def _handle(exc: AppException) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@me_router.get("/offboarding", response_model=list[OffboardingEmployeeViewResponse])
def list_my_offboarding(
    current_user: User = Depends(get_current_user),
    service: OffboardingService = Depends(get_offboarding_service),
) -> list[OffboardingEmployeeViewResponse]:
    try:
        return [
            build_employee_view_response(case)
            for case in service.list_for_user(current_user.id)
        ]
    except AppException as exc:
        _handle(exc)


@router.post("", response_model=OffboardingDetailResponse, status_code=status.HTTP_201_CREATED)
def create_offboarding(
    payload: OffboardingCreateRequest,
    current_user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingDetailResponse:
    try:
        case = service.create_for_hr(current_user, payload)
        # Reload with relationships for response builders
        return build_detail_response(service.get_for_hr(case.id))
    except AppException as exc:
        _handle(exc)


@router.get("", response_model=list[OffboardingListItemResponse])
def list_offboarding(
    status_filter: OffboardingStatus | None = Query(None, alias="status"),
    employee_id: int | None = Query(None),
    _user: User = Depends(require_hr_staff("offboarding:read")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> list[OffboardingListItemResponse]:
    return service.list_for_hr(status=status_filter, employee_id=employee_id)


@router.get("/{case_id}", response_model=OffboardingDetailResponse)
def get_offboarding(
    case_id: int,
    _user: User = Depends(require_hr_staff("offboarding:read")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingDetailResponse:
    try:
        return build_detail_response(service.get_for_hr(case_id))
    except AppException as exc:
        _handle(exc)


@router.post("/{case_id}/start", response_model=OffboardingDetailResponse)
def start_offboarding(
    case_id: int,
    _user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingDetailResponse:
    try:
        return build_detail_response(service.start(case_id))
    except AppException as exc:
        _handle(exc)


@router.post("/{case_id}/pending-clearance", response_model=OffboardingDetailResponse)
def pending_clearance_offboarding(
    case_id: int,
    _user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingDetailResponse:
    try:
        return build_detail_response(service.move_to_pending_clearance(case_id))
    except AppException as exc:
        _handle(exc)


@router.post("/{case_id}/complete", response_model=OffboardingDetailResponse)
def complete_offboarding(
    case_id: int,
    _user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingDetailResponse:
    try:
        return build_detail_response(service.complete(case_id))
    except AppException as exc:
        _handle(exc)


@router.post("/{case_id}/cancel", response_model=OffboardingDetailResponse)
def cancel_offboarding(
    case_id: int,
    _user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingDetailResponse:
    try:
        return build_detail_response(service.cancel(case_id))
    except AppException as exc:
        _handle(exc)
