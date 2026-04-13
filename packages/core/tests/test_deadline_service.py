"""Tests for the deadline service layer.

Validates business logic in :class:`DeadlineService` independently of
the HTTP / tool-function adapters, ensuring that the single source of
truth for deadline rules is well-covered.
"""

from datetime import date, datetime

import pytest

from agent_core.models.deadline import (
    DateType,
    DeadlinePriority,
    DeadlineRecord,
    DeadlineSource,
    parse_date_field,
    parse_datetime_field,
)
from agent_core.persistence.deadline_store import DeadlineStore
from agent_core.services.deadline_service import (
    DeadlineNotFoundError,
    DeadlineService,
    DeadlineValidationError,
    build_record_from_dict,
    sanitise_date_fields,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def store():
    """In-memory DeadlineStore for isolated testing."""
    s = DeadlineStore(":memory:")
    await s.initialize()
    yield s
    await s.close()


@pytest.fixture
async def svc(store: DeadlineStore):
    """DeadlineService backed by an in-memory store."""
    return DeadlineService(store)


# ---------------------------------------------------------------------------
# Pure helper tests
# ---------------------------------------------------------------------------


class TestParseDateField:
    """Tests for :func:`parse_date_field`."""

    def test_date_only(self) -> None:
        assert parse_date_field("2026-04-15") == date(2026, 4, 15)

    def test_datetime_hm(self) -> None:
        assert parse_date_field("2026-04-15T14:30") == date(2026, 4, 15)

    def test_datetime_hms(self) -> None:
        assert parse_date_field("2026-04-15T14:30:00") == date(2026, 4, 15)

    def test_empty(self) -> None:
        assert parse_date_field("") is None

    def test_natural_language(self) -> None:
        assert parse_date_field("next week") is None

    def test_tbd(self) -> None:
        assert parse_date_field("TBD") is None

    def test_date_passthrough(self) -> None:
        d = date(2026, 4, 15)
        assert parse_date_field(d) == d

    def test_none_passthrough(self) -> None:
        assert parse_date_field(None) is None


class TestSanitiseDateFields:
    """Tests for :func:`sanitise_date_fields` (now takes date | None)."""

    def test_valid_dates_pass_through(self) -> None:
        due, start, dt, warnings = sanitise_date_fields(
            datetime(2026, 4, 15), datetime(2026, 4, 1), DateType.PERIOD_DAY
        )
        assert due == datetime(2026, 4, 15)
        assert start == datetime(2026, 4, 1)
        assert dt == DateType.PERIOD_DAY
        assert warnings == []

    def test_none_due_downgrades_to_no_date(self) -> None:
        due, start, dt, warnings = sanitise_date_fields(None, None, DateType.MOMENT_DAY)
        assert due is None
        assert dt == DateType.NO_DATE
        assert len(warnings) >= 1

    def test_no_date_stays(self) -> None:
        due, start, dt, warnings = sanitise_date_fields(None, None, DateType.NO_DATE)
        assert dt == DateType.NO_DATE
        assert warnings == []

    def test_start_after_due_cleared(self) -> None:
        due, start, dt, warnings = sanitise_date_fields(
            datetime(2026, 4, 10), datetime(2026, 4, 15), DateType.PERIOD_DAY
        )
        assert start is None
        assert any("after" in w for w in warnings)

    def test_equal_dates_ok(self) -> None:
        due, start, dt, warnings = sanitise_date_fields(
            datetime(2026, 4, 10), datetime(2026, 4, 10), DateType.PERIOD_DAY
        )
        assert start == datetime(2026, 4, 10)
        assert warnings == []


class TestBuildRecordFromDict:
    """Tests for :func:`build_record_from_dict`."""

    def test_minimal_dict(self) -> None:
        record, warnings = build_record_from_dict({"title": "HW1"})
        assert record.title == "HW1"
        assert record.priority == DeadlinePriority.MEDIUM
        assert record.source == DeadlineSource.MANUAL
        assert record.id  # UUID generated

    def test_full_dict(self) -> None:
        record, warnings = build_record_from_dict(
            {
                "title": "Project",
                "course": "CS302",
                "due_date": "2026-04-15",
                "priority": "high",
                "source": "blackboard",
                "date_type": "moment_day",
                "description": "Submit via BB",
            }
        )
        assert record.priority == DeadlinePriority.HIGH
        assert record.source == DeadlineSource.BLACKBOARD
        assert record.date_type == DateType.MOMENT_DAY
        assert warnings == []

    def test_invalid_priority_defaults(self) -> None:
        record, warnings = build_record_from_dict(
            {"title": "Test", "priority": "URGENT"}
        )
        assert record.priority == DeadlinePriority.MEDIUM

    def test_invalid_date_type_defaults(self) -> None:
        record, warnings = build_record_from_dict(
            {"title": "Test", "date_type": "bogus"}
        )
        # date_type defaults to MOMENT_DAY, but no due_date -> downgraded to NO_DATE
        assert record.date_type == DateType.NO_DATE

    def test_invalid_date_produces_warning(self) -> None:
        record, warnings = build_record_from_dict({"title": "Test", "due_date": "TBD"})
        assert record.due_date is None
        assert record.date_type == DateType.NO_DATE
        assert len(warnings) >= 1

    def test_empty_title_gets_default(self) -> None:
        record, _ = build_record_from_dict({})
        assert record.title == "Untitled"


# ---------------------------------------------------------------------------
# Service — create
# ---------------------------------------------------------------------------


class TestServiceCreate:
    """Tests for typed :meth:`DeadlineService.create`."""

    @pytest.mark.asyncio
    async def test_create_basic(self, svc: DeadlineService) -> None:
        record, warnings = await svc.create(title="HW1", due_date=datetime(2026, 4, 15))
        assert record.title == "HW1"
        assert record.due_date == datetime(2026, 4, 15)
        assert record.id
        assert warnings == []

    @pytest.mark.asyncio
    async def test_create_with_all_fields(self, svc: DeadlineService) -> None:
        record, _ = await svc.create(
            title="Sprint",
            course="CS302",
            due_date=datetime(2026, 4, 20),
            priority=DeadlinePriority.HIGH,
            description="Important",
            date_type=DateType.PERIOD_DAY,
            start_date=datetime(2026, 4, 10),
        )
        assert record.priority == DeadlinePriority.HIGH
        assert record.date_type == DateType.PERIOD_DAY
        assert record.start_date == datetime(2026, 4, 10)

    @pytest.mark.asyncio
    async def test_create_range_violation_raises(self, svc: DeadlineService) -> None:
        with pytest.raises(DeadlineValidationError, match="start_date"):
            await svc.create(
                title="Bad",
                due_date=datetime(2026, 4, 10),
                start_date=datetime(2026, 4, 15),
                date_type=DateType.PERIOD_DAY,
            )


class TestServiceCreateFromDict:
    """Tests for :meth:`DeadlineService.create_from_dict`."""

    @pytest.mark.asyncio
    async def test_basic(self, svc: DeadlineService) -> None:
        record, warnings = await svc.create_from_dict(
            {"title": "Read Book", "due_date": "2026-04-20"}
        )
        assert record.title == "Read Book"
        assert warnings == []

    @pytest.mark.asyncio
    async def test_invalid_date_sanitised(self, svc: DeadlineService) -> None:
        record, warnings = await svc.create_from_dict(
            {"title": "Test", "due_date": "undecided"}
        )
        assert record.due_date is None
        assert record.date_type == DateType.NO_DATE
        assert len(warnings) >= 1


# ---------------------------------------------------------------------------
# Service — list / get
# ---------------------------------------------------------------------------


class TestServiceRead:
    """Tests for read operations."""

    @pytest.mark.asyncio
    async def test_list_empty(self, svc: DeadlineService) -> None:
        records = await svc.list_deadlines()
        assert records == []

    @pytest.mark.asyncio
    async def test_list_with_data(self, svc: DeadlineService) -> None:
        await svc.create(title="A", due_date=datetime(2026, 4, 10))
        await svc.create(title="B", due_date=datetime(2026, 4, 20))
        records = await svc.list_deadlines()
        assert len(records) == 2

    @pytest.mark.asyncio
    async def test_list_filter_course(self, svc: DeadlineService) -> None:
        await svc.create(title="A", course="CS302", due_date=datetime(2026, 4, 10))
        await svc.create(title="B", course="MATH201", due_date=datetime(2026, 4, 20))
        records = await svc.list_deadlines(course="CS302")
        assert len(records) == 1
        assert records[0].course == "CS302"

    @pytest.mark.asyncio
    async def test_get_existing(self, svc: DeadlineService) -> None:
        created, _ = await svc.create(title="X", due_date=datetime(2026, 4, 10))
        fetched = await svc.get(created.id)
        assert fetched.title == "X"

    @pytest.mark.asyncio
    async def test_get_nonexistent_raises(self, svc: DeadlineService) -> None:
        with pytest.raises(DeadlineNotFoundError):
            await svc.get("no-such-id")


# ---------------------------------------------------------------------------
# Service — update
# ---------------------------------------------------------------------------


class TestServiceUpdate:
    """Tests for :meth:`DeadlineService.update`."""

    @pytest.mark.asyncio
    async def test_update_single_field(self, svc: DeadlineService) -> None:
        created, _ = await svc.create(title="Old", due_date=datetime(2026, 4, 10))
        updated, warnings = await svc.update(created.id, {"title": "New"})
        assert updated.title == "New"
        assert updated.due_date == datetime(2026, 4, 10)
        assert warnings == []

    @pytest.mark.asyncio
    async def test_update_empty_dict_returns_existing(
        self, svc: DeadlineService
    ) -> None:
        created, _ = await svc.create(title="Test", due_date=datetime(2026, 4, 10))
        updated, warnings = await svc.update(created.id, {})
        assert updated.title == "Test"
        assert warnings == []

    @pytest.mark.asyncio
    async def test_update_nonexistent_raises(self, svc: DeadlineService) -> None:
        with pytest.raises(DeadlineNotFoundError):
            await svc.update("no-such-id", {"title": "X"})

    @pytest.mark.asyncio
    async def test_update_date_range_violation_raises(
        self, svc: DeadlineService
    ) -> None:
        created, _ = await svc.create(
            title="T",
            due_date=datetime(2026, 4, 15),
            start_date=datetime(2026, 4, 10),
            date_type=DateType.PERIOD_DAY,
        )
        with pytest.raises(DeadlineValidationError, match="start_date"):
            await svc.update(created.id, {"start_date": datetime(2026, 4, 20)})


class TestServiceUpdateFromTool:
    """Tests for :meth:`DeadlineService.update_from_tool`."""

    @pytest.mark.asyncio
    async def test_update_title(self, svc: DeadlineService) -> None:
        created, _ = await svc.create(title="Old", due_date=datetime(2026, 4, 15))
        updated, warnings = await svc.update_from_tool(created.id, title="New")
        assert updated.title == "New"
        assert warnings == []

    @pytest.mark.asyncio
    async def test_update_invalid_priority_raises(self, svc: DeadlineService) -> None:
        created, _ = await svc.create(title="T", due_date=datetime(2026, 4, 15))
        with pytest.raises(DeadlineValidationError, match="priority"):
            await svc.update_from_tool(created.id, priority="urgent")

    @pytest.mark.asyncio
    async def test_update_nonexistent_raises(self, svc: DeadlineService) -> None:
        with pytest.raises(DeadlineNotFoundError):
            await svc.update_from_tool("no-such-id", title="X")

    @pytest.mark.asyncio
    async def test_update_date_with_sanitisation(self, svc: DeadlineService) -> None:
        created, _ = await svc.create(
            title="T",
            due_date=datetime(2026, 4, 15),
            start_date=datetime(2026, 4, 10),
            date_type=DateType.PERIOD_DAY,
        )
        # start_date after due_date -> sanitised (cleared + warning)
        updated, warnings = await svc.update_from_tool(
            created.id, start_date="2026-04-20"
        )
        assert updated.start_date != datetime(2026, 4, 20)
        assert len(warnings) >= 1

    @pytest.mark.asyncio
    async def test_update_no_fields(self, svc: DeadlineService) -> None:
        created, _ = await svc.create(title="T", due_date=datetime(2026, 4, 15))
        updated, warnings = await svc.update_from_tool(created.id)
        assert updated.title == "T"
        assert warnings == []


# ---------------------------------------------------------------------------
# Service — delete
# ---------------------------------------------------------------------------


class TestServiceDelete:
    """Tests for :meth:`DeadlineService.delete`."""

    @pytest.mark.asyncio
    async def test_delete_existing(self, svc: DeadlineService) -> None:
        created, _ = await svc.create(title="ToDelete", due_date=datetime(2026, 4, 10))
        result = await svc.delete(created.id)
        assert result is True
        # Verify gone
        records = await svc.list_deadlines()
        assert len(records) == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent_raises(self, svc: DeadlineService) -> None:
        with pytest.raises(DeadlineNotFoundError):
            await svc.delete("no-such-id")


# ---------------------------------------------------------------------------
# Service — toggle completed
# ---------------------------------------------------------------------------


class TestServiceToggleCompleted:
    """Tests for :meth:`DeadlineService.toggle_completed`."""

    @pytest.mark.asyncio
    async def test_toggle_on(self, svc: DeadlineService) -> None:
        created, _ = await svc.create(title="T", due_date=datetime(2026, 4, 10))
        updated = await svc.toggle_completed(created.id, True)
        assert updated.completed is True

    @pytest.mark.asyncio
    async def test_toggle_off(self, svc: DeadlineService) -> None:
        created, _ = await svc.create(title="T", due_date=datetime(2026, 4, 10))
        await svc.toggle_completed(created.id, True)
        updated = await svc.toggle_completed(created.id, False)
        assert updated.completed is False

    @pytest.mark.asyncio
    async def test_toggle_nonexistent_raises(self, svc: DeadlineService) -> None:
        with pytest.raises(DeadlineNotFoundError):
            await svc.toggle_completed("no-such-id", True)


# ---------------------------------------------------------------------------
# Service — sync
# ---------------------------------------------------------------------------


class TestServiceSync:
    """Tests for sync_preview and sync_commit."""

    @pytest.mark.asyncio
    async def test_preview_all_new(self, svc: DeadlineService) -> None:
        candidates = [
            DeadlineRecord(title="A", due_date=datetime(2026, 4, 20)),
        ]
        new_tasks, duplicates = await svc.sync_preview(candidates)
        assert len(new_tasks) == 1
        assert len(duplicates) == 0

    @pytest.mark.asyncio
    async def test_preview_detects_duplicates(self, svc: DeadlineService) -> None:
        await svc.create(title="HW1", due_date=datetime(2026, 4, 15))
        candidates = [
            DeadlineRecord(title="HW1", due_date=datetime(2026, 4, 15)),
            DeadlineRecord(title="HW2", due_date=datetime(2026, 4, 20)),
        ]
        new_tasks, duplicates = await svc.sync_preview(candidates)
        assert len(new_tasks) == 1
        assert new_tasks[0].title == "HW2"
        assert len(duplicates) == 1

    @pytest.mark.asyncio
    async def test_commit(self, svc: DeadlineService) -> None:
        tasks = [
            DeadlineRecord(title="Task1", due_date=datetime(2026, 4, 25)),
            DeadlineRecord(title="Task2", due_date=datetime(2026, 4, 26)),
        ]
        added = await svc.sync_commit(tasks)
        assert len(added) == 2
        # Verify persistence
        all_items = await svc.list_deadlines()
        assert len(all_items) == 2


# ---------------------------------------------------------------------------
# Service — save_batch
# ---------------------------------------------------------------------------


class TestServiceSaveBatch:
    """Tests for :meth:`DeadlineService.save_batch`."""

    @pytest.mark.asyncio
    async def test_basic_batch(self, svc: DeadlineService) -> None:
        items = [
            {"title": "HW1", "due_date": "2026-04-15", "priority": "high"},
            {"title": "HW2", "due_date": "2026-04-20"},
        ]
        saved, warnings, skipped = await svc.save_batch(items)
        assert len(saved) == 2
        assert saved[0].priority == DeadlinePriority.HIGH
        assert saved[1].priority == DeadlinePriority.MEDIUM

    @pytest.mark.asyncio
    async def test_skips_non_dict(self, svc: DeadlineService) -> None:
        items = ["not-a-dict", {"title": "Valid", "due_date": "2026-04-10"}]
        saved, warnings, skipped = await svc.save_batch(items)
        assert len(saved) == 1
        assert len(skipped) == 1

    @pytest.mark.asyncio
    async def test_invalid_dates_produce_warnings(self, svc: DeadlineService) -> None:
        items = [{"title": "T", "due_date": "TBD"}]
        saved, warnings, skipped = await svc.save_batch(items)
        assert len(saved) == 1
        assert saved[0].due_date is None
        assert len(warnings) >= 1

    @pytest.mark.asyncio
    async def test_empty_batch(self, svc: DeadlineService) -> None:
        saved, warnings, skipped = await svc.save_batch([])
        assert saved == []
        assert warnings == []
        assert skipped == []


# ---------------------------------------------------------------------------
# A011: parse_datetime_field tests (hour:minute precision)
# ---------------------------------------------------------------------------


class TestParseDatetimeField:
    """Tests for :func:`parse_datetime_field` — datetime precision."""

    def test_date_only_returns_midnight(self) -> None:
        assert parse_datetime_field("2026-04-15") == datetime(2026, 4, 15)

    def test_datetime_hm(self) -> None:
        assert parse_datetime_field("2026-04-15T14:30") == datetime(2026, 4, 15, 14, 30)

    def test_datetime_hms(self) -> None:
        assert parse_datetime_field("2026-04-15T14:30:45") == datetime(
            2026, 4, 15, 14, 30, 45
        )

    def test_empty_string(self) -> None:
        assert parse_datetime_field("") is None

    def test_none(self) -> None:
        assert parse_datetime_field(None) is None

    def test_natural_language(self) -> None:
        assert parse_datetime_field("next week") is None

    def test_tbd(self) -> None:
        assert parse_datetime_field("TBD") is None

    def test_datetime_passthrough(self) -> None:
        dt = datetime(2026, 4, 15, 9, 0)
        assert parse_datetime_field(dt) is dt

    def test_date_object_to_midnight(self) -> None:
        d = date(2026, 4, 15)
        result = parse_datetime_field(d)
        assert result == datetime(2026, 4, 15, 0, 0)
        assert isinstance(result, datetime)


# ---------------------------------------------------------------------------
# A011: MOMENT_HM / PERIOD_HM specific scenarios
# ---------------------------------------------------------------------------


class TestHMPrecision:
    """Tests for MOMENT_HM and PERIOD_HM datetime precision."""

    @pytest.mark.asyncio
    async def test_create_moment_hm(
        self, svc: DeadlineService, store: DeadlineStore
    ) -> None:
        saved, warnings = await svc.create(
            title="Lecture",
            due_date=datetime(2026, 4, 15, 14, 30),
            date_type=DateType.MOMENT_HM,
        )
        assert saved.due_date == datetime(2026, 4, 15, 14, 30)
        assert saved.date_type == DateType.MOMENT_HM

    @pytest.mark.asyncio
    async def test_create_period_hm(
        self, svc: DeadlineService, store: DeadlineStore
    ) -> None:
        saved, warnings = await svc.create(
            title="Lab Session",
            start_date=datetime(2026, 4, 15, 9, 0),
            due_date=datetime(2026, 4, 15, 11, 30),
            date_type=DateType.PERIOD_HM,
        )
        assert saved.start_date == datetime(2026, 4, 15, 9, 0)
        assert saved.due_date == datetime(2026, 4, 15, 11, 30)
        assert saved.date_type == DateType.PERIOD_HM

    @pytest.mark.asyncio
    async def test_create_from_dict_moment_hm(self, svc: DeadlineService) -> None:
        saved, warnings = await svc.create_from_dict(
            {
                "title": "Office Hours",
                "due_date": "2026-04-15T14:30",
                "date_type": "moment_hm",
            }
        )
        assert saved.due_date == datetime(2026, 4, 15, 14, 30)
        assert saved.date_type == DateType.MOMENT_HM

    @pytest.mark.asyncio
    async def test_create_from_dict_period_hm(self, svc: DeadlineService) -> None:
        saved, warnings = await svc.create_from_dict(
            {
                "title": "Workshop",
                "start_date": "2026-04-15T09:00",
                "due_date": "2026-04-15T17:00",
                "date_type": "period_hm",
            }
        )
        assert saved.start_date == datetime(2026, 4, 15, 9, 0)
        assert saved.due_date == datetime(2026, 4, 15, 17, 0)
        assert saved.date_type == DateType.PERIOD_HM

    @pytest.mark.asyncio
    async def test_hm_range_violation(self, svc: DeadlineService) -> None:
        with pytest.raises(DeadlineValidationError):
            await svc.create(
                title="Bad",
                start_date=datetime(2026, 4, 15, 14, 0),
                due_date=datetime(2026, 4, 15, 10, 0),
                date_type=DateType.PERIOD_HM,
            )

    @pytest.mark.asyncio
    async def test_hm_serialization_roundtrip(self, svc: DeadlineService) -> None:
        saved, _ = await svc.create(
            title="Seminar",
            due_date=datetime(2026, 4, 15, 16, 45),
            date_type=DateType.MOMENT_HM,
        )
        data = saved.model_dump(mode="json")
        assert data["due_date"] == "2026-04-15T16:45:00"
        assert data["date_type"] == "moment_hm"

    @pytest.mark.asyncio
    async def test_find_duplicate_with_datetime(self, store: DeadlineStore) -> None:
        record = DeadlineRecord(
            id="d1",
            title="Meeting",
            due_date=datetime(2026, 4, 15, 14, 30),
            date_type=DateType.MOMENT_HM,
        )
        await store.add(record)
        dup = await store.find_duplicate("Meeting", datetime(2026, 4, 15, 14, 30))
        assert dup is not None
        assert dup.id == "d1"

    @pytest.mark.asyncio
    async def test_find_duplicate_different_time(self, store: DeadlineStore) -> None:
        record = DeadlineRecord(
            id="d1",
            title="Meeting",
            due_date=datetime(2026, 4, 15, 14, 30),
            date_type=DateType.MOMENT_HM,
        )
        await store.add(record)
        dup = await store.find_duplicate("Meeting", datetime(2026, 4, 15, 15, 0))
        assert dup is None
