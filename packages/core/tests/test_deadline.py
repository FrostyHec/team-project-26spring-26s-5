"""Tests for deadline management tools and persistence."""

import json
from datetime import date, datetime

import pytest

from agent_core.models.deadline import (
    DateType,
    DeadlinePriority,
    DeadlineRecord,
    DeadlineSource,
    parse_date_field,
)
from agent_core.persistence.deadline_store import DeadlineStore
from agent_core.tools.deadline import (
    _sanitise_date_fields,
    add_deadline,
    delete_deadline,
    get_announcements,
    get_exams,
    list_deadlines,
    query_email,
    register_deadline_tools,
    save_deadlines,
    set_deadline_store,
    show_deadline_dashboard,
    update_deadline,
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
            due_date=datetime(2026, 4, 15),
            priority=DeadlinePriority.HIGH,
            source=DeadlineSource.BLACKBOARD,
            description="Submit via BB",
        )
        data = record.model_dump(mode="json")
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
            due_date=datetime(2026, 4, 15),
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
            DeadlineRecord(
                id="a",
                title="HW1",
                course="CS302",
                due_date=datetime(2026, 4, 10),
            )
        )
        await store.add(
            DeadlineRecord(
                id="b",
                title="HW2",
                course="MATH201",
                due_date=datetime(2026, 4, 12),
            )
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
                due_date=datetime(2026, 4, 20),
            )
        )
        await store.add(
            DeadlineRecord(
                id="b",
                title="HW",
                priority=DeadlinePriority.LOW,
                due_date=datetime(2026, 4, 25),
            )
        )
        results = await store.list_all(priority=DeadlinePriority.HIGH)
        assert len(results) == 1
        assert results[0].title == "Exam"

    @pytest.mark.asyncio
    async def test_get_by_id(self, store: DeadlineStore) -> None:
        await store.add(
            DeadlineRecord(
                id="d1",
                title="Test",
                due_date=datetime(2026, 4, 10),
            )
        )
        item = await store.get("d1")
        assert item is not None
        assert item.title == "Test"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, store: DeadlineStore) -> None:
        item = await store.get("nonexistent")
        assert item is None

    @pytest.mark.asyncio
    async def test_delete(self, store: DeadlineStore) -> None:
        await store.add(
            DeadlineRecord(
                id="d1",
                title="Test",
                due_date=datetime(2026, 4, 10),
            )
        )
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
        await store.add(
            DeadlineRecord(
                id="a",
                title="Later",
                due_date=datetime(2026, 5, 1),
            )
        )
        await store.add(
            DeadlineRecord(
                id="b",
                title="Earlier",
                due_date=datetime(2026, 4, 1),
            )
        )
        items = await store.list_all()
        assert items[0].title == "Earlier"
        assert items[1].title == "Later"


# ---------------------------------------------------------------------------
# Tool function tests
# ---------------------------------------------------------------------------


class TestMockDataTools:
    """Tests for mock external data source tools."""

    def test_get_announcements_returns_json(self) -> None:
        result = json.loads(get_announcements())
        assert isinstance(result, list)
        assert len(result) > 0
        assert "course" in result[0]
        assert "title" in result[0]

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
            "delete_deadline",
            "update_deadline",
        }
        assert expected == tool_names

    def test_save_deadlines_is_sensitive(self) -> None:
        registry = ToolRegistry()
        register_deadline_tools(registry)
        assert registry.is_sensitive("save_deadlines") is True

    def test_delete_deadline_is_sensitive(self) -> None:
        registry = ToolRegistry()
        register_deadline_tools(registry)
        assert registry.is_sensitive("delete_deadline") is True

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
            "update_deadline",
        ]
        for name in safe_tools:
            assert registry.is_sensitive(name) is False, f"{name} should be safe"


# ---------------------------------------------------------------------------
# A006: DateType enum and new model fields
# ---------------------------------------------------------------------------


