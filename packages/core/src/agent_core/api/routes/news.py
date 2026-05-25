"""Campus news REST routes for the frontend news widget."""

from fastapi import APIRouter, Depends, HTTPException
from langchain_openai import ChatOpenAI

from agent_core.api.dependencies import get_llm, get_news_push_service
from agent_core.models.news import (
    NewsArticleDetail,
    NewsDigestWidgetData,
    NewsListResponse,
    NewsReportRequest,
    NewsReportResponse,
)
from agent_core.models.news_push import NewsPushSettings
from agent_core.services.news_push_service import NewsPushService
from agent_core.services.news_service import NewsService, create_default_news_service

router = APIRouter(prefix="/news", tags=["news"])


async def _widget_news_service() -> NewsService:
    """News service for widget-facing routes: real sources only, no mock."""
    return await create_default_news_service(include_mock=False)


@router.get("", response_model=NewsListResponse)
async def list_news(
    target_date: str | None = None,
    query: str | None = None,
    source: str = "all",
    limit: int = 10,
) -> NewsListResponse:
    """List campus news using optional date and keyword filters.

    Args:
        target_date: Optional ISO date string filter. Empty or omitted means no
            date filter.
        query: Optional keyword search filter. When provided together with
            target_date, both filters are applied.
        source: Source filter (all, email, wechat, official_site, etc.).
        limit: Maximum number of articles to return.
    """
    service = await _widget_news_service()
    return await service.list_articles(
        target_date=target_date,
        query=query,
        source=source,
        limit=limit,
    )


@router.get("/latest", response_model=NewsListResponse)
async def latest_news(source: str = "all", limit: int = 10) -> NewsListResponse:
    """Return the latest campus news articles."""
    service = await _widget_news_service()
    return await service.list_articles(source=source, limit=limit)


@router.get("/digest", response_model=NewsDigestWidgetData)
async def news_digest(
    target_date: str | None = None,
    source: str = "all",
    limit: int = 5,
) -> NewsDigestWidgetData:
    """Return a digest payload suitable for the NewsDigestWidget."""
    service = await _widget_news_service()
    return await service.create_digest(
        target_date=target_date,
        source=source,
        limit=limit,
    )


@router.post("/report", response_model=NewsReportResponse)
async def news_report(
    request: NewsReportRequest,
    llm: ChatOpenAI = Depends(get_llm),
) -> NewsReportResponse:
    """Generate an AI-written report for the current campus news filters."""
    service = await _widget_news_service()
    return await service.create_ai_report(
        llm=llm,
        target_date=request.target_date,
        query=request.query,
        source=request.source,
        limit=request.limit,
    )


@router.get("/push/settings", response_model=NewsPushSettings)
async def get_news_push_settings(
    service: NewsPushService = Depends(get_news_push_service),
) -> NewsPushSettings:
    """Return the current daily campus news push settings."""
    return await service.get_settings()


@router.put("/push/settings", response_model=NewsPushSettings)
async def save_news_push_settings(
    settings: NewsPushSettings,
    service: NewsPushService = Depends(get_news_push_service),
) -> NewsPushSettings:
    """Validate and persist daily campus news push settings."""
    return await service.save_settings(settings)


@router.get("/{news_id}", response_model=NewsArticleDetail)
async def news_detail(news_id: str) -> NewsArticleDetail:
    """Return full content for one campus news article."""
    service = await _widget_news_service()
    detail = await service.get_article_detail(news_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="News article not found")
    return detail
