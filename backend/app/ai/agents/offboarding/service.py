"""Offboarding Agent factory."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.agents.offboarding.agent import OffboardingAgent
from app.ai.core.llm.base import LLMProvider
from app.modules.employees.repository import (
    DepartmentRepository,
    EmployeeRepository,
    PositionRepository,
)
from app.modules.employees.service import DepartmentService, EmployeeService, PositionService
from app.modules.identity.models import User
from app.modules.offboarding.dependencies import build_offboarding_service


def build_offboarding_agent(
    *,
    llm_provider: LLMProvider,
    db: Session,
) -> OffboardingAgent:
    offboarding = build_offboarding_service(db)
    departments = DepartmentService(DepartmentRepository(db))
    positions = PositionService(PositionRepository(db), departments)
    employees = EmployeeService(EmployeeRepository(db), departments, None, positions)

    def _get_user(user_id: int) -> User | None:
        return db.query(User).filter(User.id == user_id).first()

    return OffboardingAgent(
        llm_provider=llm_provider,
        offboarding=offboarding,
        employees=employees,
        get_user=_get_user,
        db=db,
    )
