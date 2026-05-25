"""Tests for the campus news email push service."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from agent_core.models.news import NewsReportResponse
from agent_core.models.news_push import (
    NewsPushSettings,
    NewsPushStatus,
)
from agent_core.services.news_push_service import NewsPushService

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeNewsPushStore:
    """In-memory store fake with the NewsPushStore async interface."""

    def __init__(self, settings: NewsPushSettings) -> None:
        self.settings = settings
        self.deliveries: list[tuple[str, NewsPushStatus, str]] = []
        self.successful: set[str] = set()
        self.statuses: dict[str, NewsPushStatus] = {}
        self.prepared: dict[str, NewsReportResponse] = {}
        self.record_failures: set[NewsPushStatus] = set()

    async def get_settings(self) -> NewsPushSettings:
        return self.settings

    async def save_settings(self, settings: NewsPushSettings) -> None:
        self.settings = settings

    async def was_sent(self, target_date: str) -> bool:
        return target_date in self.successful

    async def try_claim_send(self, target_date: str) -> bool:
        if target_date in self.successful:
            return False
        status = self.statuses.get(target_date)
        if status not in (None, NewsPushStatus.FAILED):
            return False
        self.statuses[target_date] = NewsPushStatus.IN_PROGRESS
        return True

    async def record_send(
        self,
        target_date: str,
        status: NewsPushStatus,
        error: str = "",
    ) -> None:
        if status in self.record_failures:
            raise RuntimeError(f"record failed for {status.value}")
        self.deliveries.append((target_date, status, error))
        self.statuses[target_date] = status
        if status == NewsPushStatus.SUCCESS:
            self.successful.add(target_date)

    async def get_prepared_report(self, target_date: str) -> NewsReportResponse | None:
        return self.prepared.get(target_date)

    async def save_prepared_report(
        self, target_date: str, report: NewsReportResponse
    ) -> None:
        self.prepared[target_date] = report


class FakeNewsService:
    """Fake report generator that records the requested report filters."""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self.error = error

    async def create_ai_report(
        self,
        *,
        llm: object,
        target_date: str | None = None,
        query: str | None = None,
        source: str = "all",
        limit: int = 20,
    ) -> NewsReportResponse:
        self.calls.append(
            {
                "llm": llm,
                "target_date": target_date,
                "query": query,
                "source": source,
                "limit": limit,
            }
        )
        if self.error is not None:
            raise self.error
        return NewsReportResponse(
            title=f"{target_date} Campus News Daily",
            generated_at="2026-05-23",
            filter_text="test",
            article_count=1,
            summary="One campus update is ready.",
            key_points=["Library hours changed."],
            action_items=["Check the new schedule."],
        )


def _today(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 5, 23, hour, minute, tzinfo=UTC)


def _make_service(
    *,
    settings: NewsPushSettings | None = None,
    news_service: FakeNewsService | None = None,
    email_sink: list[tuple[str, str]] | None = None,
    email_error: Exception | None = None,
) -> tuple[NewsPushService, FakeNewsPushStore, FakeNewsService, list[tuple[str, str]]]:
    settings = settings or NewsPushSettings(enabled=True, push_time="08:30")
    store = FakeNewsPushStore(settings)
    news = news_service or FakeNewsService()
    emails = email_sink if email_sink is not None else []

    def send_email(subject: str, body: str) -> None:
        if email_error is not None:
            raise email_error
        emails.append((subject, body))

    service = NewsPushService(store, news, send_email_fn=send_email)
    return service, store, news, emails


# ---------------------------------------------------------------------------
# Disabled / not-due paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tick_is_noop_when_disabled() -> None:
    settings = NewsPushSettings(enabled=False, push_time="08:30")
    service, store, news, emails = _make_service(settings=settings)

    await service.tick(_today(9, 0))

    assert news.calls == []
    assert emails == []
    assert store.deliveries == []
    assert store.prepared == {}


@pytest.mark.asyncio
async def test_tick_skips_prep_before_prep_window() -> None:
    # push_time 08:30 -> prep window opens at 08:25
    service, store, news, emails = _make_service()

    await service.tick(_today(8, 24))

    assert news.calls == []
    assert store.prepared == {}
    assert emails == []
    assert store.deliveries == []


# ---------------------------------------------------------------------------
# Prepare phase
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tick_prepares_inside_prep_window_but_does_not_send() -> None:
    service, store, news, emails = _make_service()

    await service.tick(_today(8, 25))

    assert len(news.calls) == 1
    assert news.calls[0]["target_date"] == "2026-05-23"
    assert news.calls[0]["source"] == "all"
    assert news.calls[0]["query"] is None
    assert "2026-05-23" in store.prepared
    assert emails == []
    assert store.deliveries == []


@pytest.mark.asyncio
async def test_tick_does_not_regenerate_when_already_prepared() -> None:
    service, store, news, emails = _make_service()
    await service.tick(_today(8, 25))
    assert len(news.calls) == 1

    await service.tick(_today(8, 27))
    assert len(news.calls) == 1
    assert emails == []


@pytest.mark.asyncio
async def test_failed_prep_does_not_record_send_or_email() -> None:
    failing_news = FakeNewsService(error=RuntimeError("LLM down"))
    service, store, news, emails = _make_service(news_service=failing_news)

    await service.tick(_today(8, 25))

    assert "2026-05-23" not in store.prepared
    assert emails == []
    assert store.deliveries == []  # nothing claimed yet; dispatch wasn't due


# ---------------------------------------------------------------------------
# Dispatch phase
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tick_sends_email_at_push_time_using_prepared_report() -> None:
    service, store, news, emails = _make_service()
    await service.tick(_today(8, 25))  # prep
    assert len(news.calls) == 1

    await service.tick(_today(8, 30))  # dispatch

    assert len(news.calls) == 1  # no LLM re-call at dispatch
    assert len(emails) == 1
    subject, body = emails[0]
    assert subject.startswith("Daily Campus News:")
    assert "One campus update is ready." in body
    assert store.deliveries[-1] == (
        "2026-05-23",
        NewsPushStatus.SUCCESS,
        "",
    )


@pytest.mark.asyncio
async def test_tick_backfills_when_app_starts_after_push_time() -> None:
    """App started at 09:00 with push_time 08:30 — prep+send happen in one tick."""
    service, store, news, emails = _make_service()

    await service.tick(_today(9, 0))

    assert len(news.calls) == 1
    assert len(emails) == 1
    assert store.successful == {"2026-05-23"}


@pytest.mark.asyncio
async def test_tick_inline_generates_when_prepared_report_missing() -> None:
    """If prep failed earlier, the dispatch tick must still try to generate."""
    service, store, news, emails = _make_service()
    # Simulate prep was missed entirely (no prepared row), and we tick after push time.

    await service.tick(_today(8, 31))

    assert len(news.calls) == 1
    assert "2026-05-23" in store.prepared
    assert len(emails) == 1
    assert store.successful == {"2026-05-23"}


@pytest.mark.asyncio
async def test_tick_records_failure_when_email_send_raises() -> None:
    service, store, news, emails = _make_service(
        email_error=RuntimeError("SMTP unavailable")
    )

    await service.tick(_today(8, 31))

    assert news.calls  # report was generated
    assert emails == []  # send failed; sink unchanged
    assert store.deliveries[-1] == (
        "2026-05-23",
        NewsPushStatus.FAILED,
        "SMTP unavailable",
    )


@pytest.mark.asyncio
async def test_tick_records_failure_when_inline_generation_fails() -> None:
    failing_news = FakeNewsService(error=RuntimeError("LLM dead"))
    service, store, news, emails = _make_service(news_service=failing_news)

    await service.tick(_today(8, 31))

    assert emails == []
    assert store.deliveries[-1][0] == "2026-05-23"
    assert store.deliveries[-1][1] == NewsPushStatus.FAILED
    assert "LLM dead" in store.deliveries[-1][2]


@pytest.mark.asyncio
async def test_tick_does_not_resend_after_success() -> None:
    service, store, news, emails = _make_service()
    await service.tick(_today(8, 30))
    assert len(emails) == 1

    await service.tick(_today(8, 31))
    await service.tick(_today(8, 32))

    assert len(emails) == 1


@pytest.mark.asyncio
async def test_concurrent_ticks_only_send_one_email() -> None:
    service, store, news, emails = _make_service()
    # Pre-prepare so dispatch is the only race we exercise.
    await service.tick(_today(8, 25))

    await asyncio.gather(
        service.tick(_today(8, 30)),
        service.tick(_today(8, 30)),
        service.tick(_today(8, 30)),
    )

    assert len(emails) == 1
    assert store.successful == {"2026-05-23"}


# ---------------------------------------------------------------------------
# Settings I/O
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_settings_persists_through_store() -> None:
    service, store, _, _ = _make_service()
    new_settings = NewsPushSettings(enabled=True, push_time="09:30", limit=5)

    saved = await service.save_settings(new_settings)

    assert saved == new_settings
    assert store.settings == new_settings


@pytest.mark.asyncio
async def test_get_settings_returns_store_value() -> None:
    settings = NewsPushSettings(enabled=True, push_time="10:00", limit=3)
    service, _, _, _ = _make_service(settings=settings)

    assert await service.get_settings() == settings