class TestDateType:
    """Tests for the DateType enum values."""

    def test_date_type_enum_values(self) -> None:
        assert DateType.NO_DATE == "no_date"
        assert DateType.MOMENT_DAY == "moment_day"
        assert DateType.MOMENT_HM == "moment_hm"
        assert DateType.PERIOD_DAY == "period_day"
        assert DateType.PERIOD_HM == "period_hm"

    def test_record_new_fields_defaults(self) -> None:
        record = DeadlineRecord(id="x", title="Test")
        assert record.date_type == DateType.MOMENT_DAY
        assert record.start_date is None
        assert record.completed is False

    def test_record_new_fields_serialization(self) -> None:
        record = DeadlineRecord(
            id="t1",
            title="Sprint",
            date_type=DateType.PERIOD_DAY,
            start_date=datetime(2026, 4, 1),
            due_date=datetime(2026, 4, 15),
            completed=True,
        )
        data = record.model_dump(mode="json")
        assert data["date_type"] == "period_day"
        assert data["start_date"] == "2026-04-01T00:00:00"
        assert data["completed"] is True


# ---------------------------------------------------------------------------
# A006: Store new methods — toggle_completed, find_duplicate, is_connected
# ---------------------------------------------------------------------------


class TestDeadlineStoreA006:
    """Tests for new store methods added in A006."""

    @pytest.fixture
    async def store(self):
        s = DeadlineStore(":memory:")
        await s.initialize()
        yield s
        await s.close()

    @pytest.mark.asyncio
    async def test_is_connected_after_init(self, store: DeadlineStore) -> None:
        assert store.is_connected is True

    @pytest.mark.asyncio
    async def test_is_connected_after_close(self) -> None:
        s = DeadlineStore(":memory:")
        await s.initialize()
        assert s.is_connected is True
        await s.close()
        assert s.is_connected is False

    @pytest.mark.asyncio
    async def test_add_with_new_fields(self, store: DeadlineStore) -> None:
        record = DeadlineRecord(
            id="p1",
            title="Sprint 1",
            date_type=DateType.PERIOD_DAY,
            start_date=datetime(2026, 4, 1),
            due_date=datetime(2026, 4, 15),
            completed=False,
        )
        saved = await store.add(record)
        assert saved.date_type == DateType.PERIOD_DAY
        assert saved.start_date == datetime(2026, 4, 1)

        items = await store.list_all()
        assert len(items) == 1
        assert items[0].date_type == DateType.PERIOD_DAY
        assert items[0].start_date == datetime(2026, 4, 1)
        assert items[0].completed is False

    @pytest.mark.asyncio
    async def test_toggle_completed(self, store: DeadlineStore) -> None:
        await store.add(
            DeadlineRecord(
                id="d1",
                title="Test",
                due_date=datetime(2026, 4, 10),
            )
        )
        updated = await store.toggle_completed("d1", True)
        assert updated is not None
        assert updated.completed is True

        # Verify persistence
        item = await store.get("d1")
        assert item is not None
        assert item.completed is True

    @pytest.mark.asyncio
    async def test_toggle_completed_nonexistent(self, store: DeadlineStore) -> None:
        result = await store.toggle_completed("nonexistent", True)
        assert result is None

    @pytest.mark.asyncio
    async def test_toggle_completed_back_to_false(self, store: DeadlineStore) -> None:
        await store.add(
            DeadlineRecord(
                id="d1",
                title="Test",
                due_date=datetime(2026, 4, 10),
            )
        )
        await store.toggle_completed("d1", True)
        updated = await store.toggle_completed("d1", False)
        assert updated is not None
        assert updated.completed is False

    @pytest.mark.asyncio
    async def test_find_duplicate_match(self, store: DeadlineStore) -> None:
        await store.add(
            DeadlineRecord(
                id="d1",
                title="HW1",
                due_date=datetime(2026, 4, 15),
            )
        )
        dup = await store.find_duplicate("HW1", datetime(2026, 4, 15))
        assert dup is not None
        assert dup.id == "d1"

    @pytest.mark.asyncio
    async def test_find_duplicate_case_insensitive(self, store: DeadlineStore) -> None:
        await store.add(
            DeadlineRecord(
                id="d1",
                title="Homework One",
                due_date=datetime(2026, 4, 15),
            )
        )
        dup = await store.find_duplicate("homework one", datetime(2026, 4, 15))
        assert dup is not None
        assert dup.id == "d1"

    @pytest.mark.asyncio
    async def test_find_duplicate_no_match(self, store: DeadlineStore) -> None:
        await store.add(
            DeadlineRecord(
                id="d1",
                title="HW1",
                due_date=datetime(2026, 4, 15),
            )
        )
        dup = await store.find_duplicate("HW2", datetime(2026, 4, 15))
        assert dup is None

    @pytest.mark.asyncio
    async def test_find_duplicate_different_date(self, store: DeadlineStore) -> None:
        await store.add(
            DeadlineRecord(
                id="d1",
                title="HW1",
                due_date=datetime(2026, 4, 15),
            )
        )
        dup = await store.find_duplicate("HW1", datetime(2026, 4, 16))
        assert dup is None

    @pytest.mark.asyncio
    async def test_schema_migration_idempotent(self) -> None:
        """Calling initialize twice should not fail (migration is idempotent)."""
        s = DeadlineStore(":memory:")
        await s.initialize()
        await s.initialize()  # Second call must not raise
        await s.add(DeadlineRecord(id="d1", title="Test", date_type=DateType.NO_DATE))
        items = await s.list_all()
        assert len(items) == 1
        assert items[0].date_type == DateType.NO_DATE
        await s.close()


