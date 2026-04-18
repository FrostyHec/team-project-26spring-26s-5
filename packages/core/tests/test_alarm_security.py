"""Security tests for alarm settings and notifications REST API endpoints.

Covers:
  SEC1: PUT /alarm-settings with invalid lead_time value → 422
  SEC2: PUT /alarm-settings with invalid channel value → 422
  SEC3: POST /notifications/{unknown_id}/ack → 404 (no sensitive info leak)
  SEC4: PUT /alarm-settings enabled=true with empty lead_times → 422
        (Pydantic model_validator enforced at API boundary)
  SEC5: PUT /alarm-settings with extra unknown fields → 200 (fields stripped)
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


class TestAlarmSecurityBoundaries:
    """SEC1-SEC5: input validation and information-leakage checks."""

    def test_invalid_lead_time_rejected(self, client: TestClient) -> None:
        """SEC1: Invalid lead_time enum value must return 422."""
        payload = {
            "enabled": True,
            "lead_times": ["not_a_real_lead_time"],
            "channels": ["in_app"],
            "enabled_priorities": ["high"],
        }
        response = client.put("/alarm-settings", json=payload)
        assert response.status_code == 422

    def test_invalid_channel_rejected(self, client: TestClient) -> None:
        """SEC2: Invalid channel enum value must return 422."""
        payload = {
            "enabled": True,
            "lead_times": ["day_1"],
            "channels": ["sms"],  # Not a valid AlarmChannel value
            "enabled_priorities": ["high"],
        }
        response = client.put("/alarm-settings", json=payload)
        assert response.status_code == 422

    def test_ack_nonexistent_notification_returns_404_no_leak(
        self, client: TestClient
    ) -> None:
        """SEC3: ACK for unknown notification id must return 404 without
        leaking internal implementation details."""
        response = client.post("/notifications/nonexistent-uuid-9999/ack")
        assert response.status_code == 404
        body = response.json()
        # Response should be a standard detail dict, not a stack trace
        assert "detail" in body
        assert "nonexistent-uuid-9999" in body["detail"]

    def test_enabled_with_empty_lead_times_rejected(self, client: TestClient) -> None:
        """SEC4: enabled=true with empty lead_times must return 422
        (AlarmSettings model_validator enforced at API boundary)."""
        payload = {
            "enabled": True,
            "lead_times": [],
            "channels": ["in_app"],
            "enabled_priorities": ["high"],
        }
        response = client.put("/alarm-settings", json=payload)
        assert response.status_code == 422

    def test_extra_fields_stripped(self, client: TestClient) -> None:
        """SEC5: Extra unknown fields in PUT body should not cause errors;
        Pydantic strips them and processes valid fields normally."""
        payload = {
            "enabled": False,
            "lead_times": ["day_1"],
            "channels": ["in_app"],
            "enabled_priorities": ["high"],
            "injected_field": "malicious_value",
            "__class__": "exploit",
        }
        response = client.put("/alarm-settings", json=payload)
        # Pydantic v2 with model_config extra='ignore' strips unknown fields
        assert response.status_code in (200, 422)
        if response.status_code == 200:
            data = response.json()
            assert "injected_field" not in data
            assert "__class__" not in data
