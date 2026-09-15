from sqlalchemy.orm import Session, joinedload, selectinload

from app.modules.employees.models import Employee
from app.modules.identity.models import Candidate
from app.modules.interviews.models import Interview, InterviewSlot
from app.modules.recruitment.models import Application


class InterviewRepository:
    def __init__(self, db: Session):
        self.db = db

    def _query(self):
        return (
            self.db.query(Interview)
            .options(
                selectinload(Interview.slots),
                joinedload(Interview.selected_slot),
                joinedload(Interview.interviewer),
                joinedload(Interview.application)
                .joinedload(Application.candidate)
                .joinedload(Candidate.user),
                joinedload(Interview.application).joinedload(Application.job),
            )
        )

    def get_by_id(self, interview_id: int) -> Interview | None:
        return self._query().filter(Interview.id == interview_id).first()

    def list_for_application(self, application_id: int) -> list[Interview]:
        return (
            self._query()
            .filter(Interview.application_id == application_id)
            .order_by(Interview.created_at.desc())
            .all()
        )

    def add(self, interview: Interview) -> Interview:
        self.db.add(interview)
        self.db.commit()
        loaded = self.get_by_id(interview.id)
        if loaded is None:
            raise RuntimeError("Failed to load created interview")
        return loaded

    def save(self, interview: Interview) -> Interview:
        self.db.commit()
        loaded = self.get_by_id(interview.id)
        if loaded is None:
            raise RuntimeError("Failed to load updated interview")
        return loaded

    def get_employee_for_user(self, user_id: int) -> Employee | None:
        return self.db.query(Employee).filter(Employee.user_id == user_id).first()

    def has_proposed_for_application(self, application_id: int) -> bool:
        from app.modules.interviews.models import InterviewStatus

        return (
            self.db.query(Interview)
            .filter(
                Interview.application_id == application_id,
                Interview.status == InterviewStatus.PROPOSED,
            )
            .count()
            > 0
        )

    def has_active_invitation_for_application(self, application_id: int) -> bool:
        """Block new invites while proposed, scheduled, or completed without outcome."""
        from app.modules.interviews.models import InterviewStatus

        blocking = (
            self.db.query(Interview)
            .filter(
                Interview.application_id == application_id,
                Interview.status.in_([InterviewStatus.PROPOSED, InterviewStatus.SCHEDULED]),
            )
            .count()
        )
        if blocking > 0:
            return True

        pending_outcome = (
            self.db.query(Interview)
            .filter(
                Interview.application_id == application_id,
                Interview.status == InterviewStatus.COMPLETED,
                Interview.outcome.is_(None),
            )
            .count()
        )
        return pending_outcome > 0

    def save_without_commit(self, interview: Interview) -> None:
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
