from fastapi import APIRouter, Depends, HTTPException

from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User
from app.modules.notifications.dependencies import get_notification_service
from app.modules.notifications.schemas import MarkAllReadResponse, NotificationResponse, UnreadCountResponse
from app.modules.notifications.service import NotificationService, build_notification_response
from app.shared.exceptions import AppException

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _handle(exc: AppException) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("", response_model=list[NotificationResponse])
def list_notifications(
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
) -> list[NotificationResponse]:
    return [
        build_notification_response(item)
        for item in notification_service.list_for_user(current_user.id)
    ]


@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
) -> UnreadCountResponse:
    return UnreadCountResponse(count=notification_service.get_unread_count(current_user.id))


@router.patch("/read-all", response_model=MarkAllReadResponse)
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
) -> MarkAllReadResponse:
    return MarkAllReadResponse(updated=notification_service.mark_all_as_read(current_user.id))


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
) -> NotificationResponse:
    try:
        return build_notification_response(
            notification_service.mark_as_read(notification_id, current_user.id)
        )
    except AppException as exc:
        _handle(exc)
