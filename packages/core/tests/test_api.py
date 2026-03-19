"""Tests for the FastAPI server endpoints."""

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
