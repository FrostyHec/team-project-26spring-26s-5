"""Tests for campus news push models and persistence."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent_core.models.news import NewsReportArticleRef, NewsReportResponse
from agent_core.models.news_push import (
    NewsPushSettings,
    NewsPushStatus,
)
from agent_core.persistence.news_push_store import NewsPushStore

# ---------------------------------------------------------------------------
# Settings model
# ---------------------------------------------------------------------------


def test_news_push_settings_defaults() -> None:
    """News push settings default to a disabled email push at 08:30."""
    settings = NewsPushSettings()

    assert settings.enabled is False
    assert settings.push_time == "08:30"
    assert settings.limit == 20


def test_news_push_settings_rejects_invalid_time() -> None:
    """Push time must be a valid HH:MM clock time."""
    with pytest.raises(ValidationError, match="push_time"):
        NewsPushSettings(push_time="24:00")


def test_news_push_settings_rejects_invalid_limit() -> None:
    """Push limit must stay within the supported range."""
    with pytest.raises(ValidationError):
        NewsPushSettings(limit=0)

    with pytest.raises(ValidationError):
        NewsPushSettings(limit=51)


# ---------------------------------------------------------------------------
# Settings persistence
# ---------------------------------------------------------------------------


async def test_news_push_store_returns_default_settings(tmp_path) -> None:
    """Store returns default settings when none have been saved."""
    store = NewsPushStore(str(tmp_path / "sessions.db"))
    await store.initialize()
    try:
        assert await store.get_settings() == NewsPushSettings()
    finally:
        await store.close()


async def test_news_push_store_saves_and_loads_settings(tmp_path) -> None:
    """Store persists settings across connections."""
    db_path = str(tmp_path / "sessions.db")
    settings = NewsPushSettings(enabled=True, push_time="09:15", limit=10)

    store = NewsPushStore(db_path)
    await store.initialize()
    try:
        await store.save_settings(settings)
    finally:
        await store.close()

    reopened = NewsPushStore(db_path)
    await reopened.initialize()
    try:
        assert await reopened.get_settings() == settings
    finally:
        await reopened.close()


# ---------------------------------------------------------------------------
# Delivery log
# ---------------------------------------------------------------------------


async def test_try_claim_send_succeeds_when_no_row(tmp_path) -> None:
    """An unclaimed date can be claimed (writes an IN_PROGRESS row)."""
    store = NewsPushStore(str(tmp_path / "sessions.db"))
    await store.initialize()
    try:
        claimed = await store.try_claim_send("2026-05-23")
        log = await store.list_log()
    finally:
        await store.close()

    assert claimed is True
    assert len(log) == 1
    assert log[0].target_date == "2026-05-23"
    assert log[0].status == NewsPushStatus.IN_PROGRESS


async def test_try_claim_send_rejects_when_already_success(tmp_path) -> None:
    """Already-successful sends cannot be claimed again."""
    store = NewsPushStore(str(tmp_path / "sessions.db"))
    await store.initialize()
    try:
        await store.record_send("2026-05-23", NewsPushStatus.SUCCESS)

        claimed = await store.try_claim_send("2026-05-23")
        log = await store.list_log()
    finally:
        await store.close()

    assert claimed is False
    assert log[0].status == NewsPushStatus.SUCCESS


async def test_try_claim_send_allows_retry_after_failure(tmp_path) -> None:
    """A FAILED row can be reclaimed as IN_PROGRESS."""
    store = NewsPushStore(str(tmp_path / "sessions.db"))
    await store.initialize()
    try:
        await store.record_send("2026-05-23", NewsPushStatus.FAILED, "smtp down")

        claimed = await store.try_claim_send("2026-05-23")
        log = await store.list_log()
    finally:
        await store.close()

    assert claimed is True
    assert len(log) == 1
    assert log[0].status == NewsPushStatus.IN_PROGRESS
    assert log[0].error == ""


async def test_was_sent_only_true_for_success(tmp_path) -> None:
    """was_sent only returns True for SUCCESS rows."""
    store = NewsPushStore(str(tmp_path / "sessions.db"))
    await store.initialize()
    try:
        assert await store.was_sent("2026-05-23") is False

        await store.record_send("2026-05-23", NewsPushStatus.FAILED, "smtp")
        assert await store.was_sent("2026-05-23") is False

        await store.record_send("2026-05-23", NewsPushStatus.SUCCESS)
        assert await store.was_sent("2026-05-23") is True
    finally:
        await store.close()


async def test_record_send_does_not_downgrade_success(tmp_path) -> None:
    """A later FAILED record must not overwrite a SUCCESS row."""
    store = NewsPushStore(str(tmp_path / "sessions.db"))
    await store.initialize()
    try:
        await store.record_send("2026-05-23", NewsPushStatus.SUCCESS)
        await store.record_send("2026-05-23", NewsPushStatus.FAILED, "later flake")

        assert await store.was_sent("2026-05-23") is True
        log = await store.list_log()
    finally:
        await store.close()

    assert len(log) == 1
    assert log[0].status == NewsPushStatus.SUCCESS
    assert log[0].error == ""


# ---------------------------------------------------------------------------
# Prepared report cache
# ---------------------------------------------------------------------------


def _sample_report() -> NewsReportResponse:
    return NewsReportResponse(
        title="2026-05-23 Campus News Daily",
        generated_at="2026-05-23",
        filter_text="2026-05-23 | all",
        article_count=1,
        summary="One campus update today.",
        key_points=["Library hours changed."],
        action_items=["Check the new schedule."],
        articles=[
            NewsReportArticleRef(
                id="news-1",
                title="Library hours change",
                date="2026-05-23",
                category="announcement",
                source="Campus Comms",
                source_type="mock",
                summary="Library hours have shifted.",
            )
        ],
    )


async def test_get_prepared_report_returns_none_when_absent(tmp_path) -> None:
    """A target date with no prepared row returns None."""
    store = NewsPushStore(str(tmp_path / "sessions.db"))
    await store.initialize()
    try:
        assert await store.get_prepared_report("2026-05-23") is None
    finally:
        await store.close()


async def test_save_and_load_prepared_report_round_trips(tmp_path) -> None:
    """A saved report can be reloaded byte-for-byte."""
    report = _sample_report()
    store = NewsPushStore(str(tmp_path / "sessions.db"))
    await store.initialize()
    try:
        await store.save_prepared_report("2026-05-23", report)
        loaded = await store.get_prepared_report("2026-05-23")
    finally:
        await store.close()

    assert loaded == report


async def test_save_prepared_report_upserts(tmp_path) -> None:
    """Re-saving for the same date overwrites the previous report."""
    first = _sample_report()
    second = first.model_copy(update={"summary": "Updated summary."})

    store = NewsPushStore(str(tmp_path / "sessions.db"))
    await store.initialize()
    try:
        await store.save_prepared_report("2026-05-23", first)
        await store.save_prepared_report("2026-05-23", second)
        loaded = await store.get_prepared_report("2026-05-23")
    finally:
        await store.close()

    assert loaded is not None
    assert loaded.summary == "Updated summary."