# ---------------------------------------------------------------------------
# A006: Tool functions with new fields
# ---------------------------------------------------------------------------


class TestToolsA006:
    """Tests for tool functions with new A006 fields."""

    @pytest.fixture(autouse=True)
    async def _reset_store(self):
        store = DeadlineStore(":memory:")
        await store.initialize()
        await set_deadline_store(store)
        yield
        await store.close()
        await set_deadline_store(None)

    @pytest.mark.asyncio
    async def test_save_deadlines_with_date_type(self) -> None:
        items = json.dumps(
            [
                {
                    "title": "Sprint 1",
                    "due_date": "2026-04-15",
                    "date_type": "period_day",
                    "start_date": "2026-04-01",
                }
            ]
        )
        result = json.loads(await save_deadlines(items))
        assert result["count"] == 1
        assert result["deadlines"][0]["date_type"] == "period_day"
        assert result["deadlines"][0]["start_date"] == "2026-04-01T00:00:00"

    @pytest.mark.asyncio
    async def test_save_deadlines_invalid_date_type_defaults(self) -> None:
        items = json.dumps(
            [
                {
                    "title": "Test",
                    "due_date": "2026-04-15",
                    "date_type": "invalid_type",
                }
            ]
        )
        result = json.loads(await save_deadlines(items))
        assert result["count"] == 1
        assert result["deadlines"][0]["date_type"] == "moment_day"

    @pytest.mark.asyncio
    async def test_add_deadline_with_date_type(self) -> None:
        result = json.loads(
            await add_deadline(
                title="No-date task",
                date_type="no_date",
            )
        )
        assert result["date_type"] == "no_date"
        assert result["start_date"] is None

    @pytest.mark.asyncio
    async def test_add_deadline_with_period(self) -> None:
        result = json.loads(
            await add_deadline(
                title="Code Review",
                due_date="2026-04-20",
                date_type="period_hm",
                start_date="2026-04-18T09:00:00",
            )
        )
        assert result["date_type"] == "period_hm"
        assert result["start_date"] == "2026-04-18T09:00:00"

    @pytest.mark.asyncio
    async def test_add_deadline_invalid_date_type_defaults(self) -> None:
        # A007: with date validation, empty due_date forces date_type to no_date
        result = json.loads(await add_deadline(title="Test", date_type="bogus"))
        assert result["date_type"] == "no_date"

    @pytest.mark.asyncio
    async def test_add_deadline_invalid_priority_defaults(self) -> None:
        result = json.loads(await add_deadline(title="Test", priority="urgent"))
        assert result["priority"] == "medium"


# ---------------------------------------------------------------------------
# A007: Date validation helpers
# ---------------------------------------------------------------------------


