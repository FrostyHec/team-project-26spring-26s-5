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
        assert len(tools) == 4  # 4 calculator tools
        names = {t["name"] for t in tools}
        assert "add" in names
        assert "subtract" in names
        assert "multiply" in names
        assert "divide" in names


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
