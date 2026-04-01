"""Tests for the deadline REST API endpoints."""

import pytest
from fastapi.testclient import TestClient

from agent_core.api.server import create_app
from agent_core.config import AgentConfig
from agent_core.persistence.deadline_store import DeadlineStore
from agent_core.tools.deadline import set_deadline_store


@pytest.fixture
async def deadline_store():
    """Create an in-memory deadline store for testing."""
    store = DeadlineStore(":memory:")
    await store.initialize()
    await set_deadline_store(store)
    try:
        yield store
    finally:
        await store.close()
        await set_deadline_store(None)


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


class TestDeadlineEndpoints:
    """Tests for /deadlines endpoints."""

    @pytest.mark.asyncio
    async def test_list_empty(self, client: TestClient, deadline_store) -> None:
        response = client.get("/deadlines")
        assert response.status_code == 200
        data = response.json()
        assert data["deadlines"] == []

    @pytest.mark.asyncio
    async def test_list_with_data(self, client: TestClient, deadline_store) -> None:
        from agent_core.models.deadline import DeadlineRecord

        await deadline_store.add(
            DeadlineRecord(id="d1", title="HW1", course="CS302", due_date="2026-04-10")
        )
        response = client.get("/deadlines")
        assert response.status_code == 200
        deadlines = response.json()["deadlines"]
        assert len(deadlines) == 1
        assert deadlines[0]["title"] == "HW1"

    @pytest.mark.asyncio
    async def test_list_filter_course(self, client: TestClient, deadline_store) -> None:
        from agent_core.models.deadline import DeadlineRecord

        await deadline_store.add(
            DeadlineRecord(id="a", title="A", course="CS302", due_date="2026-04-10")
        )
        await deadline_store.add(
            DeadlineRecord(id="b", title="B", course="MATH201", due_date="2026-04-12")
        )
        response = client.get("/deadlines?course=CS302")
        deadlines = response.json()["deadlines"]
        assert len(deadlines) == 1
        assert deadlines[0]["course"] == "CS302"

    @pytest.mark.asyncio
    async def test_list_filter_priority(
        self, client: TestClient, deadline_store
    ) -> None:
        from agent_core.models.deadline import DeadlinePriority, DeadlineRecord

        await deadline_store.add(
            DeadlineRecord(
                id="a",
                title="Exam",
                priority=DeadlinePriority.HIGH,
                due_date="2026-04-20",
            )
        )
        await deadline_store.add(
            DeadlineRecord(
                id="b",
                title="HW",
                priority=DeadlinePriority.LOW,
                due_date="2026-04-25",
            )
        )
        response = client.get("/deadlines?priority=high")
        deadlines = response.json()["deadlines"]
        assert len(deadlines) == 1
        assert deadlines[0]["title"] == "Exam"

    @pytest.mark.asyncio
    async def test_list_filter_priority_case_insensitive(
        self, client: TestClient, deadline_store
    ) -> None:
        """Priority filter should be case-insensitive (HIGH == high)."""
        from agent_core.models.deadline import DeadlinePriority, DeadlineRecord

        await deadline_store.add(
            DeadlineRecord(
                id="a",
                title="Exam",
                priority=DeadlinePriority.HIGH,
                due_date="2026-04-20",
            )
        )
        response = client.get("/deadlines?priority=HIGH")
        assert response.status_code == 200
        deadlines = response.json()["deadlines"]
        assert len(deadlines) == 1

    @pytest.mark.asyncio
    async def test_list_filter_priority_invalid_returns_422(
        self, client: TestClient, deadline_store
    ) -> None:
        """Invalid priority value should return 422."""
        response = client.get("/deadlines?priority=urgent")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_delete_existing(self, client: TestClient, deadline_store) -> None:
        from agent_core.models.deadline import DeadlineRecord

        await deadline_store.add(
            DeadlineRecord(id="d1", title="Test", due_date="2026-04-10")
        )
        response = client.delete("/deadlines/d1")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

        # Verify it's gone
        list_response = client.get("/deadlines")
        assert list_response.json()["deadlines"] == []

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, client: TestClient, deadline_store) -> None:
        response = client.delete("/deadlines/nonexistent")
        assert response.status_code == 404