class TestDateValidation:
    """Tests for parse_date_field and _sanitise_date_fields (A007/A010C)."""

    def test_valid_date_only(self) -> None:
        assert parse_date_field("2026-04-15") == date(2026, 4, 15)

    def test_valid_datetime_hm(self) -> None:
        assert parse_date_field("2026-04-15T14:30") == date(2026, 4, 15)

    def test_valid_datetime_hms(self) -> None:
        assert parse_date_field("2026-04-15T14:30:00") == date(2026, 4, 15)

    def test_invalid_natural_language(self) -> None:
        assert parse_date_field("undecided") is None

    def test_invalid_tbd(self) -> None:
        assert parse_date_field("TBD") is None

    def test_invalid_next_week(self) -> None:
        assert parse_date_field("next week") is None

    def test_empty_string_is_none(self) -> None:
        assert parse_date_field("") is None

    def test_none_is_none(self) -> None:
        assert parse_date_field(None) is None

    def test_date_passthrough(self) -> None:
        d = date(2026, 4, 15)
        assert parse_date_field(d) == d

    def test_sanitise_downgrades_when_no_due(self) -> None:
        due, start, dt, warnings = _sanitise_date_fields(
            None,
            None,
            DateType.MOMENT_DAY,
        )
        assert due is None
        assert dt == DateType.NO_DATE
        assert len(warnings) >= 1

    def test_sanitise_no_op_for_valid_dates(self) -> None:
        due, start, dt, warnings = _sanitise_date_fields(
            datetime(2026, 4, 15),
            datetime(2026, 4, 1),
            DateType.PERIOD_DAY,
        )
        assert due == datetime(2026, 4, 15)
        assert start == datetime(2026, 4, 1)
        assert dt == DateType.PERIOD_DAY
        assert warnings == []

    def test_sanitise_no_date_type_stays(self) -> None:
        due, start, dt, warnings = _sanitise_date_fields(
            None,
            None,
            DateType.NO_DATE,
        )
        assert dt == DateType.NO_DATE
        assert warnings == []


# ---------------------------------------------------------------------------
# A007: Tool functions with date validation
# ---------------------------------------------------------------------------


