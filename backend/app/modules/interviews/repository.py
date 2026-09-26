from datetime import datetime

from sqlalchemy.orm import Session, joinedload, selectinload

from app.modules.employees.models import Employee
from app.modules.identity.models import Candidate, User
from app.modules.interviews.models import Interview, InterviewInterviewer, InterviewSlot, InterviewStatus
from app.modules.recruitment.models import Application


class InterviewRepository:
    def __init__(self, db: Session):
        self.db = db

    def _base_query(self):
        return (
            self.db.query(Interview)
            .options(
                selectinload(Interview.slots),
                joinedload(Interview.selected_slot),
                joinedload(Interview.interviewer),
                selectinload(Interview.panel_assignments).joinedload(InterviewInterviewer.employee),
                joinedload(Interview.application)
                .joinedload(Application.candidate)
                .joinedload(Candidate.user),
                joinedload(Interview.application).joinedload(Application.job),
            )
        )

    def get_by_id(self, interview_id: int) -> Interview | None:
        return self._base_query().filter(Interview.id == interview_id).first()

    def list_for_application(self, application_id: int) -> list[Interview]:
        return (
            self._base_query()
            .filter(Interview.application_id == application_id)
            .order_by(Interview.created_at.desc())
            .all()
        )

    def list_upcoming_scheduled(
        self, *, now: datetime, until: datetime, limit: int = 8
    ) -> list[Interview]:
        return (
            self._base_query()
            .join(InterviewSlot, Interview.selected_slot_id == InterviewSlot.id)
            .filter(
                Interview.status == InterviewStatus.SCHEDULED,
                InterviewSlot.starts_at >= now,
                InterviewSlot.starts_at <= until,
            )
            .order_by(InterviewSlot.starts_at.asc(), Interview.id.asc())
            .limit(limit)
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

    def get_employees_by_ids(self, employee_ids: list[int]) -> list[Employee]:
        if not employee_ids:
            return []
        return self.db.query(Employee).filter(Employee.id.in_(employee_ids)).all()

    def get_users_by_ids(self, user_ids: list[int]) -> dict[int, User]:
        if not user_ids:
            return {}
        users = self.db.query(User).filter(User.id.in_(user_ids)).all()
        return {user.id: user for user in users}

    def has_proposed_for_application(self, application_id: int) -> bool:
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
