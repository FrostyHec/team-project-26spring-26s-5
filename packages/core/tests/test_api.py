"""Tests for the FastAPI server endpoints."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from agent_core.api.server import create_app
from agent_core.config import AgentConfig
from agent_core.models.llm_settings import LlmSettingsFile, ProviderSettings


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
        # 4 calculator + 1 weather + 4 widget + 9 deadline
        #   + 7 email + 5 course + 1 policy_search + 4 agent_memory
        assert len(tools) == 35
        names = {t["name"] for t in tools}
        assert "add" in names
        assert "subtract" in names
        assert "multiply" in names
        assert "divide" in names
        assert "get_weather" in names
        assert "show_document" in names
        assert "analyze_document" in names
        assert "read_file" in names
        assert "list_memory_topics" in names
        assert "read_memory_file" in names
        assert "create_memory_file" in names
        assert "update_memory_file" in names


class TestChatEndpointErrors:
    """Test error handling for chat endpoint."""

    def test_chat_returns_503_when_no_provider_is_configured(
        self, tmp_path: Path
    ) -> None:
        """Chat should fail per-request instead of crashing app startup."""
        app = create_app(
            AgentConfig(
                openai_api_key="",
                model_name="gpt-4o-mini",
                db_path=":memory:",
                llm_settings_path=str(tmp_path / "llm_settings.yaml"),
            )
        )

        with TestClient(app) as client:
            response = client.post("/chat", json={"message": "Hello"})

        assert response.status_code == 503
        assert response.json()["detail"] == "No enabled LLM provider configured"

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

    def test_chat_accepts_provider_parameter(self, client: TestClient) -> None:
        """Test that chat endpoint forwards provider selection."""
        mock_agent = MagicMock()
        mock_agent.chat = AsyncMock(return_value="Hello!")
        with patch(
            "agent_core.api.routes.chat.get_agent_for_skill",
            return_value=mock_agent,
        ) as mock_get_agent_for_skill:
            response = client.post(
                "/chat",
                json={"message": "Hello", "provider_id": "primary"},
            )
            assert response.status_code == 200
            mock_get_agent_for_skill.assert_called_once_with(None, "en", "primary")

    def test_chat_rejects_unknown_provider_parameter(self, client: TestClient) -> None:
        """Unknown provider_id should fail fast instead of silently falling back."""
        with patch(
            "agent_core.api.routes.chat.get_agent_for_skill",
            side_effect=ValueError("Unknown provider_id: missing"),
        ):
            response = client.post(
                "/chat",
                json={"message": "Hello", "provider_id": "missing"},
            )
            assert response.status_code == 400
            assert response.json()["detail"] == "Unknown provider_id: missing"

    def test_chat_auto_fallback_tries_next_provider(self, client: TestClient) -> None:
        """Auto fallback should try the next enabled provider by priority."""
        create_resp = client.post("/sessions", json={"title": "Fallback"})
        session_id = create_resp.json()["id"]
        client.patch(
            f"/sessions/{session_id}/preferences",
            json={"selected_provider_id": "primary", "fallback_mode": "auto"},
        )

        primary_agent = MagicMock()
        primary_agent.chat = AsyncMock(side_effect=Exception("primary down"))
        secondary_agent = MagicMock()
        secondary_agent.chat = AsyncMock(return_value="Recovered")

        with (
            patch(
                "agent_core.api.routes.chat.load_llm_settings",
                return_value=LlmSettingsFile(
                    providers=[
                        ProviderSettings(
                            id="primary",
                            name="Primary",
                            priority=0,
                            api_key="key-1",
                            enabled=True,
                        ),
                        ProviderSettings(
                            id="secondary",
                            name="Secondary",
                            priority=1,
                            api_key="key-2",
                            enabled=True,
                        ),
                    ]
                ),
            ),
            patch(
                "agent_core.api.routes.chat.get_agent_for_skill",
                side_effect=[primary_agent, secondary_agent],
            ) as mock_get_agent_for_skill,
        ):
            response = client.post(
                "/chat",
                json={
                    "message": "Hello",
                    "session_id": session_id,
                    "provider_id": "primary",
                },
            )

        assert response.status_code == 200
        assert response.json()["response"] == "Recovered"
        assert mock_get_agent_for_skill.call_args_list[0].args == (
            None,
            "en",
            "primary",
        )
        assert mock_get_agent_for_skill.call_args_list[1].args == (
            None,
            "en",
            "secondary",
        )

    def test_chat_stream_auto_fallback_tries_next_provider(
        self, client: TestClient
    ) -> None:
        """Streaming fallback should switch providers before any content is emitted."""
        create_resp = client.post("/sessions", json={"title": "Fallback Stream"})
        session_id = create_resp.json()["id"]
        client.patch(
            f"/sessions/{session_id}/preferences",
            json={"selected_provider_id": "primary", "fallback_mode": "auto"},
        )

        primary_agent = MagicMock()

        async def _failing_stream(*_args, **_kwargs):
            if False:
                yield {}
            raise Exception("primary down")

        primary_agent.stream_with_history = _failing_stream

        secondary_agent = MagicMock()

        async def _success_stream(*_args, **_kwargs):
            yield {"type": "loop_start"}
            yield {"type": "token", "content": "Recovered"}

        secondary_agent.stream_with_history = _success_stream

        with (
            patch(
                "agent_core.api.routes.chat.load_llm_settings",
                return_value=LlmSettingsFile(
                    providers=[
                        ProviderSettings(
                            id="primary",
                            name="Primary",
                            priority=0,
                            api_key="key-1",
                            enabled=True,
                        ),
                        ProviderSettings(
                            id="secondary",
                            name="Secondary",
                            priority=1,
                            api_key="key-2",
                            enabled=True,
                        ),
                    ]
                ),
            ),
            patch(
                "agent_core.api.routes.chat.get_agent_for_skill",
                side_effect=[primary_agent, secondary_agent],
            ),
        ):
            response = client.post(
                "/chat/stream",
                json={
                    "message": "Hello",
                    "session_id": session_id,
                    "provider_id": "primary",
                },
            )

        assert response.status_code == 200
        assert '"type":"provider_switch"' in response.text.replace(" ", "")
        assert "Recovered" in response.text
        assert "[DONE]" in response.text

    def test_chat_stream_schedules_first_round_title_generation(
        self, client: TestClient
    ) -> None:
        """Successful first-round streams should schedule async title generation."""
        create_resp = client.post("/sessions", json={"title": "Async Title"})
        session_id = create_resp.json()["id"]

        mock_agent = MagicMock()
        mock_agent.llm = object()

        async def _success_stream(*_args, **_kwargs):
            yield {"type": "loop_start"}
            yield {"type": "token", "content": "Answer"}
            yield {"type": "loop_end"}

        mock_agent.stream_with_history = _success_stream

        with (
            patch(
                "agent_core.api.routes.chat.get_agent_for_skill",
                return_value=mock_agent,
            ),
            patch(
                "agent_core.api.routes.chat._schedule_first_round_title_generation"
            ) as mock_schedule,
        ):
            response = client.post(
                "/chat/stream",
                json={
                    "message": "Hello",
                    "session_id": session_id,
                    "provider_id": "primary",
                },
            )

        assert response.status_code == 200
        assert "[DONE]" in response.text
        mock_schedule.assert_called_once()
        scheduled_args = mock_schedule.call_args.args
        assert scheduled_args[1] == session_id
        assert scheduled_args[3] is mock_agent.llm


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
