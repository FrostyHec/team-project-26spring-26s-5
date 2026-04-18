"""Tests for alarm settings and notifications REST API endpoints.

Covers:
  API1: GET /alarm-settings returns defaults
  API2: PUT /alarm-settings persists and returns saved settings
  API3: PUT /alarm-settings with enabled=true and empty lists → 422
  API4: GET /notifications/pending returns empty list initially
  API5: POST /notifications/{unknown_id}/ack → 404
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agent_core.api.server import create_app
from agent_core.config import AgentConfig


@pytest.fixture
def client() -> TestClient:
    """TestClient backed by an in-memory app."""
    config = AgentConfig(
        openai_api_key="test-key",
        model_name="gpt-4o-mini",
        db_path=":memory:",
    )
    app = create_app(config)
    with TestClient(app) as c:
        yield c


class TestAlarmSettingsEndpoints:
    """API1-API3: /alarm-settings."""

    def test_get_returns_defaults(self, client: TestClient) -> None:
        """API1: GET /alarm-settings returns AlarmSettings defaults."""
        response = client.get("/alarm-settings")
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert "day_1" in data["lead_times"]
        assert "in_app" in data["channels"]

    def test_put_persists_settings(self, client: TestClient) -> None:
        """API2: PUT /alarm-settings saves and returns the new settings."""
        payload = {
            "enabled": False,
            "lead_times": ["week_1"],
            "channels": ["email"],
            "enabled_priorities": ["high"],
        }
        response = client.put("/alarm-settings", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["lead_times"] == ["week_1"]

        # Verify persistence via GET
        get_response = client.get("/alarm-settings")
        assert get_response.json()["enabled"] is False

    def test_put_invalid_empty_lead_times_when_enabled(
        self, client: TestClient
    ) -> None:
        """API3: enabled=true with empty lead_times → 422."""
        payload = {
            "enabled": True,
            "lead_times": [],
            "channels": ["in_app"],
            "enabled_priorities": ["high"],
        }
        response = client.put("/alarm-settings", json=payload)
        assert response.status_code == 422

    def test_put_reenabling_creates_no_duplicate_notification(
        self, client: TestClient
    ) -> None:
        """API6: re-enabling alarm (disabled→enabled) runs immediate check.

        With no deadlines stored, the immediate check_and_dispatch should
        produce no notifications but must not raise.
        """
        # Disable first
        client.put(
            "/alarm-settings",
            json={
                "enabled": False,
                "lead_times": ["day_1"],
                "channels": ["in_app"],
                "enabled_priorities": ["high"],
            },
        )
        # Re-enable — triggers immediate check_and_dispatch internally
        response = client.put(
            "/alarm-settings",
            json={
                "enabled": True,
                "lead_times": ["day_1"],
                "channels": ["in_app"],
                "enabled_priorities": ["high"],
            },
        )
        assert response.status_code == 200
        assert response.json()["enabled"] is True
        # No deadlines → no notifications created
        pending = client.get("/notifications/pending")
        assert pending.status_code == 200
        assert pending.json() == []


class TestNotificationEndpoints:
    """API4-API5: /notifications."""

    def test_get_pending_empty(self, client: TestClient) -> None:
        """API4: GET /notifications/pending returns empty list initially."""
        response = client.get("/notifications/pending")
        assert response.status_code == 200
        assert response.json() == []

    def test_ack_unknown_id_returns_404(self, client: TestClient) -> None:
        """API5: POST /notifications/{id}/ack with unknown id → 404."""
        response = client.post("/notifications/nonexistent-uuid/ack")
        assert response.status_code == 404
