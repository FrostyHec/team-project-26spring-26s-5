"""Alarm scheduler — asyncio background task driving periodic alarm checks.

Runs :meth:`~agent_core.services.alarm_service.AlarmService.check_and_dispatch`
immediately on start, then once every ``POLL_INTERVAL_SECONDS`` seconds.

Usage (managed by :mod:`agent_core.api.dependencies`)::

    scheduler = AlarmScheduler(alarm_service)
    await scheduler.start()   # call from app startup
    # ... app runs ...
    await scheduler.stop()    # call from app shutdown
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import UTC, datetime

from agent_core.logging_utils import get_logger
from agent_core.services.alarm_service import AlarmService

logger = get_logger("services.alarm_scheduler")


class AlarmScheduler:
    """Periodic asyncio background task for deadline alarm checks.

    Attributes:
        POLL_INTERVAL_SECONDS: How often (in seconds) to call
            :meth:`~AlarmService.check_and_dispatch`.  Default is 60 s.
    """

    POLL_INTERVAL_SECONDS: int = 60

    def __init__(self, service: AlarmService) -> None:
        self._service = service
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the background polling task."""
        if self._task is not None and not self._task.done():
            return  # Already running
        self._task = asyncio.create_task(self._loop(), name="alarm-scheduler")
        logger.info("AlarmScheduler started (interval=%ds)", self.POLL_INTERVAL_SECONDS)

    async def stop(self) -> None:
        """Cancel the background task and wait for it to finish."""
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        logger.info("AlarmScheduler stopped")

    async def _loop(self) -> None:
        """Polling loop: fire immediately, then repeat every interval."""
        await self._run_once()
        while True:
            await asyncio.sleep(self.POLL_INTERVAL_SECONDS)
            await self._run_once()

    async def _run_once(self) -> None:
        """Run a single check_and_dispatch cycle, catching all exceptions."""
        try:
            await self._service.check_and_dispatch(datetime.now(UTC))
        except Exception as exc:
            logger.error("Alarm check error: %s", exc, exc_info=True)
