"""Shared interface for campus news source adapters."""

from typing import Protocol

from agent_core.models.news import NewsArticle, NewsArticleDetail, NewsSourceType


class NewsSourceAdapter(Protocol):
    """Protocol implemented by every campus news source adapter."""

    source_type: NewsSourceType

    async def list_articles(self, *, limit: int = 50) -> list[NewsArticle]:
        """Return compact news articles from this source."""
        ...

    async def get_article_detail(self, news_id: str) -> NewsArticleDetail | None:
        """Return full detail if this source owns the article."""
        ...
