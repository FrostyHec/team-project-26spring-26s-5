"""Tests for campus news tools."""

import json

import pytest

from agent_core.tools.news import (
    create_news_digest,
    get_daily_news,
    get_latest_news,
    get_news_detail,
    register_news_tools,
    search_news,
)
from agent_core.tools.registry import ToolRegistry


class TestCampusNewsTools:
    """Test suite for mocked campus news tools."""

    def setup_method(self) -> None:
        """Register campus news tools for each test."""
        self.registry = ToolRegistry()
        register_news_tools(self.registry)

    def test_all_tools_registered(self) -> None:
        """Test that all campus news tools are registered."""
        tools = self.registry.list_tools()
        names = {t.name for t in tools}
        assert names == {
            "get_latest_news",
            "get_daily_news",
            "search_news",
            "get_news_detail",
            "create_news_digest",
        }

    @pytest.mark.asyncio
    async def test_get_latest_news(self) -> None:
        """Test fetching latest mocked campus news."""
        result = await get_latest_news(limit=2)
        articles = json.loads(result)

        assert len(articles) == 2
        assert articles[0]["date"] >= articles[1]["date"]
        assert "content" not in articles[0]

    @pytest.mark.asyncio
    async def test_get_daily_news(self) -> None:
        """Test fetching news for a specific date."""
        result = await get_daily_news(target_date="2026-04-11")
        payload = json.loads(result)

        assert payload["date"] == "2026-04-11"
        assert any(article["id"] == "news-001" for article in payload["articles"])

    @pytest.mark.asyncio
    async def test_search_news(self) -> None:
        """Test keyword search against mocked campus news."""
        result = await search_news(query="career", limit=5)
        articles = json.loads(result)

        assert any(article["id"] == "news-002" for article in articles)

    @pytest.mark.asyncio
    async def test_get_news_detail(self) -> None:
        """Test fetching one full mocked article by id."""
        result = await get_news_detail(news_id="news-001")
        article = json.loads(result)

        assert article["id"] == "news-001"
        assert "content" in article

    @pytest.mark.asyncio
    async def test_get_news_detail_missing(self) -> None:
        """Test missing article lookup returns an error object."""
        result = await get_news_detail(news_id="missing-news")
        payload = json.loads(result)

        assert "error" in payload

    @pytest.mark.asyncio
    async def test_create_news_digest(self) -> None:
        """Test daily campus news digest generation."""
        result = await create_news_digest(target_date="2026-04-11", limit=5)
        digest = json.loads(result)

        assert digest["widget_type"] == "news_digest"
        assert digest["date"] == "2026-04-11"
        assert digest["mode"] == "daily"
        assert digest["headline_count"] == 1
        assert digest["sources"][0]["url"]
