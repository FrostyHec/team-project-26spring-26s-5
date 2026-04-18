"""Unit tests for AlarmScheduler.

Tests cover:
  SC1 : check_and_dispatch is called immediately on start()
  SC2 : check_and_dispatch is called again after POLL_INTERVAL_SECONDS
  SC3 : stop() cancels the background task cleanly (no CancelledError propagates)
  SC4 : start() is idempotent — calling twice does not create a second task
  SC5 : exceptions inside check_and_dispatch are swallowed (scheduler keeps running)
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from agent_core.services.alarm_scheduler import AlarmScheduler


def _make_scheduler(dispatch_fn: AsyncMock | None = None) -> AlarmScheduler:
    """Return an AlarmScheduler backed by a mock AlarmService."""
    mock_service = AsyncMock()
    mock_service.check_and_dispatch = dispatch_fn or AsyncMock()
    return AlarmScheduler(mock_service)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# SC1: immediate first call on start()
# ---------------------------------------------------------------------------


class TestImmediateStart:
    """SC1: check_and_dispatch is invoked once immediately after start()."""

    @pytest.mark.asyncio
    async def test_dispatch_called_on_start(self) -> None:
        """SC1: First check_and_dispatch fires before any sleep.

        The _loop() coroutine calls _run_once() before its first
        asyncio.sleep(POLL_INTERVAL_SECONDS).  A single event-loop yield
        (``await asyncio.sleep(0)``) is enough to let the task reach that
        first call — the 60-second sleep then suspends the task for the
        remainder of the test, so the count stays at exactly 1.
        """
        dispatch = AsyncMock()
        scheduler = _make_scheduler(dispatch)

        await scheduler.start()
        # One yield hands control to the background task; it runs _run_once()
        # then blocks on asyncio.sleep(60) — control returns here.
        await asyncio.sleep(0)

        dispatch.assert_called_once()
        await scheduler.stop()


# ---------------------------------------------------------------------------
# SC2: periodic call after interval
# ---------------------------------------------------------------------------


class TestPeriodicCall:
    """SC2: check_and_dispatch fires again after POLL_INTERVAL_SECONDS."""

    @pytest.mark.asyncio
    async def test_dispatch_called_periodically(self) -> None:
        """SC2: Two iterations → check_and_dispatch called at least twice.

        Uses a very short real interval (0.05 s) so the test completes in
        ~0.15 s without any mocking of asyncio internals.
        """
        dispatch = AsyncMock()
        scheduler = _make_scheduler(dispatch)
        # Shrink the interval so the test finishes fast
        scheduler.POLL_INTERVAL_SECONDS = 0.05  # type: ignore[assignment]

        await scheduler.start()
        # Wait long enough for at least 2 intervals to elapse
        await asyncio.sleep(0.18)
        await scheduler.stop()

        assert dispatch.call_count >= 2


# ---------------------------------------------------------------------------
# SC3: stop() cancels cleanly
# ---------------------------------------------------------------------------


class TestStop:
    """SC3: stop() cancels the background task without raising."""

    @pytest.mark.asyncio
    async def test_stop_does_not_raise(self) -> None:
        """SC3: stop() completes without any exception."""
        scheduler = _make_scheduler()

        await scheduler.start()
        await asyncio.sleep(0)  # Let the task reach its first sleep
        await scheduler.stop()  # Must not raise

        assert scheduler._task is None  # noqa: SLF001 — verifying internal cleanup

    @pytest.mark.asyncio
    async def test_stop_before_start_is_noop(self) -> None:
        """SC3b: stop() on a never-started scheduler is a no-op."""
        scheduler = _make_scheduler()
        await scheduler.stop()  # Should not raise


# ---------------------------------------------------------------------------
# SC4: start() idempotency
# ---------------------------------------------------------------------------


class TestIdempotentStart:
    """SC4: calling start() twice does not create a second background task."""

    @pytest.mark.asyncio
    async def test_second_start_is_noop(self) -> None:
        """SC4: start() twice → only one asyncio.Task created."""
        scheduler = _make_scheduler()
        await scheduler.start()
        first_task = scheduler._task  # noqa: SLF001

        await scheduler.start()  # Second call — must be idempotent
        assert scheduler._task is first_task  # noqa: SLF001

        await scheduler.stop()


# ---------------------------------------------------------------------------
# SC5: exception inside check_and_dispatch is swallowed
# ---------------------------------------------------------------------------


class TestExceptionHandling:
    """SC5: exceptions inside check_and_dispatch do not crash the scheduler."""

    @pytest.mark.asyncio
    async def test_exception_in_run_once_is_swallowed(self) -> None:
        """SC5a: RuntimeError in check_and_dispatch is caught by _run_once.

        Tests _run_once() directly: the method must not propagate the
        exception, and the mock must have been called exactly once.
        """
        dispatch = AsyncMock(side_effect=RuntimeError("transient error"))
        scheduler = _make_scheduler(dispatch)

        # _run_once must swallow the exception — if it doesn't, the test fails
        await scheduler._run_once()  # noqa: SLF001
        dispatch.assert_called_once()

    @pytest.mark.asyncio
    async def test_scheduler_survives_exception_and_retries(self) -> None:
        """SC5b: After a failed dispatch, the scheduler continues polling.

        Uses a very short real interval so the retry happens quickly.
        """
        call_count = 0

        async def flaky_dispatch(*_args: object, **_kwargs: object) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("first call fails")
            # Subsequent calls succeed (return normally)

        mock_service = AsyncMock()
        mock_service.check_and_dispatch = flaky_dispatch
        scheduler = AlarmScheduler(mock_service)  # type: ignore[arg-type]
        scheduler.POLL_INTERVAL_SECONDS = 0.05  # type: ignore[assignment]

        await scheduler.start()
        # Wait for the first call (immediate) + at least one retry
        await asyncio.sleep(0.18)
        await scheduler.stop()

        # Scheduler must have retried after the first failure
        assert call_count >= 2
