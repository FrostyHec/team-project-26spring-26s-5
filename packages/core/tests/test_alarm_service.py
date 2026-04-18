"""Tests for :class:`AlarmService` — core alarm business logic.

Tests cover:
  S1-S4   : compute_trigger_time pure function
  S5-S12  : check_and_dispatch filtering and dispatch logic
  S13-S16 : dedup (alarm_log) guards
  S17-S18 : aggregation (multiple tasks → one notification)
  S19-S21 : edge cases (disabled, no due_date, wrong priority)
  S22-S24 : email dispatch details (subject/body, exception swallowed, None guard)
  S25-S27 : overdue message composition (overdue-only, upcoming-only, mixed)
  S28     : _ensure_aware treats naive datetimes as local time (not UTC)
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from agent_core.models.alarm import AlarmChannel, AlarmLeadTime, AlarmSettings
from agent_core.models.deadline import (
    DateType,
    DeadlinePriority,
    DeadlineRecord,
    DeadlineSource,
)
from agent_core.persistence.alarm_store import AlarmStore
from agent_core.persistence.deadline_store import DeadlineStore
from agent_core.services.alarm_service import AlarmService, compute_trigger_time

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_deadline(
    *,
    ddl_id: str = "ddl-1",
    title: str = "HW1",
    due_offset_hours: float = 0.5,
    priority: DeadlinePriority = DeadlinePriority.HIGH,
    date_type: DateType = DateType.MOMENT_HM,
    completed: bool = False,
    created_offset_hours: float = -24.0,
) -> DeadlineRecord:
    """Build a deadline relative to a fixed reference time of 2026-04-15 10:00 UTC."""
    ref = datetime(2026, 4, 15, 10, 0, tzinfo=UTC)
    due = ref + timedelta(hours=due_offset_hours)
    created = ref + timedelta(hours=created_offset_hours)
    return DeadlineRecord(
        id=ddl_id,
        title=title,
        due_date=due,
        created_at=created,
        priority=priority,
        date_type=date_type,
        completed=completed,
        source=DeadlineSource.MANUAL,
    )


NOW = datetime(2026, 4, 15, 10, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def deadline_store() -> AsyncGenerator[DeadlineStore, None]:
    s = DeadlineStore(":memory:")
    await s.initialize()
    yield s
    await s.close()


@pytest.fixture
async def alarm_store() -> AsyncGenerator[AlarmStore, None]:
    s = AlarmStore(":memory:")
    await s.initialize()
    yield s
    await s.close()


@pytest.fixture
def default_settings() -> AlarmSettings:
    return AlarmSettings(
        enabled=True,
        lead_times=[AlarmLeadTime.HOUR_1, AlarmLeadTime.DAY_1],
        channels=[AlarmChannel.IN_APP],
        enabled_priorities=[DeadlinePriority.HIGH, DeadlinePriority.MEDIUM],
    )


@pytest.fixture
async def svc(
    deadline_store: DeadlineStore,
    alarm_store: AlarmStore,
    default_settings: AlarmSettings,
) -> AlarmService:
    await alarm_store.save_settings(default_settings)
    return AlarmService(deadline_store, alarm_store)


# ---------------------------------------------------------------------------
# S1-S4: compute_trigger_time
# ---------------------------------------------------------------------------


class TestComputeTriggerTime:
    """Pure function tests for compute_trigger_time."""

    def test_day_based_moment_day(self) -> None:
        """S1: Day-based lead time works for day-precision tasks."""
        due = datetime(2026, 4, 15, 0, 0, tzinfo=UTC)
        trigger = compute_trigger_time(due, AlarmLeadTime.DAY_1, DateType.MOMENT_DAY)
        assert trigger == due - timedelta(days=1)

    def test_hour_based_hm_precision(self) -> None:
        """S2: Hour-based lead time works for hm-precision tasks."""
        due = datetime(2026, 4, 15, 14, 0, tzinfo=UTC)
        trigger = compute_trigger_time(due, AlarmLeadTime.HOUR_1, DateType.MOMENT_HM)
        assert trigger == due - timedelta(hours=1)

    def test_hour_based_day_precision_returns_none(self) -> None:
        """S3: Hour-based lead time for day-precision task → None."""
        due = datetime(2026, 4, 15, 0, 0, tzinfo=UTC)
        trigger = compute_trigger_time(due, AlarmLeadTime.HOUR_1, DateType.MOMENT_DAY)
        assert trigger is None

    def test_no_due_date_returns_none(self) -> None:
        """S4: Missing due_date → None regardless of lead_time."""
        trigger = compute_trigger_time(None, AlarmLeadTime.DAY_1, DateType.NO_DATE)
        assert trigger is None


# ---------------------------------------------------------------------------
# S5-S12: check_and_dispatch filtering
# ---------------------------------------------------------------------------


class TestCheckAndDispatch:
    """Integration-style tests for AlarmService.check_and_dispatch."""

    @pytest.mark.asyncio
    async def test_fires_notification_for_due_task(
        self,
        svc: AlarmService,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
    ) -> None:
        """S5: A task due in 30 min fires with HOUR_1 lead time."""
        ddl = _make_deadline(due_offset_hours=0.5)  # due 30 min from NOW
        await deadline_store.add(ddl)
        await svc.check_and_dispatch(NOW)
        notifications = await alarm_store.get_pending_notifications()
        assert len(notifications) == 1

    @pytest.mark.asyncio
    async def test_no_notification_for_future_task(
        self,
        svc: AlarmService,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
    ) -> None:
        """S6: A task due in 25 hours does NOT fire with HOUR_1 lead time."""
        ddl = _make_deadline(due_offset_hours=25)
        await deadline_store.add(ddl)
        await svc.check_and_dispatch(NOW)
        notifications = await alarm_store.get_pending_notifications()
        assert len(notifications) == 0

    @pytest.mark.asyncio
    async def test_completed_task_skipped(
        self,
        svc: AlarmService,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
    ) -> None:
        """S7: Completed tasks never trigger alarms."""
        ddl = _make_deadline(due_offset_hours=0.5, completed=True)
        await deadline_store.add(ddl)
        await svc.check_and_dispatch(NOW)
        assert await alarm_store.get_pending_notifications() == []

    @pytest.mark.asyncio
    async def test_wrong_priority_skipped(
        self,
        svc: AlarmService,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
    ) -> None:
        """S8: Low-priority task not in enabled_priorities is skipped."""
        ddl = _make_deadline(due_offset_hours=0.5, priority=DeadlinePriority.LOW)
        await deadline_store.add(ddl)
        await svc.check_and_dispatch(NOW)
        assert await alarm_store.get_pending_notifications() == []

    @pytest.mark.asyncio
    async def test_no_due_date_skipped(
        self,
        svc: AlarmService,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
    ) -> None:
        """S9: Task with no due_date is skipped."""
        ddl = DeadlineRecord(
            id="no-date",
            title="No date",
            due_date=None,
            created_at=datetime(2026, 4, 14, tzinfo=UTC),
            date_type=DateType.NO_DATE,
            priority=DeadlinePriority.HIGH,
            source=DeadlineSource.MANUAL,
        )
        await deadline_store.add(ddl)
        await svc.check_and_dispatch(NOW)
        assert await alarm_store.get_pending_notifications() == []

    @pytest.mark.asyncio
    async def test_overdue_imported_task_skipped(
        self,
        svc: AlarmService,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
    ) -> None:
        """S10: Task where due_date <= created_at (imported-overdue) is skipped."""
        ddl = DeadlineRecord(
            id="overdue",
            title="Old Task",
            due_date=datetime(2026, 4, 14, 10, 0, tzinfo=UTC),  # in the past
            created_at=datetime(2026, 4, 15, 9, 0, tzinfo=UTC),  # created after due
            date_type=DateType.MOMENT_HM,
            priority=DeadlinePriority.HIGH,
            source=DeadlineSource.MANUAL,
        )
        await deadline_store.add(ddl)
        await svc.check_and_dispatch(NOW)
        assert await alarm_store.get_pending_notifications() == []

    @pytest.mark.asyncio
    async def test_null_created_at_skipped(
        self,
        svc: AlarmService,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
    ) -> None:
        """S11: Task with created_at=None is skipped (legacy data guard)."""
        ddl = DeadlineRecord(
            id="legacy",
            title="Legacy",
            due_date=NOW + timedelta(minutes=30),
            created_at=None,  # legacy null
            date_type=DateType.MOMENT_HM,
            priority=DeadlinePriority.HIGH,
            source=DeadlineSource.MANUAL,
        )
        await deadline_store.add(ddl)
        await svc.check_and_dispatch(NOW)
        assert await alarm_store.get_pending_notifications() == []

    @pytest.mark.asyncio
    async def test_disabled_skips_all(
        self,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
    ) -> None:
        """S12: Disabled alarm settings → no notifications dispatched."""
        await alarm_store.save_settings(
            AlarmSettings(
                enabled=False,
                lead_times=[AlarmLeadTime.HOUR_1],
                channels=[AlarmChannel.IN_APP],
                enabled_priorities=[DeadlinePriority.HIGH],
            )
        )
        svc = AlarmService(deadline_store, alarm_store)
        ddl = _make_deadline(due_offset_hours=0.5)
        await deadline_store.add(ddl)
        await svc.check_and_dispatch(NOW)
        assert await alarm_store.get_pending_notifications() == []


# ---------------------------------------------------------------------------
# S13-S16: dedup (alarm_log)
# ---------------------------------------------------------------------------


class TestAlarmDedup:
    """S13-S16: alarm_log prevents re-sending."""

    @pytest.mark.asyncio
    async def test_no_duplicate_notification(
        self,
        svc: AlarmService,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
    ) -> None:
        """S13: Running check_and_dispatch twice only creates ONE notification."""
        ddl = _make_deadline(due_offset_hours=0.5)
        await deadline_store.add(ddl)
        await svc.check_and_dispatch(NOW)
        await svc.check_and_dispatch(NOW)
        notifications = await alarm_store.get_pending_notifications()
        assert len(notifications) == 1

    @pytest.mark.asyncio
    async def test_alarm_log_recorded(
        self,
        svc: AlarmService,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
    ) -> None:
        """S14: After dispatch, alarm_log contains (deadline_id, lead_time)."""
        ddl = _make_deadline(due_offset_hours=0.5)
        await deadline_store.add(ddl)
        await svc.check_and_dispatch(NOW)
        assert await alarm_store.is_alarm_sent(ddl.id, AlarmLeadTime.HOUR_1) is True

    @pytest.mark.asyncio
    async def test_only_matching_lead_time_recorded(
        self,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
    ) -> None:
        """S15: Only the lead_time that triggered is recorded in alarm_log."""
        # Task due in 36 h: WEEK_1 trigger fired (due - 7d = 132 h ago);
        # HOUR_1 trigger has NOT fired (due - 1h = 35 h from now).
        settings = AlarmSettings(
            enabled=True,
            lead_times=[AlarmLeadTime.HOUR_1, AlarmLeadTime.WEEK_1],
            channels=[AlarmChannel.IN_APP],
            enabled_priorities=[DeadlinePriority.HIGH],
        )
        await alarm_store.save_settings(settings)
        svc2 = AlarmService(deadline_store, alarm_store)
        ddl = _make_deadline(due_offset_hours=36)
        await deadline_store.add(ddl)
        await svc2.check_and_dispatch(NOW)
        assert await alarm_store.is_alarm_sent(ddl.id, AlarmLeadTime.WEEK_1) is True
        assert await alarm_store.is_alarm_sent(ddl.id, AlarmLeadTime.HOUR_1) is False

    @pytest.mark.asyncio
    async def test_ack_then_no_new_notification(
        self,
        svc: AlarmService,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
    ) -> None:
        """S16: After ack, alarm_log still guards — no second notification."""
        ddl = _make_deadline(due_offset_hours=0.5)
        await deadline_store.add(ddl)
        await svc.check_and_dispatch(NOW)
        # User acknowledges
        notifications = await alarm_store.get_pending_notifications()
        for n in notifications:
            await alarm_store.ack_notification(n.id)
        # Next poll — alarm_log still exists → no new notification
        await svc.check_and_dispatch(NOW)
        assert await alarm_store.get_pending_notifications() == []


# ---------------------------------------------------------------------------
# S17-S18: aggregation
# ---------------------------------------------------------------------------


class TestAggregation:
    """S17-S18: multiple tasks → ONE in-app notification."""

    @pytest.mark.asyncio
    async def test_two_tasks_one_notification(
        self,
        svc: AlarmService,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
    ) -> None:
        """S17: Two eligible tasks fire → exactly one in-app notification."""
        for i in range(2):
            ddl = _make_deadline(
                ddl_id=f"ddl-{i}", title=f"Task {i}", due_offset_hours=0.5
            )
            await deadline_store.add(ddl)
        await svc.check_and_dispatch(NOW)
        notifications = await alarm_store.get_pending_notifications()
        assert len(notifications) == 1

    @pytest.mark.asyncio
    async def test_email_channel_called_once(
        self,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
        default_settings: AlarmSettings,
    ) -> None:
        """S18: EMAIL channel dispatched once even for two tasks."""
        settings = default_settings.model_copy(
            update={"channels": [AlarmChannel.EMAIL, AlarmChannel.IN_APP]}
        )
        await alarm_store.save_settings(settings)
        send_mock = AsyncMock()
        svc = AlarmService(deadline_store, alarm_store, send_email_fn=send_mock)
        for i in range(2):
            ddl = _make_deadline(
                ddl_id=f"ddl-{i}", title=f"Task {i}", due_offset_hours=0.5
            )
            await deadline_store.add(ddl)
        await svc.check_and_dispatch(NOW)
        # Email sent exactly once
        assert send_mock.call_count == 1
        # In-app also created
        assert len(await alarm_store.get_pending_notifications()) == 1


# ---------------------------------------------------------------------------
# S19-S21: edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """S19-S21: boundary / edge cases."""

    @pytest.mark.asyncio
    async def test_empty_deadlines_no_notification(
        self,
        svc: AlarmService,
        alarm_store: AlarmStore,
    ) -> None:
        """S19: No deadlines → no notifications."""
        await svc.check_and_dispatch(NOW)
        assert await alarm_store.get_pending_notifications() == []

    @pytest.mark.asyncio
    async def test_period_hm_task_fires_hour_lead(
        self,
        svc: AlarmService,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
    ) -> None:
        """S20: PERIOD_HM task with HOUR_1 lead time fires correctly."""
        ddl = _make_deadline(due_offset_hours=0.5, date_type=DateType.PERIOD_HM)
        await deadline_store.add(ddl)
        await svc.check_and_dispatch(NOW)
        assert len(await alarm_store.get_pending_notifications()) == 1

    @pytest.mark.asyncio
    async def test_period_day_task_skips_hour_lead(
        self,
        svc: AlarmService,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
    ) -> None:
        """S21: PERIOD_DAY task does NOT fire for hour-based lead times."""
        # Only HOUR_1 and HOUR_3 in settings; task is 30 min away with day precision
        await alarm_store.save_settings(
            AlarmSettings(
                enabled=True,
                lead_times=[AlarmLeadTime.HOUR_1],
                channels=[AlarmChannel.IN_APP],
                enabled_priorities=[DeadlinePriority.HIGH],
            )
        )
        svc2 = AlarmService(deadline_store, alarm_store)
        ddl = _make_deadline(due_offset_hours=0.5, date_type=DateType.PERIOD_DAY)
        await deadline_store.add(ddl)
        await svc2.check_and_dispatch(NOW)
        assert await alarm_store.get_pending_notifications() == []


# ---------------------------------------------------------------------------
# S22-S24: email dispatch details
# ---------------------------------------------------------------------------


class TestEmailDispatch:
    """S22-S24: email subject/body content, exception handling, None guard."""

    @pytest.mark.asyncio
    async def test_email_subject_and_body(
        self,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
        default_settings: AlarmSettings,
    ) -> None:
        """S22: send_email_fn receives correct subject and body."""
        settings = default_settings.model_copy(
            update={"channels": [AlarmChannel.EMAIL]}
        )
        await alarm_store.save_settings(settings)
        send_mock = AsyncMock()
        svc = AlarmService(deadline_store, alarm_store, send_email_fn=send_mock)
        ddl = _make_deadline(title="Report Due", due_offset_hours=0.5)
        await deadline_store.add(ddl)
        await svc.check_and_dispatch(NOW)
        assert send_mock.call_count == 1
        subject, body = send_mock.call_args.args
        assert subject == "DDL Reminder"
        assert "Report Due" in body
        assert "You have 1 upcoming deadline(s)" in body

    @pytest.mark.asyncio
    async def test_email_exception_swallowed(
        self,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
        default_settings: AlarmSettings,
    ) -> None:
        """S23: Exception raised in send_email_fn is caught; dispatch does not crash."""
        settings = default_settings.model_copy(
            update={"channels": [AlarmChannel.EMAIL, AlarmChannel.IN_APP]}
        )
        await alarm_store.save_settings(settings)
        send_mock = AsyncMock(side_effect=RuntimeError("SMTP down"))
        svc = AlarmService(deadline_store, alarm_store, send_email_fn=send_mock)
        ddl = _make_deadline(due_offset_hours=0.5)
        await deadline_store.add(ddl)
        # Must not raise; in-app notification still created
        await svc.check_and_dispatch(NOW)
        assert len(await alarm_store.get_pending_notifications()) == 1

    @pytest.mark.asyncio
    async def test_email_none_fn_no_crash(
        self,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
        default_settings: AlarmSettings,
    ) -> None:
        """S24: send_email_fn=None with EMAIL channel logs warning, no exception."""
        settings = default_settings.model_copy(
            update={"channels": [AlarmChannel.EMAIL, AlarmChannel.IN_APP]}
        )
        await alarm_store.save_settings(settings)
        # No send_email_fn provided (default None)
        svc = AlarmService(deadline_store, alarm_store)
        ddl = _make_deadline(due_offset_hours=0.5)
        await deadline_store.add(ddl)
        # Must not raise; in-app notification still created despite missing email fn
        await svc.check_and_dispatch(NOW)
        assert len(await alarm_store.get_pending_notifications()) == 1

    @pytest.mark.asyncio
    async def test_email_only_failure_does_not_mark_sent(
        self,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
        default_settings: AlarmSettings,
    ) -> None:
        """S25a: EMAIL-only channel fails → pairs NOT marked sent; next poll retries.

        Regression for the bug where mark_alarm_sent was called unconditionally
        even when every channel failed, permanently silencing EMAIL-only users.
        """
        settings = default_settings.model_copy(
            update={"channels": [AlarmChannel.EMAIL]}
        )
        await alarm_store.save_settings(settings)
        # send_email_fn raises — simulates transient SMTP failure
        send_mock = AsyncMock(side_effect=RuntimeError("SMTP down"))
        svc = AlarmService(deadline_store, alarm_store, send_email_fn=send_mock)
        ddl = _make_deadline(due_offset_hours=0.5)
        await deadline_store.add(ddl)

        await svc.check_and_dispatch(NOW)

        # Alarm must NOT be marked sent — a second dispatch call must retry
        already_sent = await alarm_store.is_alarm_sent(ddl.id, AlarmLeadTime.HOUR_1)
        assert not already_sent, (
            "Pairs must not be marked sent after a failed-only dispatch"
        )

    @pytest.mark.asyncio
    async def test_email_only_no_fn_does_not_mark_sent(
        self,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
        default_settings: AlarmSettings,
    ) -> None:
        """S25b: EMAIL-only channel with no send_email_fn → pairs NOT marked sent.

        Companion to S25a: covers the 'misconfigured but not crashed' path where
        send_email_fn is None rather than raising an exception.
        """
        settings = default_settings.model_copy(
            update={"channels": [AlarmChannel.EMAIL]}
        )
        await alarm_store.save_settings(settings)
        # No send_email_fn provided
        svc = AlarmService(deadline_store, alarm_store)
        ddl = _make_deadline(due_offset_hours=0.5)
        await deadline_store.add(ddl)

        await svc.check_and_dispatch(NOW)

        already_sent = await alarm_store.is_alarm_sent(ddl.id, AlarmLeadTime.HOUR_1)
        assert not already_sent, "Pairs must not be marked sent when email fn is None"


# ---------------------------------------------------------------------------
# S25-S27: overdue message composition
# ---------------------------------------------------------------------------


class TestOverdueMessage:
    """S25-S27: notification message correctly says overdue vs upcoming."""

    @pytest.mark.asyncio
    async def test_overdue_only_message(
        self,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
        default_settings: AlarmSettings,
    ) -> None:
        """S25: All firing tasks are past due → message contains 'overdue'."""
        await alarm_store.save_settings(default_settings)
        svc = AlarmService(deadline_store, alarm_store)
        # due_offset_hours=-1 → task was due 1 hour ago (overdue)
        ddl = _make_deadline(due_offset_hours=-1)
        await deadline_store.add(ddl)
        await svc.check_and_dispatch(NOW)
        notifications = await alarm_store.get_pending_notifications()
        assert len(notifications) == 1
        assert "overdue" in notifications[0].message
        assert "upcoming" not in notifications[0].message
        assert "(OVERDUE)" in notifications[0].details[0]

    @pytest.mark.asyncio
    async def test_upcoming_only_message(
        self,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
        default_settings: AlarmSettings,
    ) -> None:
        """S26: All firing tasks are still in future → message contains 'upcoming'."""
        await alarm_store.save_settings(default_settings)
        svc = AlarmService(deadline_store, alarm_store)
        ddl = _make_deadline(due_offset_hours=0.5)
        await deadline_store.add(ddl)
        await svc.check_and_dispatch(NOW)
        notifications = await alarm_store.get_pending_notifications()
        assert len(notifications) == 1
        assert "upcoming" in notifications[0].message
        assert "overdue" not in notifications[0].message
        assert "(OVERDUE)" not in notifications[0].details[0]

    @pytest.mark.asyncio
    async def test_mixed_overdue_upcoming_message(
        self,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
        default_settings: AlarmSettings,
    ) -> None:
        """S27: Mix of overdue and upcoming → message mentions both counts."""
        await alarm_store.save_settings(default_settings)
        svc = AlarmService(deadline_store, alarm_store)
        ddl_overdue = _make_deadline(
            ddl_id="over-1", title="Old Task", due_offset_hours=-1
        )
        ddl_upcoming = _make_deadline(
            ddl_id="up-1", title="New Task", due_offset_hours=0.5
        )
        await deadline_store.add(ddl_overdue)
        await deadline_store.add(ddl_upcoming)
        await svc.check_and_dispatch(NOW)
        notifications = await alarm_store.get_pending_notifications()
        assert len(notifications) == 1
        assert "overdue" in notifications[0].message
        assert "upcoming" in notifications[0].message


# ---------------------------------------------------------------------------
# S28: _ensure_aware — naive datetimes treated as local time, not UTC
# ---------------------------------------------------------------------------


class TestEnsureAware:
    """S28: _ensure_aware returns a timezone-aware datetime.

    When passed a naive datetime it must call astimezone() so the value is
    interpreted as local system time.  We cannot hard-code the expected UTC
    offset (it varies per CI host), so we verify the contract:
    * The returned value is timezone-aware.
    * An old naive datetime stays in the past after conversion.
    * An already-aware datetime passes through unchanged.
    """

    def test_naive_becomes_aware(self) -> None:
        """S28a: naive input → tzinfo is set after _ensure_aware."""
        from agent_core.services.alarm_service import _ensure_aware

        naive = datetime(2000, 6, 15, 12, 0, 0)
        result = _ensure_aware(naive)
        assert result.tzinfo is not None

    def test_naive_old_date_is_still_in_past(self) -> None:
        """S28b: very old naive datetime remains in the past after conversion."""
        from agent_core.services.alarm_service import _ensure_aware

        naive = datetime(2000, 1, 1, 0, 0, 0)
        aware = _ensure_aware(naive)
        assert aware < datetime.now(aware.tzinfo)

    def test_aware_passthrough(self) -> None:
        """S28c: already-aware datetime is returned unchanged."""
        from agent_core.services.alarm_service import _ensure_aware

        original = datetime(2026, 4, 15, 10, 0, tzinfo=UTC)
        result = _ensure_aware(original)
        assert result is original
