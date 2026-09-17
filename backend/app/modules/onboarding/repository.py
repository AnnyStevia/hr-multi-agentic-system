from sqlalchemy.orm import Session, joinedload, selectinload

from app.modules.employees.models import Employee
from app.modules.onboarding.models import Onboarding, OnboardingTask


class OnboardingRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, onboarding_id: int) -> Onboarding | None:
        return self.db.query(Onboarding).filter(Onboarding.id == onboarding_id).first()

    def get_by_employee_id(self, employee_id: int) -> Onboarding | None:
        return self.db.query(Onboarding).filter(Onboarding.employee_id == employee_id).first()

    def list_employee_ids_without_onboarding(self) -> list[int]:
        rows = (
            self.db.query(Employee.id)
            .outerjoin(Onboarding, Onboarding.employee_id == Employee.id)
            .filter(Onboarding.id.is_(None))
            .order_by(Employee.id.asc())
            .all()
        )
        return [row[0] for row in rows]

    def list_for_hr(self) -> list[Onboarding]:
        return (
            self.db.query(Onboarding)
            .options(
                joinedload(Onboarding.employee),
                selectinload(Onboarding.tasks),
            )
            .join(Employee, Onboarding.employee_id == Employee.id)
            .order_by(Onboarding.started_at.desc(), Onboarding.id.desc())
            .all()
        )

    def add(self, onboarding: Onboarding, *, commit: bool = True) -> Onboarding:
        self.db.add(onboarding)
        self.db.flush()
        if commit:
            self.db.commit()
            self.db.refresh(onboarding)
        return onboarding

    def save(self, onboarding: Onboarding) -> Onboarding:
        self.db.commit()
        self.db.refresh(onboarding)
        return onboarding

    def list_tasks_by_onboarding_id(self, onboarding_id: int) -> list[OnboardingTask]:
        return (
            self.db.query(OnboardingTask)
            .filter(OnboardingTask.onboarding_id == onboarding_id)
            .order_by(OnboardingTask.id.asc())
            .all()
        )

    def get_task_by_id(self, task_id: int) -> OnboardingTask | None:
        return (
            self.db.query(OnboardingTask)
            .options(joinedload(OnboardingTask.onboarding))
            .filter(OnboardingTask.id == task_id)
            .first()
        )

    def add_task(self, task: OnboardingTask, *, commit: bool = True) -> OnboardingTask:
        self.db.add(task)
        self.db.flush()
        if commit:
            self.db.commit()
            self.db.refresh(task)
        return task

    def save_task(self, task: OnboardingTask) -> OnboardingTask:
        self.db.commit()
        self.db.refresh(task)
        return task

    def delete_task(self, task: OnboardingTask) -> None:
        self.db.delete(task)
        self.db.commit()
