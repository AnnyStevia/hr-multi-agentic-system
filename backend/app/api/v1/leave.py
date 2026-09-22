from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.identity.dependencies import get_current_user
from app.modules.identity.hr_access import require_hr_staff
from app.modules.identity.models import User
from app.modules.leave.dependencies import get_leave_service
from app.modules.leave.models import LeaveRequestStatus
from app.modules.leave.schemas import (
    LeaveBalanceResponse,
    LeavePolicyCreateRequest,
    LeavePolicyResponse,
    LeavePolicyUpdateRequest,
    LeaveRequestCreateRequest,
    LeaveRequestRejectRequest,
    LeaveRequestResponse,
    LeaveTypeCreateRequest,
    LeaveTypeResponse,
    LeaveTypeUpdateRequest,
)
from app.modules.leave.service import (
    LeaveService,
    build_leave_policy_response,
    build_leave_request_response,
    build_leave_type_response,
)
from app.shared.exceptions import AppException

types_router = APIRouter(prefix="/leave/types", tags=["Leave Types"])
policies_router = APIRouter(prefix="/leave/policies", tags=["Leave Policies"])
requests_router = APIRouter(prefix="/leave/requests", tags=["Leave Requests"])
me_router = APIRouter(prefix="/me/leave", tags=["My Leave"])
employees_router = APIRouter(prefix="/employees", tags=["Employee Leave"])


def _handle(exc: AppException) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


# --- Types ---


@types_router.get("", response_model=list[LeaveTypeResponse])
def list_leave_types(
    active_only: bool = Query(False),
    _: User = Depends(require_hr_staff("leaves:read")),
    service: LeaveService = Depends(get_leave_service),
) -> list[LeaveTypeResponse]:
    return [
        build_leave_type_response(item)
        for item in service.list_types(active_only=active_only)
    ]


@types_router.post("", response_model=LeaveTypeResponse, status_code=201)
def create_leave_type(
    payload: LeaveTypeCreateRequest,
    _: User = Depends(require_hr_staff("leaves:write")),
    service: LeaveService = Depends(get_leave_service),
) -> LeaveTypeResponse:
    try:
        return build_leave_type_response(service.create_type(payload))
    except AppException as exc:
        _handle(exc)


@types_router.get("/{leave_type_id}", response_model=LeaveTypeResponse)
def get_leave_type(
    leave_type_id: int,
    _: User = Depends(require_hr_staff("leaves:read")),
    service: LeaveService = Depends(get_leave_service),
) -> LeaveTypeResponse:
    try:
        return build_leave_type_response(service.get_type(leave_type_id))
    except AppException as exc:
        _handle(exc)


@types_router.patch("/{leave_type_id}", response_model=LeaveTypeResponse)
def update_leave_type(
    leave_type_id: int,
    payload: LeaveTypeUpdateRequest,
    _: User = Depends(require_hr_staff("leaves:write")),
    service: LeaveService = Depends(get_leave_service),
) -> LeaveTypeResponse:
    try:
        return build_leave_type_response(service.update_type(leave_type_id, payload))
    except AppException as exc:
        _handle(exc)


@types_router.delete("/{leave_type_id}", response_model=LeaveTypeResponse)
def delete_leave_type(
    leave_type_id: int,
    _: User = Depends(require_hr_staff("leaves:write")),
    service: LeaveService = Depends(get_leave_service),
) -> LeaveTypeResponse:
    try:
        return build_leave_type_response(service.delete_type(leave_type_id))
    except AppException as exc:
        _handle(exc)


# --- Policies ---


@policies_router.get("", response_model=list[LeavePolicyResponse])
def list_leave_policies(
    leave_type_id: int | None = Query(None),
    year: int | None = Query(None),
    _: User = Depends(require_hr_staff("leaves:read")),
    service: LeaveService = Depends(get_leave_service),
) -> list[LeavePolicyResponse]:
    return [
        build_leave_policy_response(item)
        for item in service.list_policies(leave_type_id=leave_type_id, year=year)
    ]


@policies_router.post("", response_model=LeavePolicyResponse, status_code=201)
def create_leave_policy(
    payload: LeavePolicyCreateRequest,
    _: User = Depends(require_hr_staff("leaves:write")),
    service: LeaveService = Depends(get_leave_service),
) -> LeavePolicyResponse:
    try:
        return build_leave_policy_response(service.create_policy(payload))
    except AppException as exc:
        _handle(exc)


@policies_router.patch("/{policy_id}", response_model=LeavePolicyResponse)
def update_leave_policy(
    policy_id: int,
    payload: LeavePolicyUpdateRequest,
    _: User = Depends(require_hr_staff("leaves:write")),
    service: LeaveService = Depends(get_leave_service),
) -> LeavePolicyResponse:
    try:
        return build_leave_policy_response(service.update_policy(policy_id, payload))
    except AppException as exc:
        _handle(exc)


