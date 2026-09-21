from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.employees.dependencies import get_position_service
from app.modules.employees.schemas import (
    PositionCreateRequest,
    PositionResponse,
    PositionUpdateRequest,
)
from app.modules.employees.service import PositionService, build_position_response
from app.modules.identity.hr_access import require_hr_staff
from app.modules.identity.models import User
from app.shared.exceptions import AppException

router = APIRouter(prefix="/positions", tags=["Positions"])


def _handle(exc: AppException) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("", response_model=list[PositionResponse])
def list_positions(
    department_id: int | None = Query(default=None),
    q: str | None = Query(default=None),
    _user: User = Depends(require_hr_staff("employees:read")),
    position_service: PositionService = Depends(get_position_service),
) -> list[PositionResponse]:
    try:
        return [
            build_position_response(item)
            for item in position_service.list_positions(department_id=department_id, q=q)
        ]
    except AppException as exc:
        _handle(exc)


@router.post("", response_model=PositionResponse, status_code=201)
def create_position(
    payload: PositionCreateRequest,
    _user: User = Depends(require_hr_staff("employees:write")),
    position_service: PositionService = Depends(get_position_service),
) -> PositionResponse:
    try:
        return build_position_response(position_service.create_position(payload))
    except AppException as exc:
        _handle(exc)


@router.get("/{position_id}", response_model=PositionResponse)
def get_position(
    position_id: int,
    _user: User = Depends(require_hr_staff("employees:read")),
    position_service: PositionService = Depends(get_position_service),
) -> PositionResponse:
    try:
        return build_position_response(position_service.get_position(position_id))
    except AppException as exc:
        _handle(exc)


@router.patch("/{position_id}", response_model=PositionResponse)
def update_position(
    position_id: int,
    payload: PositionUpdateRequest,
    _user: User = Depends(require_hr_staff("employees:write")),
    position_service: PositionService = Depends(get_position_service),
) -> PositionResponse:
    try:
        return build_position_response(position_service.update_position(position_id, payload))
    except AppException as exc:
        _handle(exc)


@router.delete("/{position_id}", status_code=204)
def delete_position(
    position_id: int,
    _user: User = Depends(require_hr_staff("employees:write")),
    position_service: PositionService = Depends(get_position_service),
) -> None:
    try:
        position_service.delete_position(position_id)
    except AppException as exc:
        _handle(exc)
