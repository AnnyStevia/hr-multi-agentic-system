from sqlalchemy.orm import Session, joinedload

from app.modules.employees.models import Employee
from app.modules.offboarding.models import (
    ACTIVE_EXIT_INTERVIEW_STATUSES,
    ACTIVE_OFFBOARDING_STATUSES,
    ExitInterview,
    OffboardingCase,
    OffboardingClearanceItem,
    OffboardingStatus,
    OffboardingTask,
)


class OffboardingRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, case_id: int) -> OffboardingCase | None:
        return (
            self.db.query(OffboardingCase)
            .options(
                joinedload(OffboardingCase.employee),
                joinedload(OffboardingCase.created_by),
            )
            .filter(OffboardingCase.id == case_id)
            .first()
        )

    def get_by_id_for_update(self, case_id: int) -> OffboardingCase | None:
        # Lock the case row only. Postgres rejects FOR UPDATE on the nullable
        # side of OUTER JOINs, so do not combine with_for_update + joinedload.
        locked = (
            self.db.query(OffboardingCase)
            .filter(OffboardingCase.id == case_id)
            .with_for_update()
            .first()
        )
        if locked is None:
            return None
        return self.get_by_id(case_id)

    def get_active_for_employee(self, employee_id: int) -> OffboardingCase | None:
        return (
            self.db.query(OffboardingCase)
            .filter(
                OffboardingCase.employee_id == employee_id,
                OffboardingCase.status.in_(tuple(ACTIVE_OFFBOARDING_STATUSES)),
            )
            .first()
        )

    def list_for_hr(
        self,
        *,
        status: OffboardingStatus | None = None,
        employee_id: int | None = None,
    ) -> list[OffboardingCase]:
        query = (
            self.db.query(OffboardingCase)
            .options(joinedload(OffboardingCase.employee))
            .join(Employee, OffboardingCase.employee_id == Employee.id)
        )
        if status is not None:
            query = query.filter(OffboardingCase.status == status)
        if employee_id is not None:
            query = query.filter(OffboardingCase.employee_id == employee_id)
        return (
            query.order_by(OffboardingCase.initiated_at.desc(), OffboardingCase.id.desc()).all()
        )

    def list_for_employee(self, employee_id: int) -> list[OffboardingCase]:
        return (
            self.db.query(OffboardingCase)
            .filter(OffboardingCase.employee_id == employee_id)
            .order_by(OffboardingCase.initiated_at.desc(), OffboardingCase.id.desc())
            .all()
        )

    def add(self, case: OffboardingCase, *, commit: bool = True) -> OffboardingCase:
        self.db.add(case)
        self.db.flush()
        if commit:
            self.db.commit()
            self.db.refresh(case)
        return case

    def save(self, case: OffboardingCase) -> OffboardingCase:
        self.db.commit()
        self.db.refresh(case)
        return case

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def list_tasks_for_case(self, case_id: int) -> list[OffboardingTask]:
        return (
            self.db.query(OffboardingTask)
            .options(
                joinedload(OffboardingTask.assigned_to),
                joinedload(OffboardingTask.completed_by),
            )
            .filter(OffboardingTask.offboarding_case_id == case_id)
            .order_by(OffboardingTask.id.asc())
            .all()
        )

    def get_task_for_case(self, case_id: int, task_id: int) -> OffboardingTask | None:
        return (
            self.db.query(OffboardingTask)
            .options(
                joinedload(OffboardingTask.assigned_to),
                joinedload(OffboardingTask.completed_by),
                joinedload(OffboardingTask.offboarding_case),
            )
            .filter(
                OffboardingTask.id == task_id,
                OffboardingTask.offboarding_case_id == case_id,
            )
            .first()
        )

    def get_task_by_id(self, task_id: int) -> OffboardingTask | None:
        return (
            self.db.query(OffboardingTask)
            .options(
                joinedload(OffboardingTask.assigned_to),
                joinedload(OffboardingTask.offboarding_case),
            )
            .filter(OffboardingTask.id == task_id)
            .first()
        )

    def list_tasks_assigned_to_employee(self, employee_id: int) -> list[OffboardingTask]:
        return (
            self.db.query(OffboardingTask)
            .options(joinedload(OffboardingTask.offboarding_case))
            .filter(OffboardingTask.assigned_to_employee_id == employee_id)
            .order_by(OffboardingTask.id.asc())
            .all()
        )

    def add_task(self, task: OffboardingTask, *, commit: bool = True) -> OffboardingTask:
        self.db.add(task)
        self.db.flush()
        if commit:
            self.db.commit()
            self.db.refresh(task)
        return task

    def save_task(self, task: OffboardingTask) -> OffboardingTask:
        self.db.commit()
        self.db.refresh(task)
        return task

    def list_clearance_for_case(self, case_id: int) -> list[OffboardingClearanceItem]:
        return (
            self.db.query(OffboardingClearanceItem)
            .options(joinedload(OffboardingClearanceItem.completed_by))
            .filter(OffboardingClearanceItem.offboarding_case_id == case_id)
            .order_by(OffboardingClearanceItem.id.asc())
            .all()
        )

    def count_clearance_for_case(self, case_id: int) -> int:
        return (
            self.db.query(OffboardingClearanceItem)
            .filter(OffboardingClearanceItem.offboarding_case_id == case_id)
            .count()
        )

    def get_clearance_for_case(
        self, case_id: int, item_id: int
    ) -> OffboardingClearanceItem | None:
        return (
            self.db.query(OffboardingClearanceItem)
            .options(
                joinedload(OffboardingClearanceItem.completed_by),
                joinedload(OffboardingClearanceItem.offboarding_case),
            )
            .filter(
                OffboardingClearanceItem.id == item_id,
                OffboardingClearanceItem.offboarding_case_id == case_id,
            )
            .first()
        )

    def add_clearance_item(
        self, item: OffboardingClearanceItem, *, commit: bool = True
    ) -> OffboardingClearanceItem:
        self.db.add(item)
        self.db.flush()
        if commit:
            self.db.commit()
            self.db.refresh(item)
        return item

    def save_clearance_item(self, item: OffboardingClearanceItem) -> OffboardingClearanceItem:
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_active_exit_interview_for_case(self, case_id: int) -> ExitInterview | None:
        return (
            self.db.query(ExitInterview)
            .options(
                joinedload(ExitInterview.interviewer),
                joinedload(ExitInterview.offboarding_case).joinedload(
                    OffboardingCase.employee
                ),
            )
            .filter(
                ExitInterview.offboarding_case_id == case_id,
                ExitInterview.status.in_(tuple(ACTIVE_EXIT_INTERVIEW_STATUSES)),
            )
            .first()
        )

    def get_exit_interview_by_id(self, exit_interview_id: int) -> ExitInterview | None:
        return (
            self.db.query(ExitInterview)
            .options(
                joinedload(ExitInterview.interviewer),
                joinedload(ExitInterview.offboarding_case).joinedload(
                    OffboardingCase.employee
                ),
            )
            .filter(ExitInterview.id == exit_interview_id)
            .first()
        )

    def get_exit_interview_for_case(
        self, case_id: int, exit_interview_id: int
    ) -> ExitInterview | None:
        return (
            self.db.query(ExitInterview)
            .options(
                joinedload(ExitInterview.interviewer),
                joinedload(ExitInterview.offboarding_case).joinedload(
                    OffboardingCase.employee
                ),
            )
            .filter(
                ExitInterview.id == exit_interview_id,
                ExitInterview.offboarding_case_id == case_id,
            )
            .first()
        )

    def add_exit_interview(
        self, interview: ExitInterview, *, commit: bool = True
    ) -> ExitInterview:
        self.db.add(interview)
        self.db.flush()
        if commit:
            self.db.commit()
            self.db.refresh(interview)
        return interview

    def save_exit_interview(self, interview: ExitInterview) -> ExitInterview:
        self.db.commit()
        self.db.refresh(interview)
        return interview
