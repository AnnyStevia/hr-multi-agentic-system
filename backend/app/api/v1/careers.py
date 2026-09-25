import json

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from app.modules.identity.models import User
from app.modules.onboarding.dependencies import require_careers_access
from app.modules.recruitment.application_service import (
    ApplicationService,
    build_application_detail,
)
from app.modules.recruitment.dependencies import get_application_service, get_job_service
from app.modules.recruitment.fit_analysis_runner import run_application_fit_analysis
from app.modules.recruitment.schemas import ApplicationDetail, ApplicationPayload, JobResponse
from app.modules.recruitment.service import JobService, build_job_response
from app.shared.exceptions import AppException

router = APIRouter(prefix="/careers/jobs", tags=["Careers"])


def _handle(exc: AppException) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("", response_model=list[JobResponse])
def list_career_jobs(
    _candidate: User = Depends(require_careers_access),
    job_service: JobService = Depends(get_job_service),
) -> list[JobResponse]:
    return [build_job_response(job) for job in job_service.list_published_jobs()]


@router.get("/{job_id}", response_model=JobResponse)
def get_career_job(
    job_id: int,
    _candidate: User = Depends(require_careers_access),
    job_service: JobService = Depends(get_job_service),
) -> JobResponse:
    try:
        return build_job_response(job_service.get_published_job(job_id))
    except AppException as exc:
        _handle(exc)


@router.get("/{job_id}/application", response_model=ApplicationDetail)
def get_own_job_application(
    job_id: int,
    current_user: User = Depends(require_careers_access),
    application_service: ApplicationService = Depends(get_application_service),
) -> ApplicationDetail:
    try:
        application = application_service.get_own_for_job(current_user, job_id)
        if application is None:
            raise AppException("Application not found", status_code=404)
        return build_application_detail(application)
    except AppException as exc:
        _handle(exc)


@router.post("/{job_id}/applications", response_model=ApplicationDetail, status_code=201)
def apply_to_job(
    job_id: int,
    background_tasks: BackgroundTasks,
    education: str = Form(...),
    experience: str = Form(...),
    answers: str = Form("[]"),
    phone: str = Form(...),
    cv: UploadFile = File(...),
    cover_letter: UploadFile | None = File(None),
    current_user: User = Depends(require_careers_access),
    application_service: ApplicationService = Depends(get_application_service),
) -> ApplicationDetail:
    try:
        try:
            payload = ApplicationPayload(
                phone=phone,
                education=_parse_json_list(education, "education"),
                experience=_parse_json_list(experience, "experience"),
                answers=_parse_json_list(answers, "answers"),
            )
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
        cv_content = cv.file.read()
        cover_content = None
        cover_name = None
        cover_type = None
        if cover_letter is not None and cover_letter.filename:
            cover_content = cover_letter.file.read()
            cover_name = cover_letter.filename
            cover_type = cover_letter.content_type
        application = application_service.submit(
            user=current_user,
            job_id=job_id,
            payload=payload,
            cv_filename=cv.filename,
            cv_content_type=cv.content_type,
            cv_content=cv_content,
            cover_letter_filename=cover_name,
            cover_letter_content_type=cover_type,
            cover_letter_content=cover_content,
        )
        background_tasks.add_task(run_application_fit_analysis, application.id)
        return build_application_detail(application)
    except AppException as exc:
        _handle(exc)


def _parse_json_list(raw: str, field_name: str) -> list:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid JSON for {field_name}") from exc
    if not isinstance(parsed, list):
        raise HTTPException(status_code=422, detail=f"{field_name} must be a JSON array")
    return parsed
