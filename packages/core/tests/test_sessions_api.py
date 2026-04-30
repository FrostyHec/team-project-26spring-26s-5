"""Tests for session management API endpoints."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from agent_core.api.dependencies import get_conversation_tree_store, get_store
from agent_core.api.server import create_app
from agent_core.config import AgentConfig
from agent_core.models.session import (
    ChatNodeRecord,
    MessageRole,
    MessageStatus,
    NodeSourceKind,
)


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


class TestSessionPreferences:
    """Test PATCH /sessions/{session_id}/preferences."""

    def test_update_session_preferences(self, client: TestClient) -> None:
        create_resp = client.post("/sessions", json={"title": "Prefs"})
        session_id = create_resp.json()["id"]

        response = client.patch(
            f"/sessions/{session_id}/preferences",
            json={"selected_provider_id": "primary", "fallback_mode": "auto"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["selected_provider_id"] == "primary"
        assert data["fallback_mode"] == "auto"

    def test_update_session_preferences_allows_clearing_provider(
        self, client: TestClient
    ) -> None:
        create_resp = client.post("/sessions", json={"title": "Prefs"})
        session_id = create_resp.json()["id"]
        client.patch(
            f"/sessions/{session_id}/preferences",
            json={"selected_provider_id": "primary", "fallback_mode": "auto"},
        )

        response = client.patch(
            f"/sessions/{session_id}/preferences",
            json={"selected_provider_id": None, "fallback_mode": "manual"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["selected_provider_id"] is None
        assert data["fallback_mode"] == "manual"


class TestUpdateSession:
    """Test PATCH /sessions/{session_id}."""

    def test_update_session_title(self, client: TestClient) -> None:
        create_resp = client.post("/sessions", json={"title": "Before"})
        session_id = create_resp.json()["id"]

        response = client.patch(
            f"/sessions/{session_id}",
            json={"title": "After"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "After"


class TestInterruptSession:
    """Test POST /sessions/{session_id}/interrupt."""

    def test_interrupt_session_persists_partial_output(
        self, client: TestClient
    ) -> None:
        create_resp = client.post("/sessions", json={"title": "Interrupt"})
        session_id = create_resp.json()["id"]

        response = client.post(
            f"/sessions/{session_id}/interrupt",
            json={"user_message": "hello", "assistant_content": "partial answer"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "human"
        assert data["messages"][1]["status"] == "interrupted"

    def test_partial_response_persists_failed_status(self, client: TestClient) -> None:
        create_resp = client.post("/sessions", json={"title": "Failed"})
        session_id = create_resp.json()["id"]

        response = client.post(
            f"/sessions/{session_id}/partial-response",
            json={
                "user_message": "hello",
                "assistant_content": "partial answer",
                "assistant_status": "failed",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["messages"][1]["status"] == "failed"

    def test_partial_response_strips_think_blocks_before_persistence(
        self, client: TestClient
    ) -> None:
        create_resp = client.post("/sessions", json={"title": "Think"})
        session_id = create_resp.json()["id"]

        response = client.post(
            f"/sessions/{session_id}/partial-response",
            json={
                "user_message": "hello",
                "assistant_content": "<think>internal</think>\n\nvisible answer",
                "assistant_status": "failed",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["messages"][1]["content"] == "visible answer"

    def test_partial_response_rejects_completed_status(
        self, client: TestClient
    ) -> None:
        create_resp = client.post("/sessions", json={"title": "Completed"})
        session_id = create_resp.json()["id"]

        response = client.post(
            f"/sessions/{session_id}/partial-response",
            json={
                "user_message": "hello",
                "assistant_content": "partial answer",
                "assistant_status": "completed",
            },
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any("interrupted" in str(item) for item in detail)
        assert any("failed" in str(item) for item in detail)


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


def _now() -> datetime:
    return datetime.now(UTC)


async def _seed_node(**kwargs: object) -> ChatNodeRecord:
    return await get_conversation_tree_store().add_node(ChatNodeRecord(**kwargs))


class TestConversationTreeSessionRoutes:
    def test_get_session_returns_tree_projection(self, client: TestClient) -> None:
        store = get_store()
        session = asyncio.run(store.create_session("Tree Detail"))
        user_node = asyncio.run(
            _seed_node(
                id="user-1",
                session_id=session.id,
                parent_id=None,
                role=MessageRole.HUMAN,
                content="hello",
                status=MessageStatus.COMPLETED,
                version_group_id="vg-user-1",
                version_index=0,
                source_kind=NodeSourceKind.INITIAL,
                created_at=_now(),
                updated_at=_now(),
            )
        )
        assistant_node = asyncio.run(
            _seed_node(
                id="assistant-1",
                session_id=session.id,
                parent_id=user_node.id,
                role=MessageRole.AI,
                content="answer",
                status=MessageStatus.COMPLETED,
                version_group_id="vg-assistant-1",
                version_index=0,
                source_kind=NodeSourceKind.INITIAL,
                response_to_node_id=user_node.id,
                trace_steps=[
                    {"type": "loop_start"},
                    {"type": "thinking", "content": "Plan A"},
                    {"type": "tool_start", "name": "calc", "input": {"x": 1}},
                    {"type": "tool_end", "name": "calc", "output": "1"},
                    {"type": "thinking", "content": "Plan B"},
                    {"type": "loop_end"},
                ],
                created_at=_now(),
                updated_at=_now(),
            )
        )
        asyncio.run(store.update_current_leaf(session.id, assistant_node.id))

        response = client.get(f"/sessions/{session.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["visible_path"] == ["user-1", "assistant-1"]
        assert len(data["nodes"]) == 2
        assert [message["content"] for message in data["messages"]] == [
            "hello",
            "answer",
        ]
        assert data["nodes"][1]["trace_steps"] == [
            {"type": "loop_start"},
            {"type": "thinking", "content": "Plan A"},
            {"type": "tool_start", "name": "calc", "input": {"x": 1}},
            {"type": "tool_end", "name": "calc", "output": "1"},
            {"type": "thinking", "content": "Plan B"},
            {"type": "loop_end"},
        ]

    def test_select_version_switches_visible_path(self, client: TestClient) -> None:
        store = get_store()
        session = asyncio.run(store.create_session("Version Switch"))
        user_node = asyncio.run(
            _seed_node(
                id="user-1",
                session_id=session.id,
                parent_id=None,
                role=MessageRole.HUMAN,
                content="hello",
                status=MessageStatus.COMPLETED,
                version_group_id="vg-user-1",
                version_index=0,
                source_kind=NodeSourceKind.INITIAL,
                created_at=_now(),
                updated_at=_now(),
            )
        )
        assistant_a = asyncio.run(
            _seed_node(
                id="assistant-1",
                session_id=session.id,
                parent_id=user_node.id,
                role=MessageRole.AI,
                content="branch-a",
                status=MessageStatus.COMPLETED,
                version_group_id="vg-assistant-1",
                version_index=0,
                source_kind=NodeSourceKind.INITIAL,
                response_to_node_id=user_node.id,
                created_at=_now(),
                updated_at=_now(),
            )
        )
        assistant_b = asyncio.run(
            _seed_node(
                id="assistant-2",
                session_id=session.id,
                parent_id=user_node.id,
                role=MessageRole.AI,
                content="branch-b",
                status=MessageStatus.COMPLETED,
                version_group_id="vg-assistant-1",
                version_index=1,
                source_kind=NodeSourceKind.RETRY,
                source_node_id=assistant_a.id,
                response_to_node_id=user_node.id,
                created_at=_now(),
                updated_at=_now(),
            )
        )
        asyncio.run(store.update_current_leaf(session.id, assistant_a.id))

        response = client.patch(
            f"/sessions/{session.id}/version-groups/vg-assistant-1/select",
            json={"node_id": assistant_b.id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session"]["current_leaf_node_id"] == assistant_b.id
        assert data["visible_path"] == ["user-1", "assistant-2"]

    def test_retry_and_edit_routes_create_new_versions(
        self, client: TestClient
    ) -> None:
        store = get_store()
        session = asyncio.run(store.create_session("Mutations"))
        user_node = asyncio.run(
            _seed_node(
                id="user-1",
                session_id=session.id,
                parent_id=None,
                role=MessageRole.HUMAN,
                content="hello",
                status=MessageStatus.COMPLETED,
                version_group_id="vg-user-1",
                version_index=0,
                source_kind=NodeSourceKind.INITIAL,
                created_at=_now(),
                updated_at=_now(),
            )
        )
        assistant_node = asyncio.run(
            _seed_node(
                id="assistant-1",
                session_id=session.id,
                parent_id=user_node.id,
                role=MessageRole.AI,
                content="answer",
                status=MessageStatus.COMPLETED,
                version_group_id="vg-assistant-1",
                version_index=0,
                source_kind=NodeSourceKind.INITIAL,
                response_to_node_id=user_node.id,
                created_at=_now(),
                updated_at=_now(),
            )
        )
        asyncio.run(store.update_current_leaf(session.id, assistant_node.id))

        retry_response = client.post(
            f"/sessions/{session.id}/nodes/{assistant_node.id}/retry"
        )
        assert retry_response.status_code == 200
        retry_data = retry_response.json()
        assert retry_data["messages"][-1]["status"] == "streaming"

        edit_user_response = client.patch(
            f"/sessions/{session.id}/nodes/{user_node.id}/edit",
            json={"content": "edited user"},
        )
        assert edit_user_response.status_code == 200
        edit_user_data = edit_user_response.json()
        assert edit_user_data["messages"][0]["content"] == "edited user"
        assert edit_user_data["messages"][-1]["status"] == "streaming"

        edit_assistant_response = client.patch(
            f"/sessions/{session.id}/nodes/{assistant_node.id}/edit",
            json={"content": "edited assistant"},
        )
        assert edit_assistant_response.status_code == 200
        edit_assistant_data = edit_assistant_response.json()
        assert edit_assistant_data["messages"][-1]["content"] == "edited assistant"
