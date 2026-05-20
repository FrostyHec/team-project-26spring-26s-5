"""Tests for the multi-source campus news aggregation service."""

import pytest

from agent_core.models.news import NewsArticle, NewsArticleDetail, NewsSourceType
from agent_core.services.news_service import NewsService
from agent_core.services.news_sources.mock_source import MockNewsSource


class FakeLLMResponse:
    """Small response object shaped like a LangChain AIMessage for tests."""

    content = (
        '{"summary":"Today focuses on a campus seminar.",'
        '"key_points":["The college published a seminar notice."],'
        '"action_items":["Interested students should review registration details."]}'
    )


class FakeLLM:
    """Small async LLM fake used to verify report generation."""

    def __init__(self) -> None:
        self.calls = 0

    async def ainvoke(self, _: object) -> FakeLLMResponse:
        self.calls += 1
        return FakeLLMResponse()


class FakeEmailSource:
    """Small source adapter used to verify multi-source aggregation."""

    source_type = NewsSourceType.EMAIL

    async def list_articles(self, *, limit: int = 50) -> list[NewsArticle]:
        return [
            NewsArticle(
                id="email-10",
                title="Campus seminar from email",
                date="2026-04-10",
                category="event",
                summary="A seminar announcement from the mailbox.",
                source="Campus Office",
                source_type=NewsSourceType.EMAIL,
                source_name="Campus Office",
                source_id="office@example.edu",
                external_id="10",
                tags=["email", "seminar"],
            )
        ][:limit]

    async def get_article_detail(self, news_id: str) -> NewsArticleDetail | None:
        if news_id != "email-10":
            return None
        return NewsArticleDetail(
            id="email-10",
            title="Campus seminar from email",
            date="2026-04-10",
            category="event",
            summary="A seminar announcement from the mailbox.",
            source="Campus Office",
            source_type=NewsSourceType.EMAIL,
            content="Full email-derived seminar content.",
        )


@pytest.mark.asyncio
async def test_news_service_aggregates_sources() -> None:
    service = NewsService([MockNewsSource(), FakeEmailSource()])

    payload = await service.list_articles(limit=20)

    ids = {article.id for article in payload.articles}
    assert "news-002" in ids
    assert "email-10" in ids


@pytest.mark.asyncio
async def test_news_service_filters_query_and_date() -> None:
    service = NewsService([MockNewsSource(), FakeEmailSource()])

    payload = await service.list_articles(
        target_date="2026-04-10",
        query="seminar",
        limit=20,
    )

    assert payload.mode == "search"
    assert payload.date == "2026-04-10"
    assert [article.id for article in payload.articles] == ["email-10"]


@pytest.mark.asyncio
async def test_news_service_dispatches_detail_to_source() -> None:
    service = NewsService([MockNewsSource(), FakeEmailSource()])

    detail = await service.get_article_detail("email-10")

    assert detail is not None
    assert detail.content == "Full email-derived seminar content."


@pytest.mark.asyncio
async def test_news_service_creates_latest_available_digest() -> None:
    service = NewsService([MockNewsSource(), FakeEmailSource()])

    digest = await service.create_digest(target_date="2099-01-01", limit=2)

    assert digest.mode == "latest_available"
    assert digest.headline_count == 2


@pytest.mark.asyncio
async def test_news_service_creates_ai_report() -> None:
    service = NewsService([FakeEmailSource()])
    llm = FakeLLM()

    report = await service.create_ai_report(
        llm=llm,
        target_date="2026-04-10",
        query="seminar",
    )

    assert llm.calls == 1
    assert report.article_count == 1
    assert report.summary == "Today focuses on a campus seminar."
    assert report.key_points == ["The college published a seminar notice."]
    assert report.action_items == [
        "Interested students should review registration details."
    ]
    assert report.articles[0].id == "email-10"
