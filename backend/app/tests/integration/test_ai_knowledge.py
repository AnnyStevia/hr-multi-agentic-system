"""API tests for Knowledge Agent ask endpoint (mocked agent; no Gemini)."""

from unittest.mock import MagicMock

from app.api.v1 import ai_knowledge
from app.ai.rag.generation.schemas import Citation, RAGAnswer
from app.tests.helpers import auth_header, create_user_with_role


def test_ask_requires_auth(client):
    response = client.post("/api/v1/ai/knowledge/ask", json={"question": "Hello"})
    assert response.status_code == 401


def test_ask_requires_company_documents_read(client, db_session):
    create_user_with_role(
        db_session,
        email="candidate.ai@test.com",
        password="pass12345",
        role_name="candidate",
    )
    headers = auth_header(client, email="candidate.ai@test.com", password="pass12345")
    response = client.post(
        "/api/v1/ai/knowledge/ask",
        json={"question": "What is leave?"},
        headers=headers,
    )
    assert response.status_code == 403


def test_ask_returns_grounded_answer(client, db_session):
    create_user_with_role(
        db_session,
        email="hr.ai@test.com",
        password="hrpass123",
        role_name="hr",
        first_name="Amina",
        last_name="HR",
    )
    headers = auth_header(client, email="hr.ai@test.com", password="hrpass123")

    mock_agent = MagicMock()
    mock_agent.ask.return_value = RAGAnswer(
        query="What position?",
        answer="AI Software Engineer [1]",
        citations=[
            Citation(
                citation_id=1,
                chunk_id=6,
                company_document_id=2,
                page_start=1,
                page_end=1,
                document_name="Internship CV",
                content_hash="a" * 64,
            )
        ],
        has_context=True,
        retrieval_count=1,
        selected_context_count=1,
        model="gemini-3.8-flash",
    )

    client.app.dependency_overrides[ai_knowledge.get_knowledge_agent] = lambda: mock_agent
    try:
        response = client.post(
            "/api/v1/ai/knowledge/ask",
            json={"question": "What position?"},
            headers=headers,
        )
    finally:
        client.app.dependency_overrides.pop(ai_knowledge.get_knowledge_agent, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answer"] == "AI Software Engineer [1]"
    assert body["has_context"] is True
    assert body["citations"][0]["citation_id"] == 1
    assert body["citations"][0]["document_name"] == "Internship CV"
    assert body["citations"][0]["company_document_id"] == 2
    assert "content_hash" not in body["citations"][0]
    mock_agent.ask.assert_called_once()
