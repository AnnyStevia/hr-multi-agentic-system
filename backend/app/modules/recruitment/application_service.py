from datetime import UTC, datetime
from io import BytesIO

from sqlalchemy.orm import Session

from app.modules.identity.models import Candidate, User
from app.modules.recruitment.file_validation import ValidatedUpload, validate_application_document
from app.modules.recruitment.models import (
    Application,
    ApplicationAnswer,
    ApplicationDocument,
    ApplicationEducation,
    ApplicationExperience,
    ApplicationStatus,
    DocumentKind,
    JobStatus,
    QuestionType,
)
from app.modules.recruitment.repository import ApplicationRepository, JobRepository
from app.modules.recruitment.status_transitions import validate_application_status_transition
from app.modules.recruitment.schemas import (
    AnswerInput,
    AnswerResponse,
    ApplicationDetail,
    ApplicationListItem,
    ApplicationPayload,
    CandidateSummary,
    DocumentResponse,
    FitAssessmentResponse,
    HrApplicationDetail,
    JobSummary,
    PresignedDocumentResponse,
)
from app.modules.identity.hr_access import list_hr_staff_user_ids
from app.modules.notifications.models import NotificationType
from app.modules.notifications.service import NotificationService
from app.shared.exceptions import AppException
from app.shared.storage import StorageService
from app.shared.storage.exceptions import StorageException

PRESIGNED_URL_EXPIRES_IN = 300


