from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.modules.identity.dependencies import get_current_user
from app.modules.identity.hr_access import require_hr_staff
from app.modules.identity.models import User
from app.modules.profile.dependencies import get_profile_service
from app.modules.profile.schemas import (
    EducationCreateRequest,
    EducationResponse,
    EducationUpdateRequest,
    EmployeeProfileResponse,
    ExperienceCreateRequest,
    ExperienceResponse,
    ExperienceUpdateRequest,
    PresignedProfilePictureUrlResponse,
    ProfileUpdateRequest,
)
from app.modules.profile.service import (
    ProfileService,
    build_education_response,
    build_experience_response,
    build_profile_response,
)
from app.shared.exceptions import AppException

me_router = APIRouter(prefix="/me/profile", tags=["My Profile"])
employees_router = APIRouter(prefix="/employees", tags=["Employee Profile"])


@me_router.get("", response_model=EmployeeProfileResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> EmployeeProfileResponse:
    try:
        return build_profile_response(service.get_for_user(current_user.id))
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@me_router.patch("", response_model=EmployeeProfileResponse)
def update_my_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> EmployeeProfileResponse:
    try:
        return build_profile_response(service.update_for_user(current_user.id, payload))
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@me_router.post("/picture", response_model=EmployeeProfileResponse, status_code=201)
async def upload_my_profile_picture(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> EmployeeProfileResponse:
    content = await file.read()
    try:
        employee = service.upload_picture_for_user(
            current_user.id,
            filename=file.filename,
            content_type=file.content_type,
            content=content,
        )
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return build_profile_response(employee)


@me_router.get("/picture/url", response_model=PresignedProfilePictureUrlResponse)
def get_my_profile_picture_url(
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> PresignedProfilePictureUrlResponse:
    try:
        return service.presigned_url_for_user(current_user.id)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@me_router.delete("/picture", status_code=204)
def delete_my_profile_picture(
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> None:
    try:
        service.delete_picture_for_user(current_user.id)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@me_router.get("/education", response_model=list[EducationResponse])
def list_my_education(
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> list[EducationResponse]:
    try:
        return [
            build_education_response(item)
            for item in service.list_educations_for_user(current_user.id)
        ]
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@me_router.post("/education", response_model=EducationResponse, status_code=201)
def create_my_education(
    payload: EducationCreateRequest,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> EducationResponse:
    try:
        return build_education_response(
            service.create_education_for_user(current_user.id, payload)
        )
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@me_router.patch("/education/{education_id}", response_model=EducationResponse)
def update_my_education(
    education_id: int,
    payload: EducationUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> EducationResponse:
    try:
        return build_education_response(
            service.update_education_for_user(current_user.id, education_id, payload)
        )
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@me_router.delete("/education/{education_id}", status_code=204)
def delete_my_education(
    education_id: int,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> None:
    try:
        service.delete_education_for_user(current_user.id, education_id)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@me_router.get("/experience", response_model=list[ExperienceResponse])
def list_my_experience(
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> list[ExperienceResponse]:
    try:
        return [
            build_experience_response(item)
            for item in service.list_experiences_for_user(current_user.id)
        ]
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@me_router.post("/experience", response_model=ExperienceResponse, status_code=201)
def create_my_experience(
    payload: ExperienceCreateRequest,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> ExperienceResponse:
    try:
        return build_experience_response(
            service.create_experience_for_user(current_user.id, payload)
        )
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@me_router.patch("/experience/{experience_id}", response_model=ExperienceResponse)
def update_my_experience(
    experience_id: int,
    payload: ExperienceUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> ExperienceResponse:
    try:
        return build_experience_response(
            service.update_experience_for_user(current_user.id, experience_id, payload)
        )
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@me_router.delete("/experience/{experience_id}", status_code=204)
def delete_my_experience(
    experience_id: int,
    current_user: User = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
) -> None:
    try:
        service.delete_experience_for_user(current_user.id, experience_id)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@employees_router.get("/{employee_id}/profile", response_model=EmployeeProfileResponse)
def get_employee_profile(
    employee_id: int,
    _: User = Depends(require_hr_staff("employees:read")),
    service: ProfileService = Depends(get_profile_service),
) -> EmployeeProfileResponse:
    try:
        return build_profile_response(service.get_for_employee(employee_id))
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@employees_router.get(
    "/{employee_id}/profile/education",
    response_model=list[EducationResponse],
)
def list_employee_education(
    employee_id: int,
    _: User = Depends(require_hr_staff("employees:read")),
    service: ProfileService = Depends(get_profile_service),
) -> list[EducationResponse]:
    try:
        return [
            build_education_response(item)
            for item in service.list_educations_for_employee(employee_id)
        ]
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@employees_router.get(
    "/{employee_id}/profile/experience",
    response_model=list[ExperienceResponse],
)
def list_employee_experience(
    employee_id: int,
    _: User = Depends(require_hr_staff("employees:read")),
    service: ProfileService = Depends(get_profile_service),
) -> list[ExperienceResponse]:
    try:
        return [
            build_experience_response(item)
            for item in service.list_experiences_for_employee(employee_id)
        ]
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@employees_router.get(
    "/{employee_id}/profile/picture/url",
    response_model=PresignedProfilePictureUrlResponse,
)
def get_employee_profile_picture_url(
    employee_id: int,
    _: User = Depends(require_hr_staff("employees:read")),
    service: ProfileService = Depends(get_profile_service),
) -> PresignedProfilePictureUrlResponse:
    try:
        return service.presigned_url_for_employee(employee_id)
    except AppException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
