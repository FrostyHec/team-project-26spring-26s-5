"""Tests for the FastAPI server endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from agent_core.api.server import create_app
from agent_core.config import AgentConfig


@pytest.fixture
def client() -> TestClient:
    """Create a test client with lifespan context."""
    config = AgentConfig(
        openai_api_key="test-key",
        model_name="gpt-4o-mini",
    )
    app = create_app(config)
    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:
    """Test the health check endpoint."""

    def test_health_check(self, client: TestClient) -> None:
        """Test health endpoint returns ok."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestToolsEndpoint:
    """Test the tools listing endpoint."""

    def test_list_tools(self, client: TestClient) -> None:
        """Test listing available tools."""
        response = client.get("/tools")
        assert response.status_code == 200
        tools = response.json()
        assert isinstance(tools, list)
        assert (
            len(tools) == 26
        )  # 4 calc + 1 weather + 4 widget + 9 deadline + 7 email + 1 policy_search
        names = {t["name"] for t in tools}
        assert "add" in names
        assert "subtract" in names
        assert "multiply" in names
        assert "divide" in names
        assert "get_weather" in names
        assert "show_document" in names  # show_calendar removed


class TestChatEndpointErrors:
    """Test error handling for chat endpoint."""

    def test_chat_llm_error_returns_502(self, client: TestClient) -> None:
        """Test that LLM API errors return 502 with error detail."""
        with patch(
            "agent_core.engine.agent.ReactAgent.chat",
            new_callable=AsyncMock,
            side_effect=Exception("API key quota exhausted"),
        ):
            response = client.post(
                "/chat",
                json={"message": "Hello"},
            )
            assert response.status_code == 502
            assert "API key quota exhausted" in response.json()["detail"]

    def test_chat_missing_message_returns_422(self, client: TestClient) -> None:
        """Test that missing message field returns 422."""
        response = client.post("/chat", json={})
        assert response.status_code == 422

    def test_chat_accepts_skill_parameter(self, client: TestClient) -> None:
        """Test that chat endpoint accepts skill parameter."""
        with patch(
            "agent_core.engine.agent.ReactAgent.chat",
            new_callable=AsyncMock,
            return_value="Hello!",
        ):
            response = client.post(
                "/chat",
                json={"message": "Hello", "skill": "course_assistant"},
            )
            assert response.status_code == 200


class TestSkillsEndpoint:
    """Test the skills listing endpoint."""

    def test_list_skills(self, client: TestClient) -> None:
        """Test listing available skills."""
        response = client.get("/skills")
        assert response.status_code == 200
        skills = response.json()
        assert isinstance(skills, list)
        assert len(skills) >= 6
        ids = {s["id"] for s in skills}
        assert "general" in ids
        assert "course_assistant" in ids
        assert "deadline_manager" in ids

    def test_skills_have_required_fields(self, client: TestClient) -> None:
        """Test that each skill has all required fields."""
        response = client.get("/skills")
        skills = response.json()
        for skill in skills:
            assert "id" in skill
            assert "name" in skill
            assert "description" in skill
            assert "system_prompt" in skill
            assert "icon" in skill
            assert "color" in skill


class TestApprovalEndpoint:
    """Test the tool approval endpoint."""

    def test_approve_missing_pending_returns_404(self, client: TestClient) -> None:
        """Test approving a non-existent pending returns 404."""
        response = client.post(
            "/chat/approve",
            json={"tool_call_id": "nonexistent", "approved": True},
        )
        assert response.status_code == 404

    def test_approve_existing_pending(self, client: TestClient) -> None:
        """Test approving an existing pending approval."""
        from agent_core.api.approval import _pending, create_pending

        _pending.clear()
        create_pending("test_tc_1")

        response = client.post(
            "/chat/approve",
            json={"tool_call_id": "test_tc_1", "approved": True},
        )
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_reject_existing_pending(self, client: TestClient) -> None:
        """Test rejecting an existing pending approval."""
        from agent_core.api.approval import _pending, create_pending

        _pending.clear()
        create_pending("test_tc_2")

        response = client.post(
            "/chat/approve",
            json={"tool_call_id": "test_tc_2", "approved": False},
        )
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_approve_missing_fields_returns_422(self, client: TestClient) -> None:
        """Test that missing fields returns 422."""
        response = client.post("/chat/approve", json={})
        assert response.status_code == 422
