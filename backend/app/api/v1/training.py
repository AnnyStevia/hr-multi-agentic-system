from fastapi import APIRouter, Depends, HTTPException

from app.modules.identity.dependencies import get_current_user
from app.modules.identity.hr_access import require_hr_staff
from app.modules.identity.models import User
from app.modules.training.dependencies import get_training_service
from app.modules.training.schemas import (
    OnboardingTrainingAssignRequest,
    OnboardingTrainingResponse,
    TrainingCreateRequest,
    TrainingResponse,
    TrainingUpdateRequest,
)
from app.modules.training.service import (
    TrainingService,
    build_assignment_response,
    build_training_response,
)
from app.shared.exceptions import AppException

catalog_router = APIRouter(prefix="/trainings", tags=["Trainings"])
onboarding_router = APIRouter(prefix="/onboarding", tags=["Onboarding Trainings"])
me_router = APIRouter(prefix="/me/onboarding/trainings", tags=["My Onboarding Trainings"])


def _handle(exc: AppException) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@catalog_router.get("", response_model=list[TrainingResponse])
def list_trainings(
    _: User = Depends(require_hr_staff("training:read")),
    service: TrainingService = Depends(get_training_service),
) -> list[TrainingResponse]:
    return [build_training_response(item) for item in service.list_trainings()]


@catalog_router.post("", response_model=TrainingResponse, status_code=201)
def create_training(
    payload: TrainingCreateRequest,
    _: User = Depends(require_hr_staff("training:write")),
    service: TrainingService = Depends(get_training_service),
) -> TrainingResponse:
    try:
        return build_training_response(service.create_training(payload))
    except AppException as exc:
        _handle(exc)


@catalog_router.patch("/{training_id}", response_model=TrainingResponse)
def update_training(
    training_id: int,
    payload: TrainingUpdateRequest,
    _: User = Depends(require_hr_staff("training:write")),
    service: TrainingService = Depends(get_training_service),
) -> TrainingResponse:
    try:
        return build_training_response(service.update_training(training_id, payload))
    except AppException as exc:
        _handle(exc)


@catalog_router.delete("/{training_id}", status_code=204)
def delete_training(
    training_id: int,
    _: User = Depends(require_hr_staff("training:write")),
    service: TrainingService = Depends(get_training_service),
) -> None:
    try:
        service.delete_training(training_id)
    except AppException as exc:
        _handle(exc)


@onboarding_router.get(
    "/{onboarding_id}/trainings",
    response_model=list[OnboardingTrainingResponse],
)
def list_onboarding_trainings(
    onboarding_id: int,
    _: User = Depends(require_hr_staff("training:read")),
    service: TrainingService = Depends(get_training_service),
) -> list[OnboardingTrainingResponse]:
    try:
        return [
            build_assignment_response(item)
            for item in service.list_assignments_for_hr(onboarding_id)
        ]
    except AppException as exc:
        _handle(exc)


@onboarding_router.post(
    "/{onboarding_id}/trainings",
    response_model=OnboardingTrainingResponse,
    status_code=201,
)
def assign_onboarding_training(
    onboarding_id: int,
    payload: OnboardingTrainingAssignRequest,
    _: User = Depends(require_hr_staff("training:write")),
    service: TrainingService = Depends(get_training_service),
) -> OnboardingTrainingResponse:
    try:
        return build_assignment_response(service.assign_training(onboarding_id, payload))
    except AppException as exc:
        _handle(exc)


@onboarding_router.delete(
    "/{onboarding_id}/trainings/{assignment_id}",
    status_code=204,
)
def remove_onboarding_training(
    onboarding_id: int,
    assignment_id: int,
    _: User = Depends(require_hr_staff("training:write")),
    service: TrainingService = Depends(get_training_service),
) -> None:
    try:
        service.remove_assignment(onboarding_id, assignment_id)
    except AppException as exc:
        _handle(exc)


@me_router.get("", response_model=list[OnboardingTrainingResponse])
def list_my_onboarding_trainings(
    current_user: User = Depends(get_current_user),
    service: TrainingService = Depends(get_training_service),
) -> list[OnboardingTrainingResponse]:
    try:
        return [
            build_assignment_response(item)
            for item in service.list_assignments_for_user(current_user.id)
        ]
    except AppException as exc:
        _handle(exc)


@me_router.patch("/{assignment_id}/complete", response_model=OnboardingTrainingResponse)
def complete_my_onboarding_training(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    service: TrainingService = Depends(get_training_service),
) -> OnboardingTrainingResponse:
    try:
        return build_assignment_response(
            service.complete_assignment_for_user(current_user.id, assignment_id)
        )
    except AppException as exc:
        _handle(exc)
