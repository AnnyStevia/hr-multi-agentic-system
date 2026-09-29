from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.modules.identity.dependencies import get_current_user
from app.modules.identity.hr_access import require_hr_staff
from app.modules.identity.models import User
from app.modules.offboarding.dependencies import get_offboarding_service
from app.modules.offboarding.schemas import OffboardingDetailResponse
from app.modules.offboarding.service import OffboardingService, build_detail_response as build_case_detail_response
from app.modules.offboarding_requests.dependencies import get_offboarding_request_service
from app.modules.offboarding_requests.models import OffboardingRequestStatus
from app.modules.offboarding_requests.schemas import (
    OffboardingRequestCreatePayload,
    OffboardingRequestDetailResponse,
    OffboardingRequestEmployeeViewResponse,
    OffboardingRequestLinkCasePayload,
    OffboardingRequestListItemResponse,
    OffboardingRequestRejectPayload,
)
from app.modules.offboarding_requests.service import (
    OffboardingRequestService,
    build_detail_response,
    build_employee_view_response,
)
from app.shared.exceptions import AppException

me_router = APIRouter(prefix="/me/offboarding/requests", tags=["My Offboarding Requests"])
router = APIRouter(prefix="/offboarding/requests", tags=["Offboarding Requests"])


def _handle(exc: AppException) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


# --- Spec paths under /offboarding/requests ---


@router.post("", response_model=OffboardingRequestEmployeeViewResponse, status_code=status.HTTP_201_CREATED)
def create_offboarding_request(
    payload: OffboardingRequestCreatePayload,
    current_user: User = Depends(get_current_user),
    service: OffboardingRequestService = Depends(get_offboarding_request_service),
) -> OffboardingRequestEmployeeViewResponse:
    """Employee self-service: create an offboarding request for themselves."""
    try:
        return build_employee_view_response(
            service.create_for_user(current_user.id, payload)
        )
    except AppException as exc:
        _handle(exc)


@router.get("/me", response_model=list[OffboardingRequestEmployeeViewResponse])
def list_my_offboarding_requests_on_router(
    current_user: User = Depends(get_current_user),
    service: OffboardingRequestService = Depends(get_offboarding_request_service),
) -> list[OffboardingRequestEmployeeViewResponse]:
    """Employee self-service: list own offboarding requests."""
    try:
        return [
            build_employee_view_response(item)
            for item in service.list_for_user(current_user.id)
        ]
    except AppException as exc:
        _handle(exc)


@router.get("", response_model=list[OffboardingRequestListItemResponse])
def list_offboarding_requests(
    status_filter: OffboardingRequestStatus | None = Query(None, alias="status"),
    employee_id: int | None = Query(None),
    _user: User = Depends(require_hr_staff("offboarding:read")),
    service: OffboardingRequestService = Depends(get_offboarding_request_service),
) -> list[OffboardingRequestListItemResponse]:
    return service.list_for_hr(status=status_filter, employee_id=employee_id)


@router.get("/{request_id}", response_model=OffboardingRequestDetailResponse)
def get_offboarding_request(
    request_id: int,
    _user: User = Depends(require_hr_staff("offboarding:read")),
    service: OffboardingRequestService = Depends(get_offboarding_request_service),
) -> OffboardingRequestDetailResponse:
    try:
        return build_detail_response(service.get_for_hr(request_id))
    except AppException as exc:
        _handle(exc)


