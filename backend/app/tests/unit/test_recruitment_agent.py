"""Unit tests for RecruitmentAgent (mocked LLM; no Gemini)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.ai.agents.recruitment import (
    RecruitmentAgent,
    RecruitmentAgentError,
    RecruitmentAgentRequest,
    RecruitmentAgentValidationError,
)
from app.ai.core.context import AIExecutionContext
from app.ai.core.llm.base import LLMToolResponse, ToolCall
from app.ai.tools import ToolAuthorizationError


def _hr_context() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=1,
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"recruitment:read"}),
        employee_id=10,
        candidate_id=None,
    )


def _agent(provider: MagicMock) -> RecruitmentAgent:
    return RecruitmentAgent(
        llm_provider=provider,
        job_service=MagicMock(),
        application_service=MagicMock(),
    )


def test_empty_question_rejected():
    agent = _agent(MagicMock())
    with pytest.raises(RecruitmentAgentValidationError, match="empty"):
        agent.ask(RecruitmentAgentRequest(question="  ", context=_hr_context()))


def test_agent_answers_using_get_application_tool():
    job_service = MagicMock()
    application_service = MagicMock()
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(id="c1", name="get_application", arguments={"application_id": 3}),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content="Application 3 is submitted for Backend Engineer.",
            tool_calls=(),
            model="mock",
        ),
    ]

    # Avoid real service work: stub tool execute via monkeypatch after agent build
    agent = RecruitmentAgent(
        llm_provider=provider,
        job_service=job_service,
        application_service=application_service,
    )
    tool = agent.registry.get("get_application")
    tool.execute = MagicMock(  # type: ignore[method-assign]
        return_value=tool.output_model.model_validate(
            {
                "application": {
                    "id": 3,
                    "status": "submitted",
                    "submitted_at": "2026-01-02T00:00:00Z",
                    "created_at": "2026-01-02T00:00:00Z",
                    "updated_at": "2026-01-02T00:00:00Z",
                    "candidate": {
                        "id": 1,
                        "user_id": 2,
                        "first_name": "Ada",
                        "last_name": "Lovelace",
                        "full_name": "Ada Lovelace",
                        "email": "ada@example.com",
                        "phone": None,
                    },
                    "job": {
                        "id": 7,
                        "title": "Backend Engineer",
                        "department": "Engineering",
                        "department_id": 1,
                        "status": "published",
                    },
                    "education": [],
                    "experience": [],
                    "answers": [],
                    "documents": [],
                    "fit_assessment": None,
                }
            }
        )
    )

    answer = agent.ask(
        RecruitmentAgentRequest(
            question="What is the status of application 3?",
            context=_hr_context(),
        )
    )
    assert "submitted" in answer.answer.lower() or "Backend" in answer.answer
    assert answer.tool_names_called == ["get_application"]
    tool.execute.assert_called_once()


def test_agent_uses_get_job_and_list_and_fit_tools():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(id="1", name="get_job", arguments={"job_id": 7}),
                ToolCall(id="2", name="list_job_applications", arguments={"job_id": 7}),
                ToolCall(id="3", name="get_application_fit", arguments={"application_id": 3}),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content="Job Backend Engineer has applicants; fit score 82 GOOD.",
            tool_calls=(),
            model="mock",
        ),
    ]
    agent = _agent(provider)
    for name, payload in (
        (
            "get_job",
            {
                "id": 7,
                "title": "Backend Engineer",
                "description": "APIs",
                "requirements": "Python",
                "employment_type": "full_time",
                "internship_duration_months": None,
                "status": "published",
                "department": "Engineering",
                "position": None,
                "location": None,
                "published_at": None,
                "closed_at": None,
            },
        ),
        (
            "list_job_applications",
            {"job_id": 7, "count": 0, "applications": []},
        ),
        (
            "get_application_fit",
            {
                "application_id": 3,
                "available": True,
                "fit_assessment": {
                    "fit_score": 82,
                    "fit_level": "GOOD",
                    "matching_skills": ["Python"],
                    "missing_skills": [],
                    "experience_match": "Strong",
                    "education_match": "Match",
                    "explanation": "Good match",
                    "analysis_version": "1",
                    "analyzed_at": "2026-01-03T00:00:00Z",
                },
                "message": None,
            },
        ),
    ):
        tool = agent.registry.get(name)
        tool.execute = MagicMock(  # type: ignore[method-assign]
            return_value=tool.output_model.model_validate(payload)
        )

    answer = agent.ask(
        RecruitmentAgentRequest(question="Summarize job 7 and fit for app 3", context=_hr_context())
    )
    assert set(answer.tool_names_called) == {
        "get_job",
        "list_job_applications",
        "get_application_fit",
    }
    assert "82" in answer.answer or "GOOD" in answer.answer or "Backend" in answer.answer


def test_agent_does_not_hallucinate_when_no_tool_content():
    provider = MagicMock()
    provider.generate_with_tools.return_value = LLMToolResponse(
        content="",
        tool_calls=(),
        model="mock",
    )
    answer = _agent(provider).ask(
        RecruitmentAgentRequest(question="Who applied?", context=_hr_context())
    )
    assert answer.tool_names_called == []
    assert "enough information" in answer.answer.lower()


def test_agent_registry_includes_overview_and_write_tools():
    agent = _agent(MagicMock())
    names = {tool.name for tool in agent.registry.list_tools()}
    assert "list_recruitment_applications" in names
    assert "shortlist_application" in names
    assert "reject_application" in names
    assert agent.registry.get("shortlist_application").metadata.operation == "write"
    assert agent.registry.get("shortlist_application").metadata.may_require_confirmation is True


def _hr_write_context() -> AIExecutionContext:
    return AIExecutionContext(
        user_id=1,
        role_names=frozenset({"hr"}),
        permission_names=frozenset({"recruitment:read", "recruitment:write"}),
        employee_id=10,
        candidate_id=None,
    )


def test_explicit_shortlist_invokes_write_tool():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(id="w1", name="shortlist_application", arguments={"application_id": 12}),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content="Application 12 was shortlisted.",
            tool_calls=(),
            model="mock",
        ),
    ]
    agent = _agent(provider)
    tool = agent.registry.get("shortlist_application")
    tool.execute = MagicMock(  # type: ignore[method-assign]
        return_value=tool.output_model.model_validate(
            {
                "application_id": 12,
                "previous_status": "screening",
                "new_status": "shortlisted",
                "candidate_id": 5,
                "candidate_name": "Jane Doe",
                "job_id": 3,
                "job_title": "Backend",
                "reason": None,
            }
        )
    )
    answer = agent.ask(
        RecruitmentAgentRequest(
            question="Shortlist application 12.",
            context=_hr_write_context(),
        )
    )
    assert answer.tool_names_called == ["shortlist_application"]
    assert "shortlisted" in answer.answer.lower()
    tool.execute.assert_called_once()


def test_informational_request_does_not_invoke_write_tool():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(
                    id="r1",
                    name="get_application_fit",
                    arguments={"application_id": 12},
                ),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content="Fit score is 84 GOOD.",
            tool_calls=(),
            model="mock",
        ),
    ]
    agent = _agent(provider)
    fit_tool = agent.registry.get("get_application_fit")
    fit_tool.execute = MagicMock(  # type: ignore[method-assign]
        return_value=fit_tool.output_model.model_validate(
            {
                "application_id": 12,
                "available": True,
                "fit_assessment": {
                    "fit_score": 84,
                    "fit_level": "GOOD",
                    "matching_skills": ["Python"],
                    "missing_skills": [],
                    "experience_match": "Strong",
                    "education_match": "Match",
                    "explanation": "Good",
                    "analysis_version": "1",
                    "analyzed_at": "2026-01-03T00:00:00Z",
                },
                "message": None,
            }
        )
    )
    write = agent.registry.get("shortlist_application")
    write.execute = MagicMock()  # type: ignore[method-assign]
    answer = agent.ask(
        RecruitmentAgentRequest(
            question="What is the fit score for application 12?",
            context=_hr_write_context(),
        )
    )
    assert "shortlist_application" not in answer.tool_names_called
    assert "reject_application" not in answer.tool_names_called
    write.execute.assert_not_called()


def test_overview_question_uses_summary_tool():
    provider = MagicMock()
    provider.generate_with_tools.side_effect = [
        LLMToolResponse(
            content=None,
            tool_calls=(
                ToolCall(
                    id="o1",
                    name="list_recruitment_applications",
                    arguments={"mode": "summary"},
                ),
            ),
            model="mock",
        ),
        LLMToolResponse(
            content="You have 2 unique candidates and 3 applications.",
            tool_calls=(),
            model="mock",
        ),
    ]
    agent = _agent(provider)
    tool = agent.registry.get("list_recruitment_applications")
    tool.execute = MagicMock(  # type: ignore[method-assign]
        return_value=tool.output_model.model_validate(
            {
                "mode": "summary",
                "summary": {
                    "total_unique_candidates": 2,
                    "total_applications": 3,
                    "total_jobs_with_applications": 1,
                    "applications_by_job": [],
                },
                "listing": None,
            }
        )
    )
    answer = agent.ask(
        RecruitmentAgentRequest(question="How many candidates do we have?", context=_hr_context())
    )
    assert answer.tool_names_called == ["list_recruitment_applications"]
    assert "2" in answer.answer


def test_unauthorized_tool_call_surfaces_as_agent_error():
    provider = MagicMock()
    provider.generate_with_tools.return_value = LLMToolResponse(
        content=None,
        tool_calls=(ToolCall(id="x", name="get_job", arguments={"job_id": 1}),),
        model="mock",
    )
    agent = _agent(provider)
    unauthorized = AIExecutionContext(
        user_id=9,
        role_names=frozenset({"employee"}),
        permission_names=frozenset(),
        employee_id=1,
        candidate_id=None,
    )
    with pytest.raises((RecruitmentAgentError, ToolAuthorizationError)):
        agent.ask(RecruitmentAgentRequest(question="Show job 1", context=unauthorized))
