from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.modules.identity.models import Candidate
from app.modules.recruitment.models import (
    Application,
    ApplicationAnswer,
    ApplicationStatus,
    Job,
    JobStatus,
)


class JobRepository:
    def __init__(self, db: Session):
        self.db = db

    def _job_query(self):
        return self.db.query(Job).options(
            selectinload(Job.questions),
            joinedload(Job.department_rel),
        )

    def list_all(self) -> list[Job]:
        return self._job_query().order_by(Job.created_at.desc()).all()

    def list_published(self) -> list[Job]:
        return (
            self._job_query()
            .filter(Job.status == JobStatus.PUBLISHED)
            .order_by(Job.published_at.desc())
            .all()
        )

    def get_by_id(self, job_id: int) -> Job | None:
        return self._job_query().filter(Job.id == job_id).first()

    def add(self, job: Job) -> Job:
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return self.get_by_id(job.id) or job

    def save(self, job: Job) -> Job:
        self.db.commit()
        self.db.refresh(job)
        return self.get_by_id(job.id) or job

    def count_by_status(self, status: JobStatus) -> int:
        return self.db.query(Job).filter(Job.status == status).count()


class ApplicationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, application_id: int) -> Application | None:
        return (
            self.db.query(Application)
            .options(
                joinedload(Application.candidate).joinedload(Candidate.user),
                joinedload(Application.job).joinedload(Job.department_rel),
                joinedload(Application.job).selectinload(Job.questions),
                selectinload(Application.answers).joinedload(ApplicationAnswer.question),
                selectinload(Application.education),
                selectinload(Application.experience),
                selectinload(Application.documents),
            )
            .filter(Application.id == application_id)
            .first()
        )

    def get_by_candidate_and_job(self, candidate_id: int, job_id: int) -> Application | None:
        return (
            self.db.query(Application)
            .filter(Application.candidate_id == candidate_id, Application.job_id == job_id)
            .first()
        )

    def list_for_candidate(self, candidate_id: int) -> list[Application]:
        return (
            self.db.query(Application)
            .options(joinedload(Application.job))
            .filter(Application.candidate_id == candidate_id)
            .order_by(Application.submitted_at.desc())
            .all()
        )

    def list_for_job(self, job_id: int) -> list[Application]:
        return (
            self.db.query(Application)
            .options(
                joinedload(Application.candidate).joinedload(Candidate.user),
                selectinload(Application.documents),
            )
            .filter(Application.job_id == job_id)
            .order_by(Application.submitted_at.desc())
            .all()
        )

    def count_by_statuses(self, statuses: list[ApplicationStatus]) -> int:
        if not statuses:
            return 0
        return self.db.query(Application).filter(Application.status.in_(statuses)).count()

    def list_pending(self, *, limit: int = 8) -> list[Application]:
        pending = [ApplicationStatus.SUBMITTED, ApplicationStatus.SCREENING]
        return (
            self.db.query(Application)
            .options(
                joinedload(Application.candidate).joinedload(Candidate.user),
                joinedload(Application.job),
            )
            .filter(Application.status.in_(pending))
            .order_by(Application.submitted_at.asc(), Application.id.asc())
            .limit(limit)
            .all()
        )

    def _filtered_query(
        self,
        *,
        job_id: int | None = None,
        status: ApplicationStatus | None = None,
    ):
        query = self.db.query(Application)
        if job_id is not None:
            query = query.filter(Application.job_id == job_id)
        if status is not None:
            query = query.filter(Application.status == status)
        return query

    def count_applications(
        self,
        *,
        job_id: int | None = None,
        status: ApplicationStatus | None = None,
    ) -> int:
        return self._filtered_query(job_id=job_id, status=status).count()

    def count_unique_candidates(
        self,
        *,
        job_id: int | None = None,
        status: ApplicationStatus | None = None,
    ) -> int:
        query = self.db.query(func.count(func.distinct(Application.candidate_id)))
        if job_id is not None:
            query = query.filter(Application.job_id == job_id)
        if status is not None:
            query = query.filter(Application.status == status)
        return int(query.scalar() or 0)

    def count_applications_by_job(
        self,
        *,
        status: ApplicationStatus | None = None,
        job_id: int | None = None,
    ) -> list[tuple[int, str, int]]:
        query = (
            self.db.query(Job.id, Job.title, func.count(Application.id))
            .join(Application, Application.job_id == Job.id)
            .group_by(Job.id, Job.title)
            .order_by(func.count(Application.id).desc(), Job.title.asc())
        )
        if status is not None:
            query = query.filter(Application.status == status)
        if job_id is not None:
            query = query.filter(Job.id == job_id)
        return [(int(row[0]), str(row[1]), int(row[2])) for row in query.all()]

    def list_filtered(
        self,
        *,
        job_id: int | None = None,
        status: ApplicationStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Application]:
        return (
            self._filtered_query(job_id=job_id, status=status)
            .options(
                joinedload(Application.candidate).joinedload(Candidate.user),
                joinedload(Application.job),
            )
            .order_by(Application.submitted_at.desc(), Application.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