@router.post("/{request_id}/approve", response_model=OffboardingDetailResponse)
def approve_offboarding_request(
    request_id: int,
    current_user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingRequestService = Depends(get_offboarding_request_service),
    offboarding_service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingDetailResponse:
    try:
        case = service.approve(request_id, current_user)
        return build_case_detail_response(offboarding_service.get_for_hr(case.id))
    except AppException as exc:
        _handle(exc)


@router.post("/{request_id}/reject", response_model=OffboardingRequestDetailResponse)
def reject_offboarding_request(
    request_id: int,
    payload: OffboardingRequestRejectPayload,
    current_user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingRequestService = Depends(get_offboarding_request_service),
) -> OffboardingRequestDetailResponse:
    try:
        return build_detail_response(service.reject(request_id, current_user, payload))
    except AppException as exc:
        _handle(exc)


@router.post(
    "/{request_id}/create-case",
    response_model=OffboardingDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_case_from_offboarding_request(
    request_id: int,
    current_user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingRequestService = Depends(get_offboarding_request_service),
    offboarding_service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingDetailResponse:
    try:
        case = service.create_case_for_hr(request_id, current_user)
        return build_case_detail_response(offboarding_service.get_for_hr(case.id))
    except AppException as exc:
        _handle(exc)


@router.post("/{request_id}/cancel", response_model=OffboardingRequestEmployeeViewResponse)
def cancel_offboarding_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    service: OffboardingRequestService = Depends(get_offboarding_request_service),
) -> OffboardingRequestEmployeeViewResponse:
    """Employee self-service: cancel own pending request."""
    try:
        return build_employee_view_response(
            service.cancel_for_user(current_user.id, request_id)
        )
    except AppException as exc:
        _handle(exc)


@router.patch("/{request_id}/approve", response_model=OffboardingDetailResponse)
def approve_offboarding_request_patch(
    request_id: int,
    current_user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingRequestService = Depends(get_offboarding_request_service),
    offboarding_service: OffboardingService = Depends(get_offboarding_service),
) -> OffboardingDetailResponse:
    return approve_offboarding_request(
        request_id, current_user, service, offboarding_service
    )


@router.patch("/{request_id}/reject", response_model=OffboardingRequestDetailResponse)
def reject_offboarding_request_patch(
    request_id: int,
    payload: OffboardingRequestRejectPayload,
    current_user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingRequestService = Depends(get_offboarding_request_service),
) -> OffboardingRequestDetailResponse:
    return reject_offboarding_request(request_id, payload, current_user, service)


@router.patch("/{request_id}/link-case", response_model=OffboardingRequestDetailResponse)
def link_offboarding_request_case(
    request_id: int,
    payload: OffboardingRequestLinkCasePayload,
    _user: User = Depends(require_hr_staff("offboarding:write")),
    service: OffboardingRequestService = Depends(get_offboarding_request_service),
) -> OffboardingRequestDetailResponse:
    try:
        return build_detail_response(
            service.link_case(request_id, payload.offboarding_case_id)
        )
    except AppException as exc:
        _handle(exc)


# --- Legacy /me aliases (same handlers) ---


@me_router.post("", response_model=OffboardingRequestEmployeeViewResponse, status_code=status.HTTP_201_CREATED)
def create_my_offboarding_request(
    payload: OffboardingRequestCreatePayload,
    current_user: User = Depends(get_current_user),
    service: OffboardingRequestService = Depends(get_offboarding_request_service),
) -> OffboardingRequestEmployeeViewResponse:
    return create_offboarding_request(payload, current_user, service)


@me_router.get("", response_model=list[OffboardingRequestEmployeeViewResponse])
def list_my_offboarding_requests(
    current_user: User = Depends(get_current_user),
    service: OffboardingRequestService = Depends(get_offboarding_request_service),
) -> list[OffboardingRequestEmployeeViewResponse]:
    return list_my_offboarding_requests_on_router(current_user, service)


@me_router.get("/{request_id}", response_model=OffboardingRequestEmployeeViewResponse)
def get_my_offboarding_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    service: OffboardingRequestService = Depends(get_offboarding_request_service),
) -> OffboardingRequestEmployeeViewResponse:
    try:
        return build_employee_view_response(
            service.get_for_user(current_user.id, request_id)
        )
    except AppException as exc:
        _handle(exc)


@me_router.patch("/{request_id}/cancel", response_model=OffboardingRequestEmployeeViewResponse)
def cancel_my_offboarding_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    service: OffboardingRequestService = Depends(get_offboarding_request_service),
) -> OffboardingRequestEmployeeViewResponse:
    return cancel_offboarding_request(request_id, current_user, service)