class ApplicationService:
    def __init__(
        self,
        db: Session,
        storage: StorageService,
        notification_service: NotificationService | None = None,
    ):
        self.db = db
        self.storage = storage
        self.notifications = notification_service
        self.jobs = JobRepository(db)
        self.applications = ApplicationRepository(db)

    def submit(
        self,
        *,
        user: User,
        job_id: int,
        payload: ApplicationPayload,
        cv_filename: str | None,
        cv_content_type: str | None,
        cv_content: bytes,
        cover_letter_filename: str | None,
        cover_letter_content_type: str | None,
        cover_letter_content: bytes | None,
    ) -> Application:
        candidate = self._require_candidate(user)
        job = self.jobs.get_by_id(job_id)
        if job is None or job.status != JobStatus.PUBLISHED:
            raise AppException("Job not found", status_code=404)

        existing = self.applications.get_by_candidate_and_job(candidate.id, job.id)
        if existing is not None:
            raise AppException("You have already applied to this job", status_code=409)

        answers = self._validate_answers(job.questions, payload.answers)
        candidate.phone = _normalize_phone(payload.phone)
        cv = validate_application_document(cv_filename, cv_content_type, cv_content)
        cover_letter = None
        if cover_letter_content:
            cover_letter = validate_application_document(
                cover_letter_filename,
                cover_letter_content_type,
                cover_letter_content,
            )

        application = Application(
            candidate_id=candidate.id,
            job_id=job.id,
            status=ApplicationStatus.SUBMITTED,
            submitted_at=datetime.now(UTC),
            education=[
                ApplicationEducation(
                    institution=item.institution.strip(),
                    degree=_optional(item.degree),
                    field_of_study=_optional(item.field_of_study),
                    start_year=item.start_year,
                    end_year=item.end_year,
                )
                for item in payload.education
            ],
            experience=[
                ApplicationExperience(
                    company=item.company.strip(),
                    title=item.title.strip(),
                    start_year=item.start_year,
                    end_year=item.end_year,
                    description=_optional(item.description),
                )
                for item in payload.experience
            ],
            answers=[
                ApplicationAnswer(question_id=question_id, value=value)
                for question_id, value in answers.items()
            ],
        )
        self.db.add(application)
        self.db.flush()

        uploaded_keys: list[str] = []
        try:
            self._add_document(application, DocumentKind.CV, cv, uploaded_keys)
            if cover_letter is not None:
                self._add_document(application, DocumentKind.COVER_LETTER, cover_letter, uploaded_keys)
            self.db.commit()
        except Exception:
            self.db.rollback()
            for key in uploaded_keys:
                try:
                    self.storage.delete_file(key)
                except StorageException:
                    pass
            raise

        loaded = self.applications.get_by_id(application.id)
        if loaded is None:
            raise AppException("Failed to load submitted application", status_code=500)
        self._notify_application_submitted(loaded)
        return loaded

    def _notify_application_submitted(self, application: Application) -> None:
        if self.notifications is None:
            return
        candidate_name = application.candidate.user.full_name
        job_title = application.job.title
        for recipient_id in list_hr_staff_user_ids(self.db):
            self.notifications.create_if_absent(
                recipient_user_id=recipient_id,
                type=NotificationType.APPLICATION_SUBMITTED,
                title="New application",
                message=f"{candidate_name} applied for {job_title}.",
                related_entity_type="application",
                related_entity_id=application.id,
            )

    def get_own(self, user: User, application_id: int) -> Application:
        candidate = self._require_candidate(user)
        application = self.applications.get_by_id(application_id)
        if application is None or application.candidate_id != candidate.id:
            raise AppException("Application not found", status_code=404)
        return application

    def get_own_for_job(self, user: User, job_id: int) -> Application | None:
        candidate = self._require_candidate(user)
        return self.applications.get_by_candidate_and_job(candidate.id, job_id)

    def list_own(self, user: User) -> list[Application]:
        candidate = self._require_candidate(user)
        return self.applications.list_for_candidate(candidate.id)

    def list_for_job(self, job_id: int) -> list[Application]:
        job = self.jobs.get_by_id(job_id)
        if job is None:
            raise AppException("Job not found", status_code=404)
        return self.applications.list_for_job(job_id)

    def get_for_hr(self, application_id: int) -> Application:
        application = self.applications.get_by_id(application_id)
        if application is None:
            raise AppException("Application not found", status_code=404)
        return application

    def update_status(self, application_id: int, status: ApplicationStatus) -> Application:
        if status == ApplicationStatus.HIRED:
            raise AppException(
                "Hiring must be done through the interview outcome workflow",
                status_code=400,
            )
        application = self.get_for_hr(application_id)
        previous_status = application.status
        validate_application_status_transition(application.status, status)
        application.status = status
        self.db.commit()
        loaded = self.applications.get_by_id(application.id)
        if loaded is None:
            raise AppException("Failed to load updated application", status_code=500)

        if (
            self.notifications is not None
            and previous_status != ApplicationStatus.SHORTLISTED
            and status == ApplicationStatus.SHORTLISTED
        ):
            self.notifications.create_notification(
                recipient_user_id=loaded.candidate.user_id,
                type=NotificationType.APPLICATION_STATUS_CHANGED,
                title="You've been shortlisted!",
                message=f"You have been shortlisted for {loaded.job.title}.",
                related_entity_type="application",
                related_entity_id=loaded.id,
            )

        return loaded

    def apply_interview_driven_status(
        self,
        application: Application,
        status: ApplicationStatus,
    ) -> None:
        validate_application_status_transition(application.status, status)
        application.status = status
        self.db.flush()

    def presigned_document_url(
        self,
        application_id: int,
        document_id: int,
        *,
        download: bool = False,
    ) -> PresignedDocumentResponse:
        application = self.get_for_hr(application_id)
        document = next((item for item in application.documents if item.id == document_id), None)
        if document is None:
            raise AppException("Document not found", status_code=404)
        try:
            url = self.storage.generate_presigned_url(
                document.storage_key,
                expires_in=PRESIGNED_URL_EXPIRES_IN,
                filename=document.original_filename,
                download=download,
            )
        except StorageException as exc:
            raise AppException(exc.message, status_code=exc.status_code) from exc
        return PresignedDocumentResponse(
            url=url,
            filename=document.original_filename,
            content_type=document.content_type,
            expires_in=PRESIGNED_URL_EXPIRES_IN,
            download=download,
        )

    def _add_document(
        self,
        application: Application,
        kind: DocumentKind,
        upload: ValidatedUpload,
        uploaded_keys: list[str],
    ) -> None:
        folder = "cv" if kind == DocumentKind.CV else "cover-letters"
        document = ApplicationDocument(
            application_id=application.id,
            kind=kind,
            original_filename=upload.filename,
            content_type=upload.content_type,
            size_bytes=len(upload.content),
            storage_key="pending",
        )
        self.db.add(document)
        self.db.flush()
        storage_key = (
            f"applications/{application.id}/{folder}/{document.id}{upload.extension}"
        )
        try:
            self.storage.upload_file(
                storage_key,
                BytesIO(upload.content),
                content_type=upload.content_type,
            )
        except StorageException as exc:
            raise AppException(exc.message, status_code=exc.status_code) from exc
        uploaded_keys.append(storage_key)
        document.storage_key = storage_key

    def _require_candidate(self, user: User) -> Candidate:
        candidate = self.db.query(Candidate).filter(Candidate.user_id == user.id).first()
        if candidate is None:
            raise AppException("Candidate profile not found", status_code=403)
        return candidate

    def _validate_answers(
        self,
        questions: list,
        answers: list[AnswerInput],
    ) -> dict[int, str]:
        by_id = {item.question_id: item.value.strip() for item in answers}
        if len(by_id) != len(answers):
            raise AppException("Duplicate answers are not allowed", status_code=400)

        question_ids = {question.id for question in questions}
        unknown = set(by_id) - question_ids
        if unknown:
            raise AppException("One or more answers do not belong to this job", status_code=400)

        validated: dict[int, str] = {}
        for question in questions:
            value = by_id.get(question.id, "")
            if question.required and not value:
                raise AppException(f"An answer is required for: {question.prompt}", status_code=400)
            if not value:
                continue
            validated[question.id] = _normalize_answer(question.question_type, value, question.prompt)
        return validated


