"""Backfill onboarding records for employees missing one.

Revision ID: 016_onboarding_backfill
Revises: 015_onboarding_tasks
Create Date: 2026-09-16

"""

from alembic import op
from sqlalchemy.orm import Session

revision = "016_onboarding_backfill"
down_revision = "015_onboarding_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)
    try:
        from app.modules.employees.repository import EmployeeRepository
        from app.modules.onboarding.repository import OnboardingRepository
        from app.modules.onboarding.service import OnboardingService

        OnboardingService(
            OnboardingRepository(session),
            EmployeeRepository(session),
        ).backfill_missing_onboardings(commit=False)
        session.flush()
    finally:
        session.close()


def downgrade() -> None:
    pass
