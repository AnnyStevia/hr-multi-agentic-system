from datetime import UTC, datetime

from app.modules.employees.models import DepartmentStatus
from app.modules.employees.repository import DepartmentRepository
from app.modules.recruitment.models import EmploymentType, Job, JobQuestion, JobStatus
from app.modules.recruitment.repository import JobRepository
from app.modules.recruitment.schemas import JobCreateRequest, JobQuestionInput, JobResponse, JobUpdateRequest
from app.shared.exceptions import AppException


class JobService:
    def __init__(self, repository: JobRepository, departments: DepartmentRepository):
        self.repository = repository
        self.departments = departments

    def list_jobs(self) -> list[Job]:
        return self.repository.list_all()

    def list_published_jobs(self) -> list[Job]:
        return self.repository.list_published()

    def get_job(self, job_id: int) -> Job:
        job = self.repository.get_by_id(job_id)
        if job is None:
            raise AppException("Job not found", status_code=404)
        return job

    def get_published_job(self, job_id: int) -> Job:
        job = self.get_job(job_id)
        if job.status != JobStatus.PUBLISHED:
            raise AppException("Job not found", status_code=404)
        return job

    def create_job(self, payload: JobCreateRequest, created_by_user_id: int) -> Job:
        department_id = self._require_active_department(payload.department_id)
        job = Job(
            title=payload.title.strip(),
            description=payload.description.strip(),
            department_id=department_id,
            position=_optional_text(payload.position),
            location=_optional_text(payload.location),
            employment_type=payload.employment_type or EmploymentType.FULL_TIME,
            requirements=_optional_text(payload.requirements),
            status=JobStatus.DRAFT,
            created_by_user_id=created_by_user_id,
            questions=_build_questions(payload.questions),
        )
        return self.repository.add(job)

    def update_job(self, job_id: int, payload: JobUpdateRequest) -> Job:
        job = self.get_job(job_id)
        if job.status != JobStatus.DRAFT:
            raise AppException("Only draft jobs can be edited", status_code=409)

        data = payload.model_dump(exclude_unset=True)
        questions = data.pop("questions", None)
        if "department_id" in data:
            data["department_id"] = self._require_active_department(data["department_id"])
        for field, value in data.items():
            if isinstance(value, str):
                value = value.strip() or None if field != "title" and field != "description" else value.strip()
            setattr(job, field, value)
        if questions is not None:
            job.questions = _build_questions(payload.questions or [])
        return self.repository.save(job)

    def publish_job(self, job_id: int) -> Job:
        job = self.get_job(job_id)
        if job.status != JobStatus.DRAFT:
            raise AppException("Only draft jobs can be published", status_code=409)
        job.status = JobStatus.PUBLISHED
        job.published_at = datetime.now(UTC)
        return self.repository.save(job)

    def close_job(self, job_id: int) -> Job:
        job = self.get_job(job_id)
        if job.status != JobStatus.PUBLISHED:
            raise AppException("Only published jobs can be closed", status_code=409)
        job.status = JobStatus.CLOSED
        job.closed_at = datetime.now(UTC)
        return self.repository.save(job)

    def _require_active_department(self, department_id: int | None) -> int | None:
        if department_id is None:
            return None
        department = self.departments.get_by_id(department_id)
        if department is None:
            raise AppException("Department not found", status_code=400)
        if department.status != DepartmentStatus.ACTIVE:
            raise AppException("Department is not active", status_code=400)
        return department.id


def build_job_response(job: Job) -> JobResponse:
    department_name = job.department_rel.name if job.department_rel is not None else None
    return JobResponse(
        id=job.id,
        title=job.title,
        description=job.description,
        department_id=job.department_id,
        department=department_name,
        position=job.position,
        location=job.location,
        employment_type=job.employment_type,
        requirements=job.requirements,
        status=job.status,
        published_at=job.published_at,
        closed_at=job.closed_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
        created_by_user_id=job.created_by_user_id,
        questions=job.questions,
    )


def _build_questions(questions: list[JobQuestionInput]) -> list[JobQuestion]:
    built: list[JobQuestion] = []
    for index, item in enumerate(questions):
        prompt = item.prompt.strip()
        if not prompt:
            raise AppException("Question text cannot be empty", status_code=400)
        built.append(
            JobQuestion(
                prompt=prompt,
                question_type=item.question_type,
                required=item.required,
                display_order=item.display_order if item.display_order is not None else index,
            )
        )
    return built


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
