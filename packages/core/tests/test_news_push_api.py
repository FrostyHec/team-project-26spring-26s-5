"""HTTP integration tests for the campus news push API."""

from fastapi.testclient import TestClient

from agent_core.api.server import create_app
from agent_core.config import AgentConfig


def test_get_news_push_settings_returns_defaults() -> None:
    """The settings endpoint returns the slim default push configuration."""
    app = create_app(AgentConfig(openai_api_key="test-key", db_path=":memory:"))

    with TestClient(app) as client:
        response = client.get("/news/push/settings")

    assert response.status_code == 200
    body = response.json()
    assert body == {"enabled": False, "push_time": "08:30", "limit": 20}


def test_save_news_push_settings_round_trips_payload() -> None:
    """Saving settings persists them for subsequent GET requests."""
    app = create_app(AgentConfig(openai_api_key="test-key", db_path=":memory:"))
    payload = {"enabled": True, "push_time": "09:30", "limit": 10}

    with TestClient(app) as client:
        save_response = client.put("/news/push/settings", json=payload)
        loaded_response = client.get("/news/push/settings")

    assert save_response.status_code == 200
    assert save_response.json() == payload
    assert loaded_response.json() == payload


def test_save_news_push_settings_rejects_invalid_time() -> None:
    """The settings endpoint validates HH:MM push times."""
    app = create_app(AgentConfig(openai_api_key="test-key", db_path=":memory:"))
    payload = {"enabled": True, "push_time": "26:00", "limit": 20}

    with TestClient(app) as client:
        response = client.put("/news/push/settings", json=payload)

    assert response.status_code == 422


def test_news_detail_route_still_works_with_push_routes_registered() -> None:
    """Adding push routes must not shadow the /news/{news_id} detail route."""
    app = create_app(AgentConfig(openai_api_key="test-key", db_path=":memory:"))

    with TestClient(app) as client:
        response = client.get("/news/non-existent-id")

    assert response.status_code == 404