def _optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_phone(value: str) -> str:
    stripped = value.strip()
    digits = "".join(character for character in stripped if character.isdigit())
    if len(digits) < 8 or len(stripped) > 30:
        raise AppException("Enter a valid phone number", status_code=400)
    allowed = set("0123456789+ -().")
    if any(character not in allowed for character in stripped):
        raise AppException("Enter a valid phone number", status_code=400)
    return stripped


def _normalize_answer(question_type: QuestionType, value: str, prompt: str) -> str:
    if question_type == QuestionType.NUMBER:
        try:
            float(value.replace(",", "."))
        except ValueError as exc:
            raise AppException(f"A number is required for: {prompt}", status_code=400) from exc
        return value
    if question_type == QuestionType.YES_NO:
        normalized = value.strip().lower()
        if normalized in {"yes", "true", "1"}:
            return "yes"
        if normalized in {"no", "false", "0"}:
            return "no"
        raise AppException(f"Answer yes or no for: {prompt}", status_code=400)
    return value


def build_candidate_summary(application: Application) -> CandidateSummary:
    user = application.candidate.user
    return CandidateSummary(
        id=application.candidate_id,
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        full_name=user.full_name,
        email=user.email,
        phone=application.candidate.phone,
    )


def build_application_list_item(application: Application) -> ApplicationListItem:
    kinds = {document.kind for document in application.documents}
    return ApplicationListItem(
        id=application.id,
        status=application.status,
        submitted_at=application.submitted_at,
        candidate=build_candidate_summary(application),
        has_cv=DocumentKind.CV in kinds,
        has_cover_letter=DocumentKind.COVER_LETTER in kinds,
        fit_score=application.fit_score,
        fit_level=application.fit_level,
    )


def build_fit_assessment(application: Application) -> FitAssessmentResponse | None:
    if application.fit_analyzed_at is None or application.fit_score is None:
        return None
    return FitAssessmentResponse(
        fit_score=application.fit_score,
        fit_level=application.fit_level or "",
        matching_skills=list(application.matching_skills or []),
        missing_skills=list(application.missing_skills or []),
        experience_match=application.experience_match,
        education_match=application.education_match,
        explanation=application.fit_explanation,
        analysis_version=application.fit_analysis_version,
        analyzed_at=application.fit_analyzed_at,
    )


def build_application_detail(application: Application) -> ApplicationDetail:
    answer_by_question = {item.question_id: item.value for item in application.answers}
    questions = sorted(application.job.questions, key=lambda item: item.display_order)
    return ApplicationDetail(
        id=application.id,
        status=application.status,
        submitted_at=application.submitted_at,
        created_at=application.created_at,
        updated_at=application.updated_at,
        candidate=build_candidate_summary(application),
        job=JobSummary(
            id=application.job.id,
            title=application.job.title,
            department=application.job.department_rel.name if application.job.department_rel else None,
            department_id=application.job.department_id,
            status=application.job.status,
        ),
        education=application.education,
        experience=application.experience,
        answers=[
            AnswerResponse(
                question_id=question.id,
                prompt=question.prompt,
                question_type=question.question_type,
                required=question.required,
                value=answer_by_question.get(question.id, ""),
            )
            for question in questions
        ],
        documents=[
            DocumentResponse.model_validate(document)
            for document in application.documents
        ],
    )


def build_hr_application_detail(application: Application) -> HrApplicationDetail:
    base = build_application_detail(application)
    return HrApplicationDetail(
        **base.model_dump(),
        fit_assessment=build_fit_assessment(application),
    )