class TestToolsA007:
    """Tests for tool functions with A007 date validation."""

    @pytest.fixture(autouse=True)
    async def _reset_store(self):
        store = DeadlineStore(":memory:")
        await store.initialize()
        await set_deadline_store(store)
        yield
        await store.close()
        await set_deadline_store(None)

    @pytest.mark.asyncio
    async def test_add_deadline_invalid_date_sanitised(self) -> None:
        """Non-ISO due_date should be cleared and date_type set to no_date."""
        result = json.loads(await add_deadline(title="Read Book", due_date="undecided"))
        assert result["due_date"] is None
        assert result["date_type"] == "no_date"
        assert "warnings" in result
        assert any("undecided" in w for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_add_deadline_valid_date_no_warnings(self) -> None:
        result = json.loads(await add_deadline(title="HW1", due_date="2026-04-15"))
        assert result["due_date"] == "2026-04-15T00:00:00"
        assert result["date_type"] == "moment_day"
        assert "warnings" not in result

    @pytest.mark.asyncio
    async def test_save_deadlines_invalid_date_sanitised(self) -> None:
        items = json.dumps(
            [{"title": "TBD Task", "due_date": "TBD", "date_type": "moment_day"}]
        )
        result = json.loads(await save_deadlines(items))
        assert result["count"] == 1
        assert result["deadlines"][0]["due_date"] is None
        assert result["deadlines"][0]["date_type"] == "no_date"
        assert "warnings" in result

    @pytest.mark.asyncio
    async def test_save_deadlines_mixed_valid_invalid(self) -> None:
        items = json.dumps(
            [
                {"title": "Good", "due_date": "2026-04-15"},
                {"title": "Bad", "due_date": "next week"},
            ]
        )
        result = json.loads(await save_deadlines(items))
        assert result["count"] == 2
        assert result["deadlines"][0]["due_date"] == "2026-04-15T00:00:00"
        assert result["deadlines"][1]["due_date"] is None
        assert result["deadlines"][1]["date_type"] == "no_date"


# ---------------------------------------------------------------------------
# A007: Store update method
# ---------------------------------------------------------------------------


class TestStoreUpdateA007:
    """Tests for DeadlineStore.update() (A007)."""

    @pytest.fixture
    async def store(self):
        s = DeadlineStore(":memory:")
        await s.initialize()
        yield s
        await s.close()

    @pytest.mark.asyncio
    async def test_update_single_field(self, store: DeadlineStore) -> None:
        await store.add(
            DeadlineRecord(id="d1", title="Old Title", due_date=datetime(2026, 4, 10))
        )
        updated = await store.update("d1", {"title": "New Title"})
        assert updated is not None
        assert updated.title == "New Title"
        assert updated.due_date == datetime(2026, 4, 10)  # Unchanged

    @pytest.mark.asyncio
    async def test_update_multiple_fields(self, store: DeadlineStore) -> None:
        await store.add(
            DeadlineRecord(
                id="d1",
                title="Test",
                course="CS302",
                due_date=datetime(2026, 4, 10),
            )
        )
        updated = await store.update(
            "d1",
            {
                "title": "Updated",
                "course": "MATH201",
                "priority": DeadlinePriority.HIGH,
            },
        )
        assert updated is not None
        assert updated.title == "Updated"
        assert updated.course == "MATH201"
        assert updated.priority == DeadlinePriority.HIGH

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_none(self, store: DeadlineStore) -> None:
        result = await store.update("nonexistent", {"title": "X"})
        assert result is None

    @pytest.mark.asyncio
    async def test_update_ignores_unknown_fields(self, store: DeadlineStore) -> None:
        await store.add(
            DeadlineRecord(
                id="d1",
                title="Test",
                due_date=datetime(2026, 4, 10),
            )
        )
        updated = await store.update("d1", {"bogus_column": "value", "title": "OK"})
        assert updated is not None
        assert updated.title == "OK"

    @pytest.mark.asyncio
    async def test_update_empty_fields_returns_current(
        self, store: DeadlineStore
    ) -> None:
        await store.add(
            DeadlineRecord(
                id="d1",
                title="Test",
                due_date=datetime(2026, 4, 10),
            )
        )
        updated = await store.update("d1", {})
        assert updated is not None
        assert updated.title == "Test"


# ---------------------------------------------------------------------------
# A008: Date range validation in _sanitise_date_fields
# ---------------------------------------------------------------------------


class TestDateRangeValidation:
    """Tests for start_date <= due_date validation (A008)."""

    def test_sanitise_rejects_start_after_due(self) -> None:
        due, start, dt, warnings = _sanitise_date_fields(
            datetime(2026, 4, 10),
            datetime(2026, 4, 15),
            DateType.PERIOD_DAY,
        )
        assert start is None
        assert due == datetime(2026, 4, 10)
        assert any("start_date" in w and "after" in w for w in warnings)

    def test_sanitise_accepts_start_equal_due(self) -> None:
        due, start, dt, warnings = _sanitise_date_fields(
            datetime(2026, 4, 10),
            datetime(2026, 4, 10),
            DateType.PERIOD_DAY,
        )
        assert start == datetime(2026, 4, 10)
        assert due == datetime(2026, 4, 10)
        assert warnings == []

    def test_sanitise_accepts_start_before_due(self) -> None:
        due, start, dt, warnings = _sanitise_date_fields(
            datetime(2026, 4, 15),
            datetime(2026, 4, 10),
            DateType.PERIOD_DAY,
        )
        assert start == datetime(2026, 4, 10)
        assert due == datetime(2026, 4, 15)
        assert warnings == []

    def test_sanitise_range_check_same_date(self) -> None:
        """When both dates parse to the same date, range is OK."""
        due, start, dt, warnings = _sanitise_date_fields(
            datetime(2026, 4, 10),
            datetime(2026, 4, 10),
            DateType.PERIOD_HM,
        )
        assert start == datetime(2026, 4, 10)
        assert warnings == []

    def test_sanitise_skips_range_check_when_start_none(self) -> None:
        due, start, dt, warnings = _sanitise_date_fields(
            datetime(2026, 4, 15),
            None,
            DateType.MOMENT_DAY,
        )
        assert warnings == []

    def test_sanitise_skips_range_check_when_due_none(self) -> None:
        due, start, dt, warnings = _sanitise_date_fields(
            None,
            datetime(2026, 4, 10),
            DateType.PERIOD_DAY,
        )
        # due_date None means date_type downgraded
        assert dt == DateType.NO_DATE


# ---------------------------------------------------------------------------
# A008: delete_deadline tool
# ---------------------------------------------------------------------------


class TestDeleteDeadlineTool:
    """Tests for the delete_deadline LLM tool (A008)."""

    @pytest.fixture(autouse=True)
    async def _reset_store(self):
        store = DeadlineStore(":memory:")
        await store.initialize()
        await set_deadline_store(store)
        yield
        await store.close()
        await set_deadline_store(None)

    @pytest.mark.asyncio
    async def test_delete_existing(self) -> None:
        await add_deadline(title="To Delete", due_date="2026-04-20")
        all_items = json.loads(await list_deadlines())
        assert len(all_items) == 1
        dl_id = all_items[0]["id"]

        result = json.loads(await delete_deadline(dl_id))
        assert result["status"] == "deleted"
        assert result["id"] == dl_id

        remaining = json.loads(await list_deadlines())
        assert len(remaining) == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self) -> None:
        result = json.loads(await delete_deadline("no-such-id"))
        assert "error" in result


