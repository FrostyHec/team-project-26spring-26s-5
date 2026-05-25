"""News push scheduler — asyncio background task driving daily push checks.

Runs :meth:`~agent_core.services.news_push_service.NewsPushService.check_and_dispatch`
immediately on start, then once every ``POLL_INTERVAL_SECONDS`` seconds.

Usage (managed by :mod:`agent_core.api.dependencies`)::

    scheduler = NewsPushScheduler(news_push_service)
    await scheduler.start()   # call from app startup
    # ... app runs ...
    await scheduler.stop()    # call from app shutdown
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime

from agent_core.logging_utils import get_logger
from agent_core.services.news_push_service import NewsPushService

logger = get_logger("services.news_push_scheduler")


class NewsPushScheduler:
    """Periodic asyncio background task for daily campus news push delivery.

    Attributes:
        POLL_INTERVAL_SECONDS: How often (in seconds) to call
            :meth:`~NewsPushService.check_and_dispatch`. Default is 60 s.
    """

    POLL_INTERVAL_SECONDS: int = 60

    def __init__(self, service: NewsPushService) -> None:
        self._service = service
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the background polling task (idempotent)."""
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop(), name="news-push-scheduler")
        logger.info(
            "NewsPushScheduler started (interval=%ds)", self.POLL_INTERVAL_SECONDS
        )

    async def stop(self) -> None:
        """Cancel the background task and wait for it to finish."""
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        logger.info("NewsPushScheduler stopped")

    async def _loop(self) -> None:
        """Polling loop: fire immediately, then repeat every interval."""
        await self._run_once()
        while True:
            await asyncio.sleep(self.POLL_INTERVAL_SECONDS)
            await self._run_once()

    async def _run_once(self) -> None:
        """Run a single tick, swallowing all exceptions."""
        try:
            await self._service.tick(datetime.now().astimezone())
        except Exception as exc:
            logger.error("News push tick error: %s", exc, exc_info=True)
