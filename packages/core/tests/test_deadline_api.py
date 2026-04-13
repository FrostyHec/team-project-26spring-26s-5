"""Tests for the deadline REST API endpoints."""

from datetime import datetime

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
            DeadlineRecord(
                id="d1",
                title="HW1",
                course="CS302",
                due_date=datetime(2026, 4, 10),
            )
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
            DeadlineRecord(
                id="a",
                title="A",
                course="CS302",
                due_date=datetime(2026, 4, 10),
            )
        )
        await deadline_store.add(
            DeadlineRecord(
                id="b",
                title="B",
                course="MATH201",
                due_date=datetime(2026, 4, 12),
            )
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
                due_date=datetime(2026, 4, 20),
            )
        )
        await deadline_store.add(
            DeadlineRecord(
                id="b",
                title="HW",
                priority=DeadlinePriority.LOW,
                due_date=datetime(2026, 4, 25),
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
                due_date=datetime(2026, 4, 20),
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
            DeadlineRecord(id="d1", title="Test", due_date=datetime(2026, 4, 10))
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

    # ------------------------------------------------------------------
    # A006: New fields in list response
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_list_includes_new_fields(
        self, client: TestClient, deadline_store
    ) -> None:
        """GET /deadlines should return date_type, start_date, completed."""
        from agent_core.models.deadline import DateType, DeadlineRecord

        await deadline_store.add(
            DeadlineRecord(
                id="p1",
                title="Sprint",
                date_type=DateType.PERIOD_DAY,
                start_date=datetime(2026, 4, 1),
                due_date=datetime(2026, 4, 15),
            )
        )
        response = client.get("/deadlines")
        d = response.json()["deadlines"][0]
        assert d["date_type"] == "period_day"
        assert d["start_date"] == "2026-04-01T00:00:00"
        assert d["completed"] is False

    # ------------------------------------------------------------------
    # A006: Toggle complete endpoint
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_toggle_complete(self, client: TestClient, deadline_store) -> None:
        from agent_core.models.deadline import DeadlineRecord

        await deadline_store.add(
            DeadlineRecord(id="d1", title="Test", due_date=datetime(2026, 4, 10))
        )
        response = client.patch(
            "/deadlines/d1/complete",
            json={"completed": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "d1"
        assert data["completed"] is True

    @pytest.mark.asyncio
    async def test_toggle_complete_nonexistent(
        self, client: TestClient, deadline_store
    ) -> None:
        response = client.patch(
            "/deadlines/nonexistent/complete",
            json={"completed": True},
        )
        assert response.status_code == 404

    # ------------------------------------------------------------------
    # A006: Sync preview endpoint
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sync_preview_new_and_duplicate(
        self, client: TestClient, deadline_store
    ) -> None:
        from agent_core.models.deadline import DeadlineRecord

        # Existing record in store
        await deadline_store.add(
            DeadlineRecord(id="e1", title="HW1", due_date=datetime(2026, 4, 15))
        )
        # Candidates: one duplicate, one new
        candidates = [
            {"title": "HW1", "due_date": "2026-04-15", "course": ""},
            {"title": "HW2", "due_date": "2026-04-20", "course": ""},
        ]
        response = client.post(
            "/deadlines/sync-preview",
            json={"deadlines": candidates},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["new_tasks"]) == 1
        assert data["new_tasks"][0]["title"] == "HW2"
        assert len(data["duplicate_tasks"]) == 1
        assert data["duplicate_tasks"][0]["existing_id"] == "e1"

    @pytest.mark.asyncio
    async def test_sync_preview_all_new(
        self, client: TestClient, deadline_store
    ) -> None:
        candidates = [
            {"title": "Task A", "due_date": "2026-04-20", "course": ""},
        ]
        response = client.post(
            "/deadlines/sync-preview",
            json={"deadlines": candidates},
        )
        data = response.json()
        assert len(data["new_tasks"]) == 1
        assert len(data["duplicate_tasks"]) == 0

    # ------------------------------------------------------------------
    # A006: Sync commit endpoint
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sync_commit(self, client: TestClient, deadline_store) -> None:
        tasks = [
            {"title": "New Task 1", "due_date": "2026-04-25", "course": "CS302"},
            {"title": "New Task 2", "due_date": "2026-04-26", "course": ""},
        ]
        response = client.post(
            "/deadlines/sync-commit",
            json={"tasks": tasks},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["added"]) == 2
        # Verify they're persisted
        all_items = await deadline_store.list_all()
        assert len(all_items) == 2

    # ------------------------------------------------------------------
    # A007: Update deadline endpoint
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_single_field(
        self, client: TestClient, deadline_store
    ) -> None:
        from agent_core.models.deadline import DeadlineRecord

        await deadline_store.add(
            DeadlineRecord(id="d1", title="Old Title", due_date=datetime(2026, 4, 10))
        )
        response = client.patch("/deadlines/d1", json={"title": "New Title"})
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "New Title"
        assert data["due_date"] == "2026-04-10T00:00:00"  # unchanged

    @pytest.mark.asyncio
    async def test_update_multiple_fields(
        self, client: TestClient, deadline_store
    ) -> None:
        from agent_core.models.deadline import DeadlineRecord

        await deadline_store.add(
            DeadlineRecord(
                id="d1",
                title="Test",
                course="CS302",
                due_date=datetime(2026, 4, 10),
            )
        )
        response = client.patch(
            "/deadlines/d1",
            json={"title": "Updated", "course": "MATH201", "priority": "high"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated"
        assert data["course"] == "MATH201"
        assert data["priority"] == "high"

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_404(
        self, client: TestClient, deadline_store
    ) -> None:
        response = client.patch("/deadlines/nonexistent", json={"title": "X"})
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_invalid_priority_returns_422(
        self, client: TestClient, deadline_store
    ) -> None:
        from agent_core.models.deadline import DeadlineRecord

        await deadline_store.add(
            DeadlineRecord(id="d1", title="Test", due_date=datetime(2026, 4, 10))
        )
        response = client.patch("/deadlines/d1", json={"priority": "urgent"})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_invalid_date_type_returns_422(
        self, client: TestClient, deadline_store
    ) -> None:
        from agent_core.models.deadline import DeadlineRecord

        await deadline_store.add(
            DeadlineRecord(id="d1", title="Test", due_date=datetime(2026, 4, 10))
        )
        response = client.patch("/deadlines/d1", json={"date_type": "invalid"})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_date_type_valid(
        self, client: TestClient, deadline_store
    ) -> None:
        from agent_core.models.deadline import DeadlineRecord

        await deadline_store.add(
            DeadlineRecord(id="d1", title="Test", due_date=datetime(2026, 4, 10))
        )
        response = client.patch(
            "/deadlines/d1", json={"date_type": "no_date", "due_date": None}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["date_type"] == "no_date"
        assert data["due_date"] is None

    # ------------------------------------------------------------------
    # A008: Create deadline endpoint
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_deadline(self, client: TestClient, deadline_store) -> None:
        response = client.post(
            "/deadlines",
            json={"title": "New Task", "due_date": "2026-05-01"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "New Task"
        assert data["due_date"] == "2026-05-01T00:00:00"
        assert data["priority"] == "medium"
        assert data["source"] == "manual"
        assert data["id"]  # UUID was generated

    @pytest.mark.asyncio
    async def test_create_deadline_with_all_fields(
        self, client: TestClient, deadline_store
    ) -> None:
        response = client.post(
            "/deadlines",
            json={
                "title": "Full Task",
                "course": "CS302",
                "due_date": "2026-05-10",
                "priority": "high",
                "description": "Important",
                "date_type": "period_day",
                "start_date": "2026-05-01",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Full Task"
        assert data["course"] == "CS302"
        assert data["priority"] == "high"
        assert data["date_type"] == "period_day"
        assert data["start_date"] == "2026-05-01T00:00:00"

    @pytest.mark.asyncio
    async def test_create_deadline_invalid_priority(
        self, client: TestClient, deadline_store
    ) -> None:
        response = client.post(
            "/deadlines",
            json={"title": "Bad", "priority": "urgent"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_deadline_invalid_date_type(
        self, client: TestClient, deadline_store
    ) -> None:
        response = client.post(
            "/deadlines",
            json={"title": "Bad", "date_type": "bogus"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_deadline_date_range_violation(
        self, client: TestClient, deadline_store
    ) -> None:
        response = client.post(
            "/deadlines",
            json={
                "title": "Bad Range",
                "due_date": "2026-04-10",
                "start_date": "2026-04-15",
                "date_type": "period_day",
            },
        )
        assert response.status_code == 422
        assert "start_date" in response.json()["detail"]

    # ------------------------------------------------------------------
    # A008: Date range validation in PATCH
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_date_range_violation(
        self, client: TestClient, deadline_store
    ) -> None:
        from agent_core.models.deadline import DeadlineRecord

        await deadline_store.add(
            DeadlineRecord(
                id="d1",
                title="Period Task",
                due_date=datetime(2026, 4, 15),
                start_date=datetime(2026, 4, 10),
                date_type="period_day",
            )
        )
        # Set start_date after existing due_date
        response = client.patch(
            "/deadlines/d1",
            json={"start_date": "2026-04-20"},
        )
        assert response.status_code == 422
        assert "start_date" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_date_range_valid(
        self, client: TestClient, deadline_store
    ) -> None:
        from agent_core.models.deadline import DeadlineRecord

        await deadline_store.add(
            DeadlineRecord(
                id="d1",
                title="Period Task",
                due_date=datetime(2026, 4, 15),
                start_date=datetime(2026, 4, 10),
                date_type="period_day",
            )
        )
        response = client.patch(
            "/deadlines/d1",
            json={"start_date": "2026-04-12"},
        )
        assert response.status_code == 200
        assert response.json()["start_date"] == "2026-04-12T00:00:00"

    @pytest.mark.asyncio
    async def test_update_due_date_before_existing_start(
        self, client: TestClient, deadline_store
    ) -> None:
        from agent_core.models.deadline import DeadlineRecord

        await deadline_store.add(
            DeadlineRecord(
                id="d1",
                title="Period Task",
                due_date=datetime(2026, 4, 15),
                start_date=datetime(2026, 4, 10),
                date_type="period_day",
            )
        )
        # Move due_date before existing start_date
        response = client.patch(
            "/deadlines/d1",
            json={"due_date": "2026-04-08"},
        )
        assert response.status_code == 422

    # ------------------------------------------------------------------
    # A008: ISO date format validation
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_deadline_invalid_iso_due_date(
        self, client: TestClient, deadline_store
    ) -> None:
        response = client.post(
            "/deadlines",
            json={"title": "Bad Date", "due_date": "04/15/2026"},
        )
        assert response.status_code == 422
        assert "due_date" in str(response.json()["detail"])

    @pytest.mark.asyncio
    async def test_create_deadline_invalid_iso_start_date(
        self, client: TestClient, deadline_store
    ) -> None:
        response = client.post(
            "/deadlines",
            json={
                "title": "Bad Start",
                "due_date": "2026-04-15",
                "start_date": "not-a-date",
                "date_type": "period_day",
            },
        )
        assert response.status_code == 422
        assert "start_date" in str(response.json()["detail"])

    @pytest.mark.asyncio
    async def test_create_deadline_empty_dates_ok(
        self, client: TestClient, deadline_store
    ) -> None:
        response = client.post(
            "/deadlines",
            json={"title": "No Dates"},
        )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_update_invalid_iso_due_date(
        self, client: TestClient, deadline_store
    ) -> None:
        from agent_core.models.deadline import DeadlineRecord

        await deadline_store.add(
            DeadlineRecord(id="d1", title="Task", due_date=datetime(2026, 4, 15))
        )
        response = client.patch(
            "/deadlines/d1",
            json={"due_date": "15-04-2026"},
        )
        assert response.status_code == 422
        assert "due_date" in str(response.json()["detail"])

    @pytest.mark.asyncio
    async def test_update_invalid_iso_start_date(
        self, client: TestClient, deadline_store
    ) -> None:
        from agent_core.models.deadline import DeadlineRecord

        await deadline_store.add(
            DeadlineRecord(id="d1", title="Task", due_date=datetime(2026, 4, 15))
        )
        response = client.patch(
            "/deadlines/d1",
            json={"start_date": "April 10"},
        )
        assert response.status_code == 422
        assert "start_date" in str(response.json()["detail"])