# ---------------------------------------------------------------------------
# A008: update_deadline tool
# ---------------------------------------------------------------------------


class TestUpdateDeadlineTool:
    """Tests for the update_deadline LLM tool (A008)."""

    @pytest.fixture(autouse=True)
    async def _reset_store(self):
        store = DeadlineStore(":memory:")
        await store.initialize()
        await set_deadline_store(store)
        yield
        await store.close()
        await set_deadline_store(None)

    @pytest.mark.asyncio
    async def test_update_title(self) -> None:
        created = json.loads(await add_deadline(title="Old", due_date="2026-04-15"))
        result = json.loads(await update_deadline(created["id"], title="New"))
        assert result["title"] == "New"
        assert result["due_date"] == "2026-04-15T00:00:00"

    @pytest.mark.asyncio
    async def test_update_nonexistent(self) -> None:
        result = json.loads(await update_deadline("no-such-id", title="X"))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_update_invalid_priority(self) -> None:
        created = json.loads(await add_deadline(title="Test", due_date="2026-04-15"))
        result = json.loads(await update_deadline(created["id"], priority="urgent"))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_update_date_with_range_violation(self) -> None:
        created = json.loads(
            await add_deadline(
                title="Test",
                due_date="2026-04-15",
                start_date="2026-04-10",
                date_type="period_day",
            )
        )
        # Try to set start_date after due_date
        result = json.loads(
            await update_deadline(created["id"], start_date="2026-04-20")
        )
        # Sanitiser clears the invalid start_date and returns warnings
        assert result.get("start_date") != "2026-04-20"
        assert "warnings" in result
        assert any("start_date" in w for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_update_no_fields_returns_info(self) -> None:
        created = json.loads(await add_deadline(title="Test", due_date="2026-04-15"))
        result = json.loads(await update_deadline(created["id"]))
        assert result.get("info") == "No fields to update."

    @pytest.mark.asyncio
    async def test_update_valid_range_no_warnings(self) -> None:
        created = json.loads(
            await add_deadline(
                title="Test",
                due_date="2026-04-15",
                start_date="2026-04-10",
                date_type="period_day",
            )
        )
        result = json.loads(
            await update_deadline(created["id"], start_date="2026-04-12")
        )
        assert result["start_date"] == "2026-04-12T00:00:00"
        assert "warnings" not in result


# ---------------------------------------------------------------------------
# A008: add_deadline tool date range validation
# ---------------------------------------------------------------------------


class TestAddDeadlineDateRange:
    """Tests for add_deadline with date range validation (A008)."""

    @pytest.fixture(autouse=True)
    async def _reset_store(self):
        store = DeadlineStore(":memory:")
        await store.initialize()
        await set_deadline_store(store)
        yield
        await store.close()
        await set_deadline_store(None)

    @pytest.mark.asyncio
    async def test_add_deadline_start_after_due_cleared(self) -> None:
        result = json.loads(
            await add_deadline(
                title="Bad Range",
                due_date="2026-04-10",
                start_date="2026-04-15",
                date_type="period_day",
            )
        )
        assert result["start_date"] is None
        assert "warnings" in result

    @pytest.mark.asyncio
    async def test_add_deadline_valid_range_no_warning(self) -> None:
        result = json.loads(
            await add_deadline(
                title="Good Range",
                due_date="2026-04-15",
                start_date="2026-04-10",
                date_type="period_day",
            )
        )
        assert result["start_date"] == "2026-04-10T00:00:00"
        assert result["due_date"] == "2026-04-15T00:00:00"
        assert "warnings" not in result


# ---------------------------------------------------------------------------
# A008: Tool registration includes new tools
# ---------------------------------------------------------------------------


class TestToolRegistrationA008:
    """Tests for tool registration with new tools (A008)."""

    def test_register_includes_delete_and_update(self) -> None:
        registry = ToolRegistry()
        register_deadline_tools(registry)
        names = {t.name for t in registry.list_tools()}
        assert "delete_deadline" in names
        assert "update_deadline" in names


# ---------------------------------------------------------------------------
# A013: Legacy / dirty DB data resilience
# ---------------------------------------------------------------------------


class TestLegacyDirtyDB:
    """Ensure the ORM handles legacy DB rows containing non-ISO date strings.

    Older code (or manual edits) may have stored empty strings ``''``,
    localised placeholders like ``'TBD'``, or other non-parseable text in
    the ``due_date`` / ``start_date`` TEXT columns.  The
    ``LenientDateTime`` type decorator must silently coerce these to
    ``None`` so that ``list_all()`` never crashes.
    """

    @pytest.fixture
    async def store(self):
        s = DeadlineStore(":memory:")
        await s.initialize()
        yield s
        await s.close()

    @pytest.mark.asyncio
    async def test_list_all_with_empty_string_dates(self, store: DeadlineStore) -> None:
        """Empty-string start_date must be read as None, not crash."""
        # Insert via raw SQL to simulate legacy data
        async with store._engine.begin() as conn:
            await conn.exec_driver_sql(
                "INSERT INTO deadlines "
                "(id, title, course, due_date, start_date, priority, "
                " source, description, date_type, completed) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "dirty-1",
                    "Legacy HW",
                    "CS101",
                    "2026-04-15",  # valid
                    "",  # empty string — must not crash
                    "high",
                    "manual",
                    "",
                    "moment_day",
                    0,
                ),
            )
        items = await store.list_all()
        assert len(items) == 1
        assert items[0].due_date == datetime(2026, 4, 15)
        assert items[0].start_date is None

    @pytest.mark.asyncio
    async def test_list_all_with_non_iso_due_date(self, store: DeadlineStore) -> None:
        """Non-ISO text (e.g. 'TBD') in due_date must become None."""
        async with store._engine.begin() as conn:
            await conn.exec_driver_sql(
                "INSERT INTO deadlines "
                "(id, title, course, due_date, start_date, priority, "
                " source, description, date_type, completed) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "dirty-2",
                    "TBD Task",
                    "CS202",
                    "TBD",  # non-ISO — must not crash
                    "",
                    "medium",
                    "manual",
                    "",
                    "no_date",
                    0,
                ),
            )
        items = await store.list_all()
        assert len(items) == 1
        assert items[0].due_date is None
        assert items[0].start_date is None

    @pytest.mark.asyncio
    async def test_list_all_mixed_clean_and_dirty(self, store: DeadlineStore) -> None:
        """Mix of clean and dirty rows — all must load without error."""
        await store.add(
            DeadlineRecord(
                id="clean-1",
                title="Clean HW",
                course="CS101",
                due_date=datetime(2026, 5, 1),
            )
        )
        # Dirty row via raw SQL
        async with store._engine.begin() as conn:
            await conn.exec_driver_sql(
                "INSERT INTO deadlines "
                "(id, title, course, due_date, start_date, priority, "
                " source, description, date_type, completed) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "dirty-3",
                    "Dirty Task",
                    "CS202",
                    "TBD",
                    "",
                    "low",
                    "email",
                    "notes",
                    "no_date",
                    0,
                ),
            )
        items = await store.list_all()
        assert len(items) == 2
        titles = {r.title for r in items}
        assert titles == {"Clean HW", "Dirty Task"}

    @pytest.mark.asyncio
    async def test_get_single_dirty_row(self, store: DeadlineStore) -> None:
        """get() on a single dirty row must also succeed."""
        async with store._engine.begin() as conn:
            await conn.exec_driver_sql(
                "INSERT INTO deadlines "
                "(id, title, course, due_date, start_date, priority, "
                " source, description, date_type, completed) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "dirty-4",
                    "Single Dirty",
                    "CS303",
                    "",
                    "not-a-date",
                    "medium",
                    "manual",
                    "",
                    "moment_day",
                    0,
                ),
            )
        record = await store.get("dirty-4")
        assert record is not None
        assert record.due_date is None
        assert record.start_date is None


