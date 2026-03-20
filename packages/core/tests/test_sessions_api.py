"""Tests for session management API endpoints."""

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
        db_path=":memory:",
    )
    app = create_app(config)
    with TestClient(app) as c:
        yield c


class TestCreateSession:
    """Test POST /sessions."""

    def test_create_session_default_title(self, client: TestClient) -> None:
        """Creating a session without title should succeed."""
        response = client.post("/sessions", json={})
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["title"] == ""

    def test_create_session_with_title(self, client: TestClient) -> None:
        """Creating a session with a title should set it."""
        response = client.post("/sessions", json={"title": "My Chat"})
        assert response.status_code == 201
        assert response.json()["title"] == "My Chat"


class TestListSessions:
    """Test GET /sessions."""

    def test_list_empty(self, client: TestClient) -> None:
        """Listing with no sessions returns empty list."""
        response = client.get("/sessions")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_after_create(self, client: TestClient) -> None:
        """Sessions should appear in the list after creation."""
        client.post("/sessions", json={"title": "S1"})
        client.post("/sessions", json={"title": "S2"})

        response = client.get("/sessions")
        assert response.status_code == 200
        sessions = response.json()
        assert len(sessions) == 2
        titles = {s["title"] for s in sessions}
        assert "S1" in titles
        assert "S2" in titles


class TestGetSession:
    """Test GET /sessions/{session_id}."""

    def test_get_existing(self, client: TestClient) -> None:
        """Getting an existing session should return detail."""
        create_resp = client.post("/sessions", json={"title": "Detail"})
        session_id = create_resp.json()["id"]

        response = client.get(f"/sessions/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["session"]["id"] == session_id
        assert data["session"]["title"] == "Detail"
        assert data["messages"] == []

    def test_get_nonexistent_returns_404(self, client: TestClient) -> None:
        """Getting a non-existent session should return 404."""
        response = client.get("/sessions/no-such-id")
        assert response.status_code == 404


class TestDeleteSession:
    """Test DELETE /sessions/{session_id}."""

    def test_delete_existing(self, client: TestClient) -> None:
        """Deleting an existing session should succeed."""
        create_resp = client.post("/sessions", json={})
        session_id = create_resp.json()["id"]

        response = client.delete(f"/sessions/{session_id}")
        assert response.status_code == 200
        assert response.json() == {"ok": True}

        # Verify it's gone
        get_resp = client.get(f"/sessions/{session_id}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_returns_404(self, client: TestClient) -> None:
        """Deleting a non-existent session should return 404."""
        response = client.delete("/sessions/no-such-id")
        assert response.status_code == 404


class TestChatWithSession:
    """Test that chat endpoint accepts session_id."""

    def test_chat_request_with_session_id(self, client: TestClient) -> None:
        """Chat request body should accept session_id field."""
        with patch(
            "agent_core.engine.agent.ReactAgent.chat",
            new_callable=AsyncMock,
            return_value="Hello!",
        ):
            response = client.post(
                "/chat",
                json={
                    "message": "Hi",
                    "session_id": "test-session-123",
                },
            )
            assert response.status_code == 200
            assert response.json()["response"] == "Hello!"
