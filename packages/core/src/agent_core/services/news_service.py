"""Campus news aggregation service.

The service owns cross-source behavior: aggregation, filtering, search,
sorting, de-duplication, detail dispatch, and digest creation.  Individual
sources only convert their own raw data into the canonical news models.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent_core.logging_utils import get_logger
from agent_core.models.news import (
    NewsArticle,
    NewsArticleDetail,
    NewsDigestWidgetData,
    NewsHighlight,
    NewsListResponse,
    NewsReportArticleRef,
    NewsReportResponse,
    NewsSourceRef,
)
from agent_core.services.news_sources.base import NewsSourceAdapter
from agent_core.services.news_sources.mock_source import MockNewsSource

logger = get_logger("services.news")

_DEFAULT_LIMIT = 10


def _matches_query(article: NewsArticle, query: str) -> bool:
    """Return True if a compact article matches a keyword query."""
    normalized = query.strip().lower()
    if not normalized:
        return True
    text = " ".join(
        [
            article.title,
            article.summary,
            article.category,
            article.source,
            article.source_name,
            article.source_id,
            article.author,
            " ".join(article.tags),
        ]
    ).lower()
    return normalized in text


def _dedupe_articles(articles: list[NewsArticle]) -> list[NewsArticle]:
    """Deduplicate articles while preserving newest-first ordering."""
    seen: set[tuple[str, str, str]] = set()
    deduped: list[NewsArticle] = []
    for article in articles:
        key = (
            str(article.source_type),
            article.source_id or article.source,
            article.external_id or article.id,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(article)
    return deduped


def _source_label(article: NewsArticle) -> str:
    """Return a compact human-readable source label."""
    source_type = str(article.source_type)
    source_name = article.source_name or article.source
    return f"{source_type}: {source_name}" if source_name else source_type


def _fallback_report(
    *,
    title: str,
    generated_at: str,
    filter_text: str,
    details: list[NewsArticleDetail],
) -> NewsReportResponse:
    """Create a deterministic report when the LLM is unavailable."""
    summary = (
        "No campus news matched the current filters."
        if not details
        else f"Found {len(details)} campus news item(s) for {filter_text}."
    )
    key_points = [
        f"{item.title}: {item.summary or item.content[:160]}" for item in details[:5]
    ]
    action_items = [
        item.summary
        for item in details
        if any(
            keyword in f"{item.title} {item.summary} {item.content}".lower()
            for keyword in ("register", "submit", "deadline")
        )
    ][:5]
    return NewsReportResponse(
        title=title,
        generated_at=generated_at,
        filter_text=filter_text,
        article_count=len(details),
        summary=summary,
        key_points=key_points,
        action_items=action_items,
        articles=[
            NewsReportArticleRef(
                id=item.id,
                title=item.title,
                date=item.date,
                category=item.category,
                source=_source_label(item),
                source_type=item.source_type,
                summary=item.summary,
            )
            for item in details
        ],
    )


def _parse_report_json(content: str) -> dict[str, Any]:
    """Extract a JSON object from an LLM response."""
    start = content.find("{")
    end = content.rfind("}") + 1
    if start >= 0 and end > start:
        return json.loads(content[start:end])
    return json.loads(content)


class NewsService:
    """Aggregate campus news from one or more source adapters."""

    def __init__(self, sources: list[NewsSourceAdapter]) -> None:
        self._sources = sources

    async def _collect_articles(
        self,
        *,
        source: str = "all",
        limit_per_source: int = 50,
    ) -> list[NewsArticle]:
        """Collect compact articles from enabled sources."""
        selected_source = source.strip().lower() if source else "all"
        articles: list[NewsArticle] = []
        for adapter in self._sources:
            if selected_source not in {"all", str(adapter.source_type)}:
                continue
            try:
                articles.extend(await adapter.list_articles(limit=limit_per_source))
            except Exception as exc:
                logger.warning(
                    "Skipping news source %s after error: %s",
                    adapter.source_type,
                    exc,
                )
        articles.sort(key=lambda item: item.date, reverse=True)
        return _dedupe_articles(articles)

    async def list_articles(
        self,
        *,
        target_date: str | None = None,
        query: str | None = None,
        source: str = "all",
        limit: int = _DEFAULT_LIMIT,
    ) -> NewsListResponse:
        """Return news articles filtered by optional date and keyword."""
        selected_date = target_date.strip() if target_date else ""
        selected_query = query.strip() if query else ""
        safe_limit = limit if limit > 0 else _DEFAULT_LIMIT

        articles = await self._collect_articles(
            source=source,
            limit_per_source=max(safe_limit, 50),
        )
        if selected_date:
            articles = [
                article for article in articles if article.date == selected_date
            ]
        if selected_query:
            articles = [
                article
                for article in articles
                if _matches_query(article, selected_query)
            ]

        mode = "search" if selected_query else "daily" if selected_date else "latest"
        limited = articles[:safe_limit]
        return NewsListResponse(
            date=selected_date or None,
            query=selected_query or None,
            mode=mode,
            count=len(limited),
            articles=limited,
        )

    async def get_article_detail(self, news_id: str) -> NewsArticleDetail | None:
        """Return full detail for one article from whichever source owns it."""
        for adapter in self._sources:
            try:
                detail = await adapter.get_article_detail(news_id)
            except Exception as exc:
                logger.warning(
                    "Detail lookup failed in source %s for %s: %s",
                    adapter.source_type,
                    news_id,
                    exc,
                )
                continue
            if detail is not None:
                return detail
        return None

    async def create_digest(
        self,
        *,
        target_date: str | None = None,
        source: str = "all",
        limit: int = 5,
    ) -> NewsDigestWidgetData:
        """Create a compact digest from aggregated campus news."""
        selected_date = target_date or date.today().isoformat()
        safe_limit = limit if limit > 0 else 5
        daily = await self.list_articles(
            target_date=selected_date,
            source=source,
            limit=safe_limit,
        )
        latest = daily
        mode = "daily"
        if not daily.articles:
            latest = await self.list_articles(source=source, limit=safe_limit)
            mode = "latest_available"

        articles = latest.articles[:safe_limit]
        return NewsDigestWidgetData(
            date=selected_date,
            mode=mode,
            headline_count=len(articles),
            highlights=[
                NewsHighlight(
                    id=article.id,
                    title=article.title,
                    category=article.category,
                    summary=article.summary,
                    source_type=article.source_type,
                )
                for article in articles
            ],
            sources=[
                NewsSourceRef(
                    title=article.title,
                    source=article.source,
                    url=article.url,
                    source_type=article.source_type,
                )
                for article in articles
            ],
        )

    async def create_ai_report(
        self,
        *,
        llm: Any,
        target_date: str | None = None,
        query: str | None = None,
        source: str = "all",
        limit: int = 20,
    ) -> NewsReportResponse:
        """Generate an AI-written report for the current news filters."""
        selected_date = target_date.strip() if target_date else ""
        selected_query = query.strip() if query else ""
        safe_limit = limit if limit > 0 else _DEFAULT_LIMIT

        listed = await self.list_articles(
            target_date=selected_date or None,
            query=selected_query or None,
            source=source,
            limit=safe_limit,
        )
        details: list[NewsArticleDetail] = []
        for article in listed.articles:
            detail = await self.get_article_detail(article.id)
            if detail is None:
                detail = NewsArticleDetail(
                    **article.model_dump(),
                    content=article.summary,
                )
            details.append(detail)

        generated_at = date.today().isoformat()
        title = (
            f"{selected_date} Campus News Daily"
            if selected_date
            else "Campus News Daily Report"
        )
        filter_parts = [selected_date or "All dates", source or "all"]
        if selected_query:
            filter_parts.append(f"Keyword: {selected_query}")
        filter_text = " | ".join(filter_parts)

        if not details:
            return _fallback_report(
                title=title,
                generated_at=generated_at,
                filter_text=filter_text,
                details=details,
            )

        source_payload = [
            {
                "title": item.title,
                "date": item.date,
                "category": item.category,
                "source": _source_label(item),
                "summary": item.summary,
                "content": item.content[:1800],
            }
            for item in details
        ]
        system = SystemMessage(
            content=(
                "You are a campus news editor. Produce concise, factual "
                "daily reports from provided campus news only. Write the "
                "report in Simplified Chinese when the user-facing product "
                "locale requires it. Do not invent facts. Return valid JSON "
                "only."
            )
        )
        human = HumanMessage(
            content=(
                "Generate a campus news daily report from the articles below. "
                "Return JSON with exactly these fields: summary: string, "
                "key_points: string[], action_items: string[]. The summary "
                "should be a brief overview. The key_points array should list "
                "important news points in priority order. The action_items "
                "array should list items students need to notice or act on; "
                "return an empty array when there are none.\n\n"
                f"Filters: {filter_text}\n\n"
                f"Articles: {json.dumps(source_payload, ensure_ascii=False)}"
            )
        )

        try:
            response = await llm.ainvoke([system, human])
            parsed = _parse_report_json(str(response.content))
            return NewsReportResponse(
                title=title,
                generated_at=generated_at,
                filter_text=filter_text,
                article_count=len(details),
                summary=str(parsed.get("summary", "")).strip(),
                key_points=[
                    str(item).strip()
                    for item in parsed.get("key_points", [])
                    if str(item).strip()
                ],
                action_items=[
                    str(item).strip()
                    for item in parsed.get("action_items", [])
                    if str(item).strip()
                ],
                articles=[
                    NewsReportArticleRef(
                        id=item.id,
                        title=item.title,
                        date=item.date,
                        category=item.category,
                        source=_source_label(item),
                        source_type=item.source_type,
                        summary=item.summary,
                    )
                    for item in details
                ],
            )
        except Exception as exc:
            logger.warning("Falling back after news report generation failed: %s", exc)
            return _fallback_report(
                title=title,
                generated_at=generated_at,
                filter_text=filter_text,
                details=details,
            )


async def create_default_news_service(include_email: bool = True) -> NewsService:
    """Build a NewsService with all currently available source adapters."""
    sources: list[NewsSourceAdapter] = [MockNewsSource()]
    if include_email:
        try:
            from agent_core.persistence.email_provider import get_current_email_service
            from agent_core.services.news_sources.email_source import EmailNewsAdapter

            email_service = get_current_email_service()
            if email_service is not None:
                sources.append(EmailNewsAdapter(email_service))
        except Exception as exc:
            logger.warning("Email news source unavailable: %s", exc)
    return NewsService(sources)


async def get_default_news_service() -> NewsService:
    """Return a newly wired NewsService.

    The service is intentionally lightweight and rebuilt per call for now, so it
    always picks up the latest email service singleton from dependency setup.
    """
    return await create_default_news_service()
