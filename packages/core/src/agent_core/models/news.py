"""Campus news data models.

These models define one canonical news format that can represent the current
mock data and future sources such as campus email, WeChat official accounts,
RSS feeds, and university website APIs.
"""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from agent_core.models.events import WidgetData, WidgetType


class NewsSourceType(StrEnum):
    """Supported source families for campus news ingestion."""

    MOCK = "mock"
    EMAIL = "email"
    WECHAT = "wechat"
    OFFICIAL_SITE = "official_site"
    RSS = "rss"
    API = "api"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class NewsArticle(BaseModel):
    """Compact campus news article used by list/search responses.

    ``source`` and ``url`` are kept as simple display fields for the frontend.
    The richer source metadata fields let future adapters preserve where an
    item came from without changing the public article shape.
    """

    id: str
    title: str
    date: str
    category: str = "announcement"
    summary: str = ""
    source: str = ""
    url: str = ""
    source_type: NewsSourceType = NewsSourceType.UNKNOWN
    source_name: str = ""
    source_id: str = ""
    external_id: str = ""
    author: str = ""
    tags: list[str] = Field(default_factory=list)
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class NewsArticleDetail(NewsArticle):
    """Full campus news article shown in the detail view."""

    content: str = ""


class NewsListResponse(BaseModel):
    """Response body for date, latest, and keyword news queries."""

    date: str | None = None
    query: str | None = None
    mode: Literal["daily", "search", "latest"]
    count: int
    articles: list[NewsArticle] = Field(default_factory=list)


class NewsHighlight(BaseModel):
    """One item in the digest highlights section."""

    id: str = ""
    title: str
    category: str = "announcement"
    summary: str = ""
    source_type: NewsSourceType = NewsSourceType.UNKNOWN


class NewsSourceRef(BaseModel):
    """Source link shown under a news digest."""

    title: str
    source: str = ""
    url: str = ""
    source_type: NewsSourceType = NewsSourceType.UNKNOWN


class NewsDigestWidgetData(WidgetData):
    """Payload for the campus news digest widget."""

    widget_type: Literal[WidgetType.NEWS_DIGEST] = WidgetType.NEWS_DIGEST
    date: str
    mode: Literal["daily", "latest_available"]
    headline_count: int
    highlights: list[NewsHighlight] = Field(default_factory=list)
    sources: list[NewsSourceRef] = Field(default_factory=list)


class NewsReportRequest(BaseModel):
    """Request body for generating an AI campus news report."""

    target_date: str | None = None
    query: str | None = None
    source: str = "all"
    limit: int = 20


class NewsReportArticleRef(BaseModel):
    """Compact article reference included in an AI-generated report."""

    id: str
    title: str
    date: str
    category: str = "announcement"
    source: str = ""
    source_type: NewsSourceType = NewsSourceType.UNKNOWN
    summary: str = ""


class NewsReportResponse(BaseModel):
    """AI-generated daily campus news report for the current filters."""

    title: str
    generated_at: str
    filter_text: str
    article_count: int
    summary: str
    key_points: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    articles: list[NewsReportArticleRef] = Field(default_factory=list)
