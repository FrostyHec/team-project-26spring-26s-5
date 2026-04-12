"""Tests for deadline management tools and persistence."""

import json

import pytest

from agent_core.models.deadline import DeadlinePriority, DeadlineRecord, DeadlineSource
from agent_core.persistence.deadline_store import DeadlineStore
from agent_core.tools.deadline import (
    add_deadline,
    get_exams,
    list_deadlines,
    query_email,
    register_deadline_tools,
    save_deadlines,
    set_deadline_store,
    show_deadline_dashboard,
)
from agent_core.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestDeadlineModels:
    """Tests for deadline Pydantic models and enums."""

    def test_priority_enum_values(self) -> None:
        assert DeadlinePriority.HIGH == "high"
        assert DeadlinePriority.MEDIUM == "medium"
        assert DeadlinePriority.LOW == "low"

    def test_source_enum_values(self) -> None:
        assert DeadlineSource.BLACKBOARD == "blackboard"
        assert DeadlineSource.EMAIL == "email"
        assert DeadlineSource.TAS == "tas"
        assert DeadlineSource.MANUAL == "manual"

    def test_record_serialization(self) -> None:
        record = DeadlineRecord(
            id="test-1",
            title="HW1",
            course="CS302",
            due_date="2026-04-15",
            priority=DeadlinePriority.HIGH,
            source=DeadlineSource.BLACKBOARD,
            description="Submit via BB",
        )
        data = record.model_dump()
        assert data["id"] == "test-1"
        assert data["priority"] == "high"
        assert data["source"] == "blackboard"

    def test_record_defaults(self) -> None:
        record = DeadlineRecord(id="x", title="Test")
        assert record.course == ""
        assert record.priority == DeadlinePriority.MEDIUM
        assert record.source == DeadlineSource.MANUAL


# ---------------------------------------------------------------------------
# Store tests
# ---------------------------------------------------------------------------


