"""Unit tests: deterministic assistant router (no tools, no LLM)."""

from __future__ import annotations

from app.ai.core.context.models import AIExecutionContext
from app.ai.registry import (
    DOCUMENTS_AGENT,
    KNOWLEDGE_AGENT,
    LEAVE_AGENT,
    ONBOARDING_AGENT,
    RECRUITMENT_AGENT,
    TRAINING_AGENT,
    get_available_agents,
)
from app.ai.routing import route_message


def _emp_available():
    return (
        KNOWLEDGE_AGENT,
        LEAVE_AGENT,
        ONBOARDING_AGENT,
        TRAINING_AGENT,
        DOCUMENTS_AGENT,
    )


def _hr_available():
    return (
        KNOWLEDGE_AGENT,
        LEAVE_AGENT,
        RECRUITMENT_AGENT,
        ONBOARDING_AGENT,
        TRAINING_AGENT,
        DOCUMENTS_AGENT,
    )


def test_leave_intent_routes_to_leave():
    decision = route_message(
        "What's my remaining annual leave?",
        _emp_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "leave"


def test_onboarding_progress_routes_to_onboarding():
    decision = route_message(
        "What's my onboarding progress?",
        _emp_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "onboarding"


def test_my_training_routes_to_training():
    decision = route_message(
        "What trainings do I have?",
        _emp_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "training"


def test_show_assigned_trainings_routes_to_training():
    decision = route_message(
        "Show my assigned trainings",
        _emp_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "training"


def test_complete_my_training_routes_to_training():
    decision = route_message(
        "Mark my training as complete",
        _emp_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "training"


def test_list_trainings_catalogue_routes_to_training():
    decision = route_message(
        "What trainings are available?",
        _hr_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "training"


def test_assign_training_to_onboarding_routes_to_training():
    decision = route_message(
        "Assign security training to onboarding 42",
        _hr_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "training"


def test_training_assigned_to_onboarding_routes_to_training():
    decision = route_message(
        "What training is assigned to onboarding 42?",
        _hr_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "training"


def test_policy_say_about_training_prefers_knowledge():
    decision = route_message(
        "What does the employee handbook say about training?",
        _emp_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "knowledge"
    assert decision.reason == "policy_document_preference"


def test_course_alone_does_not_route_to_training():
    decision = route_message(
        "Tell me about courses.",
        _emp_available(),
    )
    assert decision.kind == "clarify"
    assert decision.agent_id is None


def test_knowledge_handbook_preferred_over_leave():
    decision = route_message(
        "According to the employee handbook, how many days of annual leave do we get?",
        _emp_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "knowledge"
    assert decision.reason == "policy_document_preference"


def test_knowledge_policy_intent():
    decision = route_message(
        "What does the company policy say about remote work?",
        _emp_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "knowledge"


def test_policy_say_about_onboarding_prefers_knowledge():
    """Policy/handbook Qs without task markers prefer Knowledge over Onboarding."""
    decision = route_message(
        "What does the company policy say about onboarding?",
        _emp_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "knowledge"
    assert decision.reason == "policy_document_preference"


def test_acknowledge_policy_task_routes_to_onboarding():
    decision = route_message(
        "Please acknowledge my onboarding policy task",
        _emp_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "onboarding"


def test_leave_balance_not_onboarding():
    decision = route_message(
        "What is my leave balance?",
        _emp_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "leave"


def test_onboarding_tasks_not_training():
    decision = route_message(
        "What are my onboarding tasks?",
        _emp_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "onboarding"


def test_recruitment_intent_when_available():
    decision = route_message(
        "How many candidates are currently shortlisted?",
        _hr_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "recruitment"


def test_unavailable_recruitment_intent_for_employee():
    decision = route_message(
        "Reject this candidate.",
        _emp_available(),
    )
    assert decision.kind == "unavailable"
    assert decision.agent_id is None
    assert "recruitment" in decision.reason


def test_ambiguous_interviews_clarify_for_hr():
    decision = route_message(
        "Tell me about interviews.",
        _hr_available(),
    )
    assert decision.kind == "clarify"
    assert decision.agent_id is None


def test_manager_approve_leave_routes_to_leave():
    decision = route_message(
        "Can I approve Sarah's leave?",
        _emp_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "leave"


def test_router_only_receives_available_agents():
    """Unavailable agents must not be selected even if keywords match."""
    decision = route_message(
        "Show me the hiring pipeline and candidates",
        _emp_available(),
    )
    assert decision.kind == "unavailable"
    assert decision.agent_id != "recruitment"


def test_router_does_not_execute_tools():
    """route_message is pure — no side effects beyond the decision object."""
    available = _hr_available()
    decision = route_message("Who is on leave this week?", available)
    assert decision.kind == "agent"
    assert decision.agent_id == "leave"
    # Available tuple unchanged / still the same objects.
    assert available[0] is KNOWLEDGE_AGENT


def test_no_available_agents_returns_unavailable():
    decision = route_message("Anything", ())
    assert decision.kind == "unavailable"
    assert decision.reason == "no_available_agents"


def test_availability_filter_before_routing_employee():
    ctx = AIExecutionContext(
        user_id=1,
        role_names=frozenset({"employee"}),
        permission_names=frozenset({"company_documents:read", "leaves:read"}),
        employee_id=1,
        candidate_id=None,
    )
    available = get_available_agents(ctx)
    assert "recruitment" not in {a.id for a in available}
    assert "onboarding" in {a.id for a in available}
    assert "training" in {a.id for a in available}
    assert "documents" in {a.id for a in available}
    decision = route_message("Shortlist this candidate", available)
    assert decision.kind == "unavailable"


def test_onboarding_unavailable_signal_for_candidate():
    decision = route_message(
        "What's my onboarding progress?",
        (KNOWLEDGE_AGENT,),  # no onboarding available
    )
    assert decision.kind == "unavailable"
    assert "onboarding" in decision.reason


def test_training_unavailable_signal_for_candidate():
    decision = route_message(
        "What trainings do I have?",
        (KNOWLEDGE_AGENT,),  # no training available
    )
    assert decision.kind == "unavailable"
    assert "training" in decision.reason


def test_documents_unavailable_signal_for_candidate():
    decision = route_message(
        "Show me my private documents.",
        (KNOWLEDGE_AGENT,),
    )
    assert decision.kind == "unavailable"
    assert "documents" in decision.reason


def test_summarize_handbook_routes_to_documents():
    decision = route_message(
        "Summarize the employee handbook.",
        _emp_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "documents"


def test_what_does_this_pdf_say_routes_to_documents():
    decision = route_message(
        "What does this PDF say about leave?",
        _emp_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "documents"


def test_what_does_the_document_say_routes_to_documents():
    decision = route_message(
        "What does the document say about remote work?",
        _emp_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "documents"


def test_show_private_documents_routes_to_documents():
    decision = route_message(
        "Show me my private documents.",
        _emp_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "documents"


def test_list_company_documents_routes_to_documents():
    decision = route_message(
        "List company documents.",
        _emp_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "documents"


def test_annual_leave_policy_routes_to_knowledge():
    decision = route_message(
        "What is our annual leave policy?",
        _emp_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "knowledge"


def test_leave_days_balance_still_leave():
    decision = route_message(
        "How many leave days do I have?",
        _emp_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "leave"


def test_training_pdf_routes_to_documents_not_training():
    decision = route_message(
        "What does my training PDF say?",
        _emp_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "documents"


def test_leave_policy_pdf_routes_to_documents_not_leave():
    decision = route_message(
        "What does my leave policy PDF say?",
        _emp_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "documents"


def test_my_training_still_routes_to_training_not_documents():
    decision = route_message(
        "What training do I have?",
        _emp_available(),
    )
    assert decision.kind == "agent"
    assert decision.agent_id == "training"