@policies_router.delete("/{policy_id}", status_code=204)
def delete_leave_policy(
    policy_id: int,
    _: User = Depends(require_hr_staff("leaves:write")),
    service: LeaveService = Depends(get_leave_service),
) -> None:
    try:
        service.delete_policy(policy_id)
    except AppException as exc:
        _handle(exc)


# --- HR / manager requests ---


@requests_router.get("", response_model=list[LeaveRequestResponse])
def list_leave_requests(
    employee_id: int | None = Query(None),
    leave_type_id: int | None = Query(None),
    status_filter: LeaveRequestStatus | None = Query(None, alias="status"),
    _: User = Depends(require_hr_staff("leaves:read")),
    service: LeaveService = Depends(get_leave_service),
) -> list[LeaveRequestResponse]:
    return [
        build_leave_request_response(item)
        for item in service.list_requests_for_hr(
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            status=status_filter,
        )
    ]


@requests_router.get("/{request_id}", response_model=LeaveRequestResponse)
def get_leave_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    service: LeaveService = Depends(get_leave_service),
) -> LeaveRequestResponse:
    try:
        request = service.get_request_for_hr(request_id)
        if not (
            service._is_hr_staff_user(current_user.id)
            or service.can_user_review_request(request, current_user.id)
        ):
            raise AppException("Leave request not found", status_code=404)
        return build_leave_request_response(request)
    except AppException as exc:
        _handle(exc)


@requests_router.patch("/{request_id}/approve", response_model=LeaveRequestResponse)
def approve_leave_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    service: LeaveService = Depends(get_leave_service),
) -> LeaveRequestResponse:
    try:
        return build_leave_request_response(
            service.approve_request(request_id, current_user.id)
        )
    except AppException as exc:
        _handle(exc)


@requests_router.patch("/{request_id}/reject", response_model=LeaveRequestResponse)
def reject_leave_request(
    request_id: int,
    payload: LeaveRequestRejectRequest,
    current_user: User = Depends(get_current_user),
    service: LeaveService = Depends(get_leave_service),
) -> LeaveRequestResponse:
    try:
        return build_leave_request_response(
            service.reject_request(request_id, current_user.id, payload.rejection_reason)
        )
    except AppException as exc:
        _handle(exc)


# --- Me ---


@me_router.get("/balances", response_model=list[LeaveBalanceResponse])
def list_my_leave_balances(
    year: int | None = Query(None),
    current_user: User = Depends(get_current_user),
    service: LeaveService = Depends(get_leave_service),
) -> list[LeaveBalanceResponse]:
    try:
        return service.get_balances_for_user(current_user.id, year=year)
    except AppException as exc:
        _handle(exc)


@me_router.get("/requests", response_model=list[LeaveRequestResponse])
def list_my_leave_requests(
    current_user: User = Depends(get_current_user),
    service: LeaveService = Depends(get_leave_service),
) -> list[LeaveRequestResponse]:
    try:
        return [
            build_leave_request_response(item)
            for item in service.list_requests_for_user(current_user.id)
        ]
    except AppException as exc:
        _handle(exc)


@me_router.post("/requests", response_model=LeaveRequestResponse, status_code=201)
def create_my_leave_request(
    payload: LeaveRequestCreateRequest,
    current_user: User = Depends(get_current_user),
    service: LeaveService = Depends(get_leave_service),
) -> LeaveRequestResponse:
    try:
        return build_leave_request_response(
            service.create_request_for_user(current_user.id, payload)
        )
    except AppException as exc:
        _handle(exc)


@me_router.get("/requests/{request_id}", response_model=LeaveRequestResponse)
def get_my_leave_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    service: LeaveService = Depends(get_leave_service),
) -> LeaveRequestResponse:
    try:
        return build_leave_request_response(
            service.get_request_for_user(current_user.id, request_id)
        )
    except AppException as exc:
        _handle(exc)


@me_router.patch("/requests/{request_id}/cancel", response_model=LeaveRequestResponse)
def cancel_my_leave_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    service: LeaveService = Depends(get_leave_service),
) -> LeaveRequestResponse:
    try:
        return build_leave_request_response(
            service.cancel_request_for_user(current_user.id, request_id)
        )
    except AppException as exc:
        _handle(exc)


@me_router.get("/types", response_model=list[LeaveTypeResponse])
def list_my_active_leave_types(
    current_user: User = Depends(get_current_user),
    service: LeaveService = Depends(get_leave_service),
) -> list[LeaveTypeResponse]:
    _ = current_user
    return [
        build_leave_type_response(item)
        for item in service.list_types(active_only=True)
    ]


# --- Employee balances (HR) ---


@employees_router.get(
    "/{employee_id}/leave/balances",
    response_model=list[LeaveBalanceResponse],
)
def list_employee_leave_balances(
    employee_id: int,
    year: int | None = Query(None),
    _: User = Depends(require_hr_staff("leaves:read")),
    service: LeaveService = Depends(get_leave_service),
) -> list[LeaveBalanceResponse]:
    try:
        return service.get_balances(employee_id, year=year)
    except AppException as exc:
        _handle(exc)