class TestDeadlineStore:
    """Tests for the SQLite deadline store."""

    @pytest.fixture
    async def store(self):
        s = DeadlineStore(":memory:")
        await s.initialize()
        yield s
        await s.close()

    @pytest.mark.asyncio
    async def test_add_and_list(self, store: DeadlineStore) -> None:
        record = DeadlineRecord(
            id="d1",
            title="Project 1",
            course="CS302",
            due_date="2026-04-15",
            priority=DeadlinePriority.HIGH,
            source=DeadlineSource.BLACKBOARD,
        )
        await store.add(record)
        items = await store.list_all()
        assert len(items) == 1
        assert items[0].title == "Project 1"
        assert items[0].priority == DeadlinePriority.HIGH

    @pytest.mark.asyncio
    async def test_filter_by_course(self, store: DeadlineStore) -> None:
        await store.add(
            DeadlineRecord(id="a", title="HW1", course="CS302", due_date="2026-04-10")
        )
        await store.add(
            DeadlineRecord(id="b", title="HW2", course="MATH201", due_date="2026-04-12")
        )
        results = await store.list_all(course="CS302")
        assert len(results) == 1
        assert results[0].course == "CS302"

    @pytest.mark.asyncio
    async def test_filter_by_priority(self, store: DeadlineStore) -> None:
        await store.add(
            DeadlineRecord(
                id="a",
                title="Exam",
                priority=DeadlinePriority.HIGH,
                due_date="2026-04-20",
            )
        )
        await store.add(
            DeadlineRecord(
                id="b", title="HW", priority=DeadlinePriority.LOW, due_date="2026-04-25"
            )
        )
        results = await store.list_all(priority="high")
        assert len(results) == 1
        assert results[0].title == "Exam"

    @pytest.mark.asyncio
    async def test_get_by_id(self, store: DeadlineStore) -> None:
        await store.add(DeadlineRecord(id="d1", title="Test", due_date="2026-04-10"))
        item = await store.get("d1")
        assert item is not None
        assert item.title == "Test"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, store: DeadlineStore) -> None:
        item = await store.get("nonexistent")
        assert item is None

    @pytest.mark.asyncio
    async def test_delete(self, store: DeadlineStore) -> None:
        await store.add(DeadlineRecord(id="d1", title="Test", due_date="2026-04-10"))
        deleted = await store.delete("d1")
        assert deleted is True
        items = await store.list_all()
        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, store: DeadlineStore) -> None:
        deleted = await store.delete("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_list_ordered_by_due_date(self, store: DeadlineStore) -> None:
        await store.add(DeadlineRecord(id="a", title="Later", due_date="2026-05-01"))
        await store.add(DeadlineRecord(id="b", title="Earlier", due_date="2026-04-01"))
        items = await store.list_all()
        assert items[0].title == "Earlier"
        assert items[1].title == "Later"


# ---------------------------------------------------------------------------
# Tool function tests
# ---------------------------------------------------------------------------


class TestMockDataTools:
    """Tests for mock external data source tools."""

    def test_query_email_returns_json(self) -> None:
        result = json.loads(query_email())
        assert isinstance(result, list)
        assert len(result) > 0
        assert "subject" in result[0]

    def test_get_exams_returns_json(self) -> None:
        result = json.loads(get_exams())
        assert isinstance(result, list)
        assert len(result) > 0
        assert "course" in result[0]
        assert "date" in result[0]


class TestDeadlineTools:
    """Tests for deadline CRUD tool functions."""

    @pytest.fixture(autouse=True)
    async def _setup_store(self):
        store = DeadlineStore(":memory:")
        await store.initialize()
        await set_deadline_store(store)
        try:
            yield
        finally:
            await store.close()
            await set_deadline_store(None)

    @pytest.mark.asyncio
    async def test_save_deadlines(self) -> None:
        data = json.dumps(
            [
                {
                    "title": "Project 1",
                    "due_date": "2026-04-15",
                    "course": "CS302",
                    "priority": "high",
                    "source": "blackboard",
                }
            ]
        )
        result = json.loads(await save_deadlines(data))
        assert result["status"] == "success"
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_save_deadlines_invalid_json(self) -> None:
        result = json.loads(await save_deadlines("not json"))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_save_deadlines_invalid_priority_defaults_to_medium(self) -> None:
        """Non-enum priority value should be silently coerced to 'medium'."""
        data = json.dumps(
            [{"title": "HW", "due_date": "2026-04-10", "priority": "URGENT"}]
        )
        result = json.loads(await save_deadlines(data))
        assert result["status"] == "success"
        assert result["count"] == 1
        assert result["deadlines"][0]["priority"] == "medium"

    @pytest.mark.asyncio
    async def test_save_deadlines_non_dict_item_skipped(self) -> None:
        """Non-dict items (e.g. bare string) should be skipped, not crash."""
        data = json.dumps(["not-a-dict", {"title": "Valid", "due_date": "2026-04-10"}])
        result = json.loads(await save_deadlines(data))
        assert result["status"] == "success"
        assert result["count"] == 1
        assert len(result.get("skipped", [])) == 1

    @pytest.mark.asyncio
    async def test_list_deadlines_empty(self) -> None:
        result = json.loads(await list_deadlines())
        assert result == []

    @pytest.mark.asyncio
    async def test_list_deadlines_with_data(self) -> None:
        await save_deadlines(
            json.dumps([{"title": "HW1", "due_date": "2026-04-10", "course": "CS302"}])
        )
        result = json.loads(await list_deadlines())
        assert len(result) == 1
        assert result[0]["title"] == "HW1"

    @pytest.mark.asyncio
    async def test_list_deadlines_filter_course(self) -> None:
        await save_deadlines(
            json.dumps(
                [
                    {"title": "HW1", "due_date": "2026-04-10", "course": "CS302"},
                    {"title": "HW2", "due_date": "2026-04-12", "course": "MATH201"},
                ]
            )
        )
        result = json.loads(await list_deadlines(course="CS302"))
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_deadlines_filter_priority(self) -> None:
        await save_deadlines(
            json.dumps(
                [
                    {"title": "Exam", "due_date": "2026-04-20", "priority": "high"},
                    {"title": "HW", "due_date": "2026-04-25", "priority": "low"},
                ]
            )
        )
        result = json.loads(await list_deadlines(priority="high"))
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_add_deadline(self) -> None:
        result = json.loads(
            await add_deadline(
                title="Physics Quiz",
                course="PHYS101",
                due_date="2026-04-08",
                priority="high",
            )
        )
        assert result["title"] == "Physics Quiz"
        assert result["priority"] == "high"
        assert result["source"] == "manual"

        # Verify it's in the store
        all_items = json.loads(await list_deadlines())
        assert len(all_items) == 1

    @pytest.mark.asyncio
    async def test_show_deadline_dashboard_empty(self) -> None:
        result = json.loads(await show_deadline_dashboard())
        assert result["widget_type"] == "calendar"
        assert result["events"] == []

    @pytest.mark.asyncio
    async def test_show_deadline_dashboard_with_data(self) -> None:
        await add_deadline(title="HW1", course="CS302", due_date="2026-04-15")
        result = json.loads(await show_deadline_dashboard())
        assert result["widget_type"] == "calendar"
        assert len(result["events"]) == 1
        assert result["events"][0]["title"] == "HW1"


class TestRegisterDeadlineTools:
    """Tests for tool registration."""

    def test_registers_all_tools(self) -> None:
        registry = ToolRegistry()
        register_deadline_tools(registry)
        tool_names = {t.name for t in registry.list_tools()}
        expected = {
            "get_announcements",
            "query_email",
            "get_exams",
            "save_deadlines",
            "list_deadlines",
            "add_deadline",
            "show_deadline_dashboard",
        }
        assert expected == tool_names

    def test_save_deadlines_is_sensitive(self) -> None:
        registry = ToolRegistry()
        register_deadline_tools(registry)
        assert registry.is_sensitive("save_deadlines") is True

    def test_other_tools_are_safe(self) -> None:
        registry = ToolRegistry()
        register_deadline_tools(registry)
        safe_tools = [
            "get_announcements",
            "query_email",
            "get_exams",
            "list_deadlines",
            "add_deadline",
            "show_deadline_dashboard",
        ]
        for name in safe_tools:
            assert registry.is_sensitive(name) is False, f"{name} should be safe"
