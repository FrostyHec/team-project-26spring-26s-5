"""Campus news email push orchestration service.

The service drives two-phase delivery:

1. **Prepare** — Some time before the configured ``push_time`` (default 5
   minutes), generate the daily report via the LLM and persist it to the
   prepared-report cache. This is the slow step (30-90s) and runs entirely
   in the background scheduler.
2. **Dispatch** — At/after ``push_time``, look up the prepared report and
   send the email. This step is fast (SMTP only).

If the app starts after ``push_time`` for the day, both phases run in the
same scheduler tick so the day's push is still delivered.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from datetime import datetime, time, timedelta
from typing import Any

from agent_core.logging_utils import get_logger
from agent_core.models.news import NewsReportResponse
from agent_core.models.news_push import (
    NewsPushSettings,
    NewsPushStatus,
)
from agent_core.persistence.news_push_store import NewsPushStore
from agent_core.services.news_service import NewsService

logger = get_logger("services.news_push")
SendEmailFn = Callable[[str, str], object | Awaitable[object]]


class _FallbackLLM:
    """LLM placeholder that lets NewsService use its fallback report path."""

    async def ainvoke(self, _: object) -> object:
        raise RuntimeError("News push LLM is not configured")


class NewsPushService:
    """Drive daily campus news email delivery with pre-generated reports."""

    #: How many minutes before ``push_time`` to start LLM report generation.
    PREP_LEAD_MINUTES: int = 5

    def __init__(
        self,
        store: NewsPushStore,
        news_service: NewsService,
        send_email_fn: SendEmailFn | None = None,
        llm: Any | None = None,
    ) -> None:
        self._store = store
        self._news_service = news_service
        self._send_email_fn = send_email_fn
        self._llm = llm

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    async def get_settings(self) -> NewsPushSettings:
        """Return persisted news push settings."""
        return await self._store.get_settings()

    async def save_settings(self, settings: NewsPushSettings) -> NewsPushSettings:
        """Persist news push settings and return the saved value."""
        await self._store.save_settings(settings)
        return settings

    # ------------------------------------------------------------------
    # Scheduler entry-point
    # ------------------------------------------------------------------

    async def tick(self, now: datetime) -> None:
        """One scheduler iteration: prepare (if due) then dispatch (if due)."""
        settings = await self._store.get_settings()
        if not settings.enabled:
            return

        target_date = now.date().isoformat()

        await self._ensure_prepared(now, settings, target_date)
        await self._dispatch_if_due(now, settings, target_date)

    # ------------------------------------------------------------------
    # Internal: prepare phase
    # ------------------------------------------------------------------

    async def _ensure_prepared(
        self, now: datetime, settings: NewsPushSettings, target_date: str
    ) -> None:
        """Generate today's report when within the prep window and not yet cached."""
        if not self._is_prep_due(now, settings):
            return
        existing = await self._store.get_prepared_report(target_date)
        if existing is not None:
            return
        try:
            report = await self._create_report(settings, target_date)
        except Exception as exc:
            logger.error(
                "Failed to prepare news push report for %s: %s",
                target_date,
                exc,
                exc_info=True,
            )
            return
        await self._store.save_prepared_report(target_date, report)
        logger.info("Daily news push report prepared for %s", target_date)

    # ------------------------------------------------------------------
    # Internal: dispatch phase
    # ------------------------------------------------------------------

    async def _dispatch_if_due(
        self, now: datetime, settings: NewsPushSettings, target_date: str
    ) -> None:
        """Send today's email if the push time has been reached and not yet sent."""
        if not self._is_push_due(now, settings):
            return
        if not await self._store.try_claim_send(target_date):
            return  # already SUCCESS, or another in-flight claim

        report = await self._store.get_prepared_report(target_date)
        if report is None:
            # Prep did not run (e.g., started past push_due) - generate inline fallback.
            try:
                report = await self._create_report(settings, target_date)
                await self._store.save_prepared_report(target_date, report)
            except Exception as exc:
                logger.error(
                    "News push report generation failed at dispatch: %s",
                    exc,
                    exc_info=True,
                )
                await self._record_send_safely(
                    target_date,
                    NewsPushStatus.FAILED,
                    f"Report generation failed: {exc}",
                )
                return

        try:
            await self._deliver_email(report)
        except Exception as exc:
            logger.warning("News push email failed: %s", exc)
            await self._record_send_safely(target_date, NewsPushStatus.FAILED, str(exc))
            return

        await self._record_send_safely(target_date, NewsPushStatus.SUCCESS)
        logger.info("Daily news push email sent for %s", target_date)

    async def _record_send_safely(
        self, target_date: str, status: NewsPushStatus, error: str = ""
    ) -> None:
        try:
            await self._store.record_send(target_date, status, error=error)
        except Exception:
            logger.exception(
                "Failed to record news push delivery status for %s.", target_date
            )

    # ------------------------------------------------------------------
    # Internal: report & email helpers
    # ------------------------------------------------------------------

    async def _create_report(
        self, settings: NewsPushSettings, target_date: str
    ) -> NewsReportResponse:
        # Daily push always reports today's news from all sources; user-side
        # filters only apply to widget browsing, not the digest.
        return await self._news_service.create_ai_report(
            llm=self._llm or _FallbackLLM(),
            target_date=target_date,
            query=None,
            source="all",
            limit=settings.limit,
        )

    async def _deliver_email(self, report: NewsReportResponse) -> None:
        if self._send_email_fn is None:
            raise RuntimeError("Email delivery is not configured")
        result = self._send_email_fn(
            f"Daily Campus News: {report.title}",
            self._email_body(report),
        )
        if inspect.isawaitable(result):
            await result

    def _email_body(self, report: NewsReportResponse) -> str:
        sections = [report.summary]
        if report.key_points:
            sections.append(
                "Key points:\n" + "\n".join(f"- {point}" for point in report.key_points)
            )
        if report.action_items:
            sections.append(
                "Action items:\n"
                + "\n".join(f"- {item}" for item in report.action_items)
            )
        return "\n\n".join(section for section in sections if section)

    # ------------------------------------------------------------------
    # Internal: timing helpers
    # ------------------------------------------------------------------

    def _is_prep_due(self, now: datetime, settings: NewsPushSettings) -> bool:
        push_at = self._push_datetime_for_day(now, settings)
        prep_at = push_at - timedelta(minutes=self.PREP_LEAD_MINUTES)
        return now >= prep_at

    def _is_push_due(self, now: datetime, settings: NewsPushSettings) -> bool:
        push_at = self._push_datetime_for_day(now, settings)
        return now >= push_at

    @staticmethod
    def _push_datetime_for_day(now: datetime, settings: NewsPushSettings) -> datetime:
        hour_text, minute_text = settings.push_time.split(":", 1)
        push_time = time(int(hour_text), int(minute_text))
        return datetime.combine(now.date(), push_time, tzinfo=now.tzinfo)
