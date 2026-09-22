"""Thin sync entrypoint so Profile/Document/Training avoid circular imports."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.onboarding.models import OnboardingTaskType


def sync_onboarding_tasks_for_employee(
    db: Session,
    employee_id: int,
    *,
    task_types: set[OnboardingTaskType] | None = None,
) -> None:
    from app.modules.onboarding.dependencies import build_onboarding_service

    build_onboarding_service(db).sync_verified_tasks(employee_id, task_types=task_types)
