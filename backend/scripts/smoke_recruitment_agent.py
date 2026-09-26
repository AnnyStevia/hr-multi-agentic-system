"""Controlled live smoke for Recruitment Agent (optional; needs GEMINI_API_KEY).

Run from backend/:

  $env:PYTHONPATH = "."
  .\\.venv\\Scripts\\python.exe scripts/smoke_recruitment_agent.py
"""

from __future__ import annotations

import os
import sys

from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.employees import models as employee_models  # noqa: F401
from app.modules.recruitment import models as recruitment_models  # noqa: F401

from app.ai.agents.recruitment import RecruitmentAgent, RecruitmentAgentRequest
from app.ai.core.context.models import AIExecutionContext
from app.ai.core.llm import get_llm_provider
from app.core.database import SessionLocal
from app.core.config import settings
from app.modules.employees.repository import DepartmentRepository
from app.modules.identity.models import Permission, Role, RolePermission, User, UserRole
from app.modules.interviews.repository import InterviewRepository
from app.modules.interviews.service import InterviewService
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.service import NotificationService
from app.modules.recruitment.application_service import ApplicationService
from app.modules.recruitment.repository import ApplicationRepository, JobRepository
from app.modules.recruitment.service import JobService
from app.shared.storage import get_storage_service

QUERY = "List applications briefly if any job exists; otherwise say you lack information."


def _context_with_recruitment_read(db) -> AIExecutionContext:
    user = (
        db.query(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .filter(Permission.name == "recruitment:read", User.is_active.is_(True))
        .order_by(User.id.asc())
        .first()
    )
    assert user is not None, "No user with recruitment:read found"
    role_names: set[str] = set()
    permission_names: set[str] = set()
    for user_role in user.user_roles:
        role = user_role.role
        if role is None:
            continue
        role_names.add(role.name)
        for role_perm in role.role_permissions:
            if role_perm.permission is not None:
                permission_names.add(role_perm.permission.name)
    return AIExecutionContext(
        user_id=user.id,
        role_names=frozenset(role_names),
        permission_names=frozenset(permission_names),
        employee_id=None,
        candidate_id=None,
    )


def main() -> int:
    if not (os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", None)):
        print("SKIP: GEMINI_API_KEY not configured")
        return 0

    db = SessionLocal()
    try:
        context = _context_with_recruitment_read(db)
        agent = RecruitmentAgent(
            llm_provider=get_llm_provider(),
            job_service=JobService(JobRepository(db), DepartmentRepository(db)),
            application_service=ApplicationService(
                db,
                get_storage_service(),
                NotificationService(NotificationRepository(db)),
            ),
            interview_service=InterviewService(
                InterviewRepository(db),
                ApplicationRepository(db),
                NotificationService(NotificationRepository(db)),
            ),
        )
        answer = agent.ask(RecruitmentAgentRequest(question=QUERY, context=context))
        print("model:", answer.model)
        print("tools:", answer.tool_names_called)
        print("answer:", answer.answer)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
