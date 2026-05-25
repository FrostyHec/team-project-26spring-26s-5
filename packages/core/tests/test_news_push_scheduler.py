"""Tests for the campus news push scheduler."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agent_core.services.news_push_scheduler import NewsPushScheduler


def _make_scheduler(tick: AsyncMock | None = None) -> NewsPushScheduler:
    service = AsyncMock()
    service.tick = tick or AsyncMock()
    return NewsPushScheduler(service)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_run_once_calls_service_tick() -> None:
    """A single run-once cycle invokes the service exactly once."""
    tick = AsyncMock()
    scheduler = _make_scheduler(tick)

    await scheduler._run_once()  # noqa: SLF001

    tick.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_is_idempotent_when_task_is_already_running() -> None:
    """Calling start twice keeps the same background task."""
    scheduler = _make_scheduler()

    await scheduler.start()
    first_task = scheduler._task  # noqa: SLF001
    try:
        await scheduler.start()
        assert scheduler._task is first_task  # noqa: SLF001
    finally:
        await scheduler.stop()


@pytest.mark.asyncio
async def test_run_once_swallows_tick_exceptions() -> None:
    """An error raised by tick must not propagate."""
    tick = AsyncMock(side_effect=RuntimeError("boom"))
    scheduler = _make_scheduler(tick)

    await scheduler._run_once()  # noqa: SLF001

    tick.assert_awaited_once()


@pytest.mark.asyncio
async def test_stop_without_start_is_noop() -> None:
    """Stopping a scheduler that never started must not raise."""
    scheduler = _make_scheduler()

    await scheduler.stop()

    assert scheduler._task is None  # noqa: SLF001
