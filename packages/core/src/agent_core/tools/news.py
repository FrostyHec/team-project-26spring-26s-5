"""Campus news tools - fetch, search, and summarize daily campus news.

Tools are intentionally thin wrappers over :class:`NewsService`, so the agent
and REST API use the same multi-source aggregation logic.
"""

import json
from datetime import date
from typing import Any

from agent_core.services.news_service import get_default_news_service
from agent_core.tools.registry import ToolRegistry, ToolSensitivity

_DEFAULT_LIMIT = 5


async def get_latest_news(limit: int = _DEFAULT_LIMIT) -> str:
    """Fetch the latest campus news articles from all configured sources."""
    service = await get_default_news_service()
    payload = await service.list_articles(limit=limit)
    return json.dumps(
        [article.model_dump(mode="json") for article in payload.articles],
        ensure_ascii=False,
    )


async def get_daily_news(target_date: str = "") -> str:
    """Fetch campus news for a specific day from all configured sources."""
    selected_date = target_date or date.today().isoformat()
    service = await get_default_news_service()
    payload = await service.list_articles(target_date=selected_date, limit=50)
    return payload.model_dump_json()


async def search_news(
    query: str,
    limit: int = _DEFAULT_LIMIT,
    target_date: str = "",
) -> str:
    """Search campus news by keyword, optionally within a specific date."""
    service = await get_default_news_service()
    payload = await service.list_articles(
        target_date=target_date or None,
        query=query,
        limit=limit,
    )
    return json.dumps(
        [article.model_dump(mode="json") for article in payload.articles],
        ensure_ascii=False,
    )


async def get_news_detail(news_id: str) -> str:
    """Fetch detailed content for a single campus news article."""
    service = await get_default_news_service()
    detail = await service.get_article_detail(news_id)
    if detail is None:
        return json.dumps(
            {"error": f"News article not found: {news_id}"},
            ensure_ascii=False,
        )
    return detail.model_dump_json()


async def create_news_digest(
    target_date: str = "",
    limit: int = _DEFAULT_LIMIT,
) -> str:
    """Create a compact daily campus news digest from all configured sources."""
    service = await get_default_news_service()
    digest = await service.create_digest(
        target_date=target_date or None,
        limit=limit,
    )
    return digest.model_dump_json()


_TOOL_DESCRIPTIONS: list[tuple[Any, str, ToolSensitivity]] = [
    (
        get_latest_news,
        "Fetch the latest campus news articles from all configured sources. "
        "Returns a JSON array with id, title, date, category, summary, source, "
        "source_type, and url fields. Call this when the user asks for recent "
        "campus news or updates.",
        ToolSensitivity.SAFE,
    ),
    (
        get_daily_news,
        "Fetch campus news for a specific date. Pass target_date as an ISO date "
        "like 2026-04-11, or leave it empty for today. Returns a JSON object "
        "with matching articles.",
        ToolSensitivity.SAFE,
    ),
    (
        search_news,
        "Search campus news by keyword across configured sources. Optionally "
        "pass target_date to search only within one day. Use this when the user "
        "asks about a topic such as career fair, library, volunteer, event, "
        "announcement, or email-derived campus news.",
        ToolSensitivity.SAFE,
    ),
    (
        get_news_detail,
        "Fetch detailed content for one campus news article by news_id. Use an "
        "id returned by get_latest_news, get_daily_news, or search_news.",
        ToolSensitivity.SAFE,
    ),
    (
        create_news_digest,
        "Create a compact daily campus news digest with highlights and source "
        "links. Call this when the user asks for a daily digest or summary.",
        ToolSensitivity.SAFE,
    ),
]


def register_news_tools(registry: ToolRegistry) -> None:
    """Register all campus news tools with the given registry."""
    for func, description, sensitivity in _TOOL_DESCRIPTIONS:
        registry.add_tool(func=func, description=description, sensitivity=sensitivity)
