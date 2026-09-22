from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from app.modules.identity.dependencies import get_user_service, require_roles
from app.modules.identity.models import User
from app.modules.identity.schemas import CreateHRRequest, UserListItem, UserResponse
from app.modules.identity.service import AuthService, UserService
from app.shared.exceptions import AppException

router = APIRouter(prefix="/users", tags=["Users"])

EXCEL_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("", response_model=list[UserListItem])
def list_accounts(
    _admin: User = Depends(require_roles("admin")),
    user_service: UserService = Depends(get_user_service),
) -> list[UserListItem]:
    return [UserService.build_list_item(user) for user in user_service.list_accounts()]


@router.get("/export")
def export_accounts(
    _admin: User = Depends(require_roles("admin")),
    user_service: UserService = Depends(get_user_service),
) -> Response:
    content = user_service.export_accounts_excel()
    return Response(
        content=content,
        media_type=EXCEL_MEDIA_TYPE,
        headers={"Content-Disposition": 'attachment; filename="hr-platform-accounts.xlsx"'},
    )


@router.post("/hr", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_hr_account(
    payload: CreateHRRequest,
    _admin: User = Depends(require_roles("admin")),
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    try:
        user = user_service.create_hr_account(
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            password=payload.password,
            phone=payload.phone,
            department_id=payload.department_id,
            position=payload.position,
            hire_date=payload.hire_date,
            manager_id=payload.manager_id,
        )
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return AuthService.build_user_response(user)