# ---------------------------------------------------------------------------
# A017: Old-schema database migration — NOT NULL → nullable
# ---------------------------------------------------------------------------


class TestOldSchemaMigration:
    """Ensure DeadlineStore handles old DB schemas with NOT NULL date columns.

    Older databases were created with:
        start_date TEXT NOT NULL DEFAULT ''
        due_date   TEXT NOT NULL DEFAULT ''

    The current model defines these as nullable.  SQLModel's create_all()
    does NOT alter existing tables, so the store must handle this mismatch
    by migrating the schema on initialize().
    """

    @pytest.fixture
    async def old_schema_store(self, tmp_path):
        """Create a store backed by a DB file with the old NOT NULL schema."""
        import aiosqlite

        db_file = str(tmp_path / "old_deadlines.db")

        # Create the old schema manually (NOT NULL DEFAULT '' on date cols)
        async with aiosqlite.connect(db_file) as db:
            await db.execute(
                """
                CREATE TABLE deadlines (
                    id         TEXT PRIMARY KEY,
                    title      TEXT NOT NULL,
                    course     TEXT NOT NULL DEFAULT '',
                    due_date   TEXT NOT NULL DEFAULT '',
                    priority   TEXT NOT NULL DEFAULT 'medium',
                    source     TEXT NOT NULL DEFAULT 'manual',
                    description TEXT NOT NULL DEFAULT '',
                    date_type  TEXT NOT NULL DEFAULT 'moment_day',
                    start_date TEXT NOT NULL DEFAULT '',
                    completed  INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            await db.commit()

        store = DeadlineStore(db_file)
        await store.initialize()
        yield store
        await store.close()

    @pytest.mark.asyncio
    async def test_insert_none_start_date_on_old_schema(
        self, old_schema_store: DeadlineStore
    ) -> None:
        """Inserting a record with start_date=None must not crash on old schema.

        This is the exact bug reported in A017: the frontend sends
        start_date="" which is coerced to None, but the old NOT NULL
        column rejects NULL, causing a 500 IntegrityError.
        """
        record = DeadlineRecord(
            id="test-old-1",
            title="Test on old schema",
            course="CS302",
            due_date=datetime(2026, 4, 14, 18, 55),
            priority=DeadlinePriority.MEDIUM,
            source=DeadlineSource.MANUAL,
            date_type=DateType.MOMENT_HM,
            start_date=None,  # This is the critical case
        )
        saved = await old_schema_store.add(record)
        assert saved.id == "test-old-1"
        assert saved.start_date is None

    @pytest.mark.asyncio
    async def test_insert_none_due_date_on_old_schema(
        self, old_schema_store: DeadlineStore
    ) -> None:
        """Inserting a record with due_date=None must not crash on old schema."""
        record = DeadlineRecord(
            id="test-old-2",
            title="No-date task on old schema",
            date_type=DateType.NO_DATE,
            due_date=None,
            start_date=None,
        )
        saved = await old_schema_store.add(record)
        assert saved.id == "test-old-2"
        assert saved.due_date is None
        assert saved.start_date is None

    @pytest.mark.asyncio
    async def test_old_schema_preserves_existing_data(
        self,
        tmp_path,
    ) -> None:
        """Migration must not lose existing data in old-schema tables."""
        import aiosqlite

        db_file = str(tmp_path / "preserve_deadlines.db")

        # Create old schema with existing data
        async with aiosqlite.connect(db_file) as db:
            await db.execute(
                """
                CREATE TABLE deadlines (
                    id         TEXT PRIMARY KEY,
                    title      TEXT NOT NULL,
                    course     TEXT NOT NULL DEFAULT '',
                    due_date   TEXT NOT NULL DEFAULT '',
                    priority   TEXT NOT NULL DEFAULT 'medium',
                    source     TEXT NOT NULL DEFAULT 'manual',
                    description TEXT NOT NULL DEFAULT '',
                    date_type  TEXT NOT NULL DEFAULT 'moment_day',
                    start_date TEXT NOT NULL DEFAULT '',
                    completed  INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            await db.execute(
                "INSERT INTO deadlines (id, title, course, due_date, start_date) "
                "VALUES (?, ?, ?, ?, ?)",
                ("existing-1", "Old HW", "CS101", "2026-04-15", ""),
            )
            await db.commit()

        store = DeadlineStore(db_file)
        await store.initialize()
        try:
            items = await store.list_all()
            assert len(items) == 1
            assert items[0].title == "Old HW"
            assert items[0].due_date == datetime(2026, 4, 15)
            assert items[0].start_date is None  # "" coerced to None on read
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_update_date_to_none_on_old_schema(
        self, old_schema_store: DeadlineStore
    ) -> None:
        """Updating a date field to None should work on migrated old schema."""
        record = DeadlineRecord(
            id="test-old-3",
            title="To update",
            due_date=datetime(2026, 4, 15),
            start_date=datetime(2026, 4, 10),
            date_type=DateType.PERIOD_DAY,
        )
        await old_schema_store.add(record)
        updated = await old_schema_store.update("test-old-3", {"start_date": None})
        assert updated is not None
        assert updated.start_date is None
