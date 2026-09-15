from sqlalchemy.orm import Session, joinedload, selectinload

from app.modules.identity.models import Candidate
from app.modules.recruitment.models import Application, ApplicationAnswer, Job, JobStatus


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
