"""Mock campus news source for local development and tests."""

from __future__ import annotations

from datetime import date
from typing import Any

from agent_core.models.news import NewsArticle, NewsArticleDetail, NewsSourceType

MOCK_NEWS: list[dict[str, Any]] = [
    {
        "id": "news-today-001",
        "title": "Daily campus briefing is available",
        "date": date.today().isoformat(),
        "category": "announcement",
        "summary": (
            "A fresh campus briefing is ready with today's student services, "
            "events, and academic reminders."
        ),
        "source": "Campus Communications",
        "source_type": NewsSourceType.MOCK,
        "source_name": "Campus Communications",
        "source_id": "mock-campus-comms",
        "external_id": "daily-campus-briefing",
        "tags": ["daily", "student-services"],
        "url": "https://example.edu/news/daily-campus-briefing",
        "content": (
            "The daily campus briefing collects student service updates, "
            "campus activities, academic reminders, and opportunity highlights "
            "for the current day."
        ),
        "raw_metadata": {"mock": True, "future_adapter": "campus_api"},
    },
    {
        "id": "news-001",
        "title": "Library extends opening hours during exam week",
        "date": "2026-04-11",
        "category": "announcement",
        "summary": (
            "The university library will stay open until midnight during the "
            "upcoming exam week."
        ),
        "source": "University Library",
        "source_type": NewsSourceType.OFFICIAL_SITE,
        "source_name": "University Library",
        "source_id": "library",
        "external_id": "library-hours",
        "tags": ["library", "exam-week"],
        "url": "https://example.edu/news/library-hours",
        "content": (
            "To support students during exam preparation, the university library "
            "will extend its opening hours until midnight from April 13 to "
            "April 24. Study rooms can be reserved through the library portal."
        ),
        "raw_metadata": {"mock": True, "future_adapter": "official_site"},
    },
    {
        "id": "news-002",
        "title": "Spring career fair registration is now open",
        "date": "2026-04-10",
        "category": "opportunity",
        "summary": (
            "Students can register for the spring career fair featuring campus "
            "recruiters and internship opportunities."
        ),
        "source": "Career Development Center",
        "source_type": NewsSourceType.WECHAT,
        "source_name": "Career Development Center",
        "source_id": "career-center-wechat",
        "external_id": "spring-career-fair",
        "tags": ["career", "internship", "event"],
        "url": "https://example.edu/news/spring-career-fair",
        "content": (
            "The Spring Career Fair will be held at the Student Activity Center "
            "on April 18. Participating employers will offer internships, "
            "graduate roles, and resume review sessions."
        ),
        "raw_metadata": {"mock": True, "future_adapter": "wechat"},
    },
    {
        "id": "news-003",
        "title": "Campus volunteer program seeks weekend mentors",
        "date": "2026-04-09",
        "category": "event",
        "summary": (
            "The student volunteer office is recruiting mentors for a weekend "
            "community learning program."
        ),
        "source": "Student Volunteer Office",
        "source_type": NewsSourceType.EMAIL,
        "source_name": "Student Volunteer Office",
        "source_id": "student-volunteer-office",
        "external_id": "weekend-mentors",
        "tags": ["volunteer", "mentor", "weekend"],
        "url": "https://example.edu/news/weekend-mentors",
        "content": (
            "Volunteers will mentor local middle school students in science, "
            "reading, and English. Training sessions are scheduled this Friday."
        ),
        "raw_metadata": {"mock": True, "future_adapter": "email"},
    },
]


class MockNewsSource:
    """Local mock news source used until real campus APIs are connected."""

    source_type = NewsSourceType.MOCK

    async def list_articles(self, *, limit: int = 50) -> list[NewsArticle]:
        """Return compact mock articles sorted newest-first."""
        articles = [NewsArticle.model_validate(article) for article in MOCK_NEWS]
        articles.sort(key=lambda item: item.date, reverse=True)
        return articles[:limit]

    async def get_article_detail(self, news_id: str) -> NewsArticleDetail | None:
        """Return full mock article content."""
        for article in MOCK_NEWS:
            if article["id"] == news_id:
                return NewsArticleDetail.model_validate(article)
        return None
