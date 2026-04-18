"""Tests for :class:`AlarmStore`.

Covers CRUD operations for settings, dedup log, and pending notifications.
"""

import pytest

from agent_core.models.alarm import AlarmChannel, AlarmLeadTime, AlarmSettings
from agent_core.models.deadline import DeadlinePriority
from agent_core.persistence.alarm_store import AlarmStore


@pytest.fixture
async def store():
    """In-memory AlarmStore for isolated testing."""
    s = AlarmStore(":memory:")
    await s.initialize()
    yield s
    await s.close()


class TestAlarmSettings:
    """A1 – A2: settings persistence."""

    @pytest.mark.asyncio
    async def test_default_settings(self, store: AlarmStore) -> None:
        """A1: get_settings returns defaults when nothing is stored."""
        settings = await store.get_settings()
        assert settings.enabled is True
        assert AlarmLeadTime.DAY_1 in settings.lead_times
        assert AlarmChannel.IN_APP in settings.channels

    @pytest.mark.asyncio
    async def test_save_and_reload(self, store: AlarmStore) -> None:
        """A2: save_settings persists and get_settings retrieves correctly."""
        custom = AlarmSettings(
            enabled=False,
            lead_times=[AlarmLeadTime.HOUR_6],
            channels=[AlarmChannel.EMAIL],
            enabled_priorities=[DeadlinePriority.HIGH],
        )
        await store.save_settings(custom)
        loaded = await store.get_settings()
        assert loaded.enabled is False
        assert loaded.lead_times == [AlarmLeadTime.HOUR_6]
        assert loaded.channels == [AlarmChannel.EMAIL]


class TestAlarmLog:
    """A3 – A4: dedup log."""

    @pytest.mark.asyncio
    async def test_not_sent_initially(self, store: AlarmStore) -> None:
        """A3: is_alarm_sent returns False before any mark."""
        result = await store.is_alarm_sent("ddl-1", "day_1")
        assert result is False

    @pytest.mark.asyncio
    async def test_mark_then_check(self, store: AlarmStore) -> None:
        """A4: mark_alarm_sent then is_alarm_sent returns True; idempotent."""
        await store.mark_alarm_sent("ddl-1", "day_1")
        assert await store.is_alarm_sent("ddl-1", "day_1") is True
        # Idempotent — should not raise
        await store.mark_alarm_sent("ddl-1", "day_1")
        assert await store.is_alarm_sent("ddl-1", "day_1") is True


class TestPendingNotifications:
    """A5 – A6: pending notifications CRUD."""

    @pytest.mark.asyncio
    async def test_add_and_list(self, store: AlarmStore) -> None:
        """A5: add_pending_notification creates a row; get_pending returns it."""
        nid = await store.add_pending_notification(
            "You have 2 upcoming deadline(s)", ["CS101 HW1 — 2026-04-15 14:00"]
        )
        notifications = await store.get_pending_notifications()
        assert len(notifications) == 1
        assert notifications[0].id == nid
        assert notifications[0].message == "You have 2 upcoming deadline(s)"
        assert len(notifications[0].details) == 1

    @pytest.mark.asyncio
    async def test_ack_removes_notification(self, store: AlarmStore) -> None:
        """A6: ack_notification deletes the row; returns False for unknown id."""
        nid = await store.add_pending_notification("test", [])
        assert await store.ack_notification(nid) is True
        assert await store.get_pending_notifications() == []
        # Unknown id
        assert await store.ack_notification("nonexistent-id") is False
