"""Phase 6.4G mocked-LLM end-to-end recruitment demo scenario."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.ai.audit.models import AiToolActionAudit
from app.ai.core.llm.base import LLMToolResponse, ToolCall
from app.modules.identity.models import User
from app.modules.recruitment.models import Application, ApplicationStatus
from app.tests.helpers import create_user_with_role
from app.tests.integration.test_ai_recruitment_writes import _build_agent, _hr_write_context
from app.tests.integration.test_application_review import _submit_application
from app.ai.agents.recruitment import RecruitmentAgentRequest


def test_e2e_recruitment_ask_confirm_audit_reread(client, db_session):
    """
    Demo path: ask get_application → shortlist pending → confirm → audit → re-ask status.
    Mocked LLM; no live Gemini/Google.
    """
    application, _job, _cand_headers, _storage = _submit_application(
        client, db_session, email="e2e.demo@test.com"
    )
    app_id = application["id"]
    row = db_session.query(Application).filter(Application.id == app_id).one()
    row.status = ApplicationStatus.SCREENING
    db_session.commit()

    create_user_with_role(
        db_session,
        email="hr.e2e.demo@test.com",
        password="hrpass123",
        role_name="hr",
    )
    hr_user = db_session.query(User).filter(User.email == "hr.e2e.demo@test.com").one()
    ctx = _hr_write_context(hr_user.id)

    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        # 1) Read application
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(id="r1", name="get_application", arguments={"application_id": app_id}),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content=f"Application {app_id} is in screening.",
            tool_calls=(),
            model="mock",
        ),
        # 2) Propose shortlist
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(
                    id="w1",
                    name="shortlist_application",
                    arguments={"application_id": app_id},
                ),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content="Please confirm shortlisting in the UI.",
            tool_calls=(),
            model="mock",
        ),
        # 3) Re-read after confirm
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(id="r2", name="get_application", arguments={"application_id": app_id}),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content=f"Application {app_id} is now shortlisted.",
            tool_calls=(),
            model="mock",
        ),
    ]

    agent = _build_agent(db_session, provider)

    read1 = agent.ask(
        RecruitmentAgentRequest(question=f"Tell me about application {app_id}", context=ctx)
    )
    assert "get_application" in read1.tool_names_called
    assert read1.pending_confirmation is None

    pending = agent.ask(
        RecruitmentAgentRequest(question=f"Shortlist application {app_id}", context=ctx)
    )
    assert pending.pending_confirmation is not None
    db_session.refresh(row)
    assert row.status == ApplicationStatus.SCREENING

    confirmed = agent.confirm(token=pending.pending_confirmation.token, context=ctx)
    assert "shortlist_application" in confirmed.tool_names_called
    assert "Result: {" not in confirmed.answer
    db_session.refresh(row)
    assert row.status == ApplicationStatus.SHORTLISTED

    audits = (
        db_session.query(AiToolActionAudit)
        .filter(AiToolActionAudit.tool_name == "shortlist_application")
        .all()
    )
    assert {a.phase for a in audits} >= {"proposed", "confirmed", "executed"}
    assert all(a.actor_user_id == hr_user.id for a in audits)

    read2 = agent.ask(
        RecruitmentAgentRequest(
            question=f"What is the status of application {app_id} now?",
            context=ctx,
        )
    )
    assert "get_application" in read2.tool_names_called
    assert "shortlisted" in read2.answer.lower()
