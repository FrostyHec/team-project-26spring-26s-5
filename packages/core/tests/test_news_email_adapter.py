"""Tests for converting cached emails into campus news articles."""

import pytest

from agent_core.models.email import EmailDetail, EmailSummary
from agent_core.models.news import NewsSourceType
from agent_core.services.news_sources.email_source import (
    EmailNewsAdapter,
    email_detail_to_news_article,
    email_summary_to_news_article,
)


class FakeEmailService:
    """Small fake service with the EmailService methods used by the adapter."""

    def __init__(
        self,
        summaries: list[EmailSummary],
        details: dict[int, EmailDetail] | None = None,
    ) -> None:
        self.summaries = summaries
        self.details = details or {}
        self.ensure_calls: list[tuple[int, str]] = []

    async def list_emails(self, **_: object) -> list[EmailSummary]:
        return self.summaries

    async def get_email_detail(
        self,
        uid: int,
        folder: str = "INBOX",
    ) -> EmailDetail | None:
        return self.details.get(uid)

    async def ensure_email_content_fetched(
        self,
        uid: int,
        folder: str = "INBOX",
    ) -> EmailDetail | None:
        self.ensure_calls.append((uid, folder))
        return self.details.get(uid)


def test_email_summary_to_news_article() -> None:
    summary = EmailSummary(
        uid=42,
        subject="Career workshop registration is open",
        sender="career@example.edu",
        sender_name="Career Center",
        date="2026-04-18T09:30:00",
        preview="Register for the campus career workshop this week.",
    )

    article = email_summary_to_news_article(summary)

    assert article.id == "email-42"
    assert article.date == "2026-04-18"
    assert article.category == "opportunity"
    assert article.source_type == NewsSourceType.EMAIL
    assert article.source_name == "Career Center"
    assert article.raw_metadata["uid"] == 42


def test_email_detail_to_news_article() -> None:
    detail = EmailDetail(
        uid=7,
        message_id="<campus-news@example.edu>",
        subject="Library notice",
        sender="library@example.edu",
        sender_name="Library",
        date="2026-04-11T10:00:00",
        body_text="The library will extend opening hours during exam week.",
    )

    article = email_detail_to_news_article(detail)

    assert article.id == "email-7"
    assert article.external_id == "<campus-news@example.edu>"
    assert "extend opening hours" in article.content
    assert article.source_type == NewsSourceType.EMAIL


def test_email_detail_cleans_html_entities() -> None:
    detail = EmailDetail(
        uid=8,
        message_id="<notice-entities@example.edu>",
        subject="Campus notice",
        sender="office@example.edu",
        sender_name="Campus Office",
        date="2026-04-11T10:00:00",
        body_text=(
            "Students:&nbsp;&nbsp;&nbsp;Hello!\n\n\n"
            "&nbsp;&nbsp;Please submit the project info &amp; poster."
        ),
    )

    article = email_detail_to_news_article(detail)

    assert "&nbsp;" not in article.content
    assert "\xa0" not in article.content
    assert "Students: Hello!" in article.content
    assert "project info & poster" in article.content
    assert "&nbsp;" not in article.summary


@pytest.mark.asyncio
async def test_adapter_lists_only_news_like_emails() -> None:
    service = FakeEmailService(
        [
            EmailSummary(
                uid=1,
                subject="Campus event: volunteer mentor program",
                sender="volunteer@example.edu",
                sender_name="Volunteer Office",
                date="2026-04-09T12:00:00",
                preview="Join the weekend volunteer mentor program.",
            ),
            EmailSummary(
                uid=2,
                subject="Private note",
                sender="friend@example.edu",
                sender_name="Friend",
                date="2026-04-09T13:00:00",
                preview="Lunch tomorrow?",
            ),
        ]
    )
    adapter = EmailNewsAdapter(service)  # type: ignore[arg-type]

    articles = await adapter.list_articles()

    assert len(articles) == 1
    assert articles[0].id == "email-1"
    assert articles[0].source_type == NewsSourceType.EMAIL


@pytest.mark.asyncio
async def test_adapter_excludes_transactional_and_personal_emails() -> None:
    service = FakeEmailService(
        [
            EmailSummary(
                uid=10,
                subject="Your verification code",
                sender="security@example.edu",
                sender_name="Security",
                date="2026-04-09T12:00:00",
                preview="Your verification code is 123456.",
            ),
            EmailSummary(
                uid=11,
                subject="Re: lunch tomorrow",
                sender="friend@example.edu",
                sender_name="Friend",
                date="2026-04-09T13:00:00",
                preview="Can we move it to noon?",
            ),
            EmailSummary(
                uid=12,
                subject="Library notice: extended opening hours",
                sender="library@example.edu",
                sender_name="Campus Library",
                date="2026-04-09T14:00:00",
                preview="The library will extend opening hours during exam week.",
            ),
        ]
    )
    adapter = EmailNewsAdapter(service)  # type: ignore[arg-type]

    articles = await adapter.list_articles()

    assert [article.id for article in articles] == ["email-12"]


@pytest.mark.asyncio
async def test_adapter_requires_enough_news_signal_for_weak_topics() -> None:
    service = FakeEmailService(
        [
            EmailSummary(
                uid=20,
                subject="Workshop notes",
                sender="classmate@example.edu",
                sender_name="Classmate",
                date="2026-04-09T12:00:00",
                preview="Here are the notes from yesterday.",
            ),
            EmailSummary(
                uid=21,
                subject="Workshop registration opens today",
                sender="career@example.edu",
                sender_name="Career Center",
                date="2026-04-09T13:00:00",
                preview="Students can register for the career workshop this week.",
            ),
        ]
    )
    adapter = EmailNewsAdapter(service)  # type: ignore[arg-type]

    articles = await adapter.list_articles()

    assert [article.id for article in articles] == ["email-21"]


@pytest.mark.asyncio
async def test_adapter_gets_email_article_detail() -> None:
    service = FakeEmailService(
        [],
        details={
            5: EmailDetail(
                uid=5,
                message_id="<notice@example.edu>",
                subject="Campus notice",
                sender="notice@example.edu",
                sender_name="Campus Office",
                date="2026-04-10T08:00:00",
                body_text="A campus-wide notice for students.",
            )
        },
    )
    adapter = EmailNewsAdapter(service)  # type: ignore[arg-type]

    article = await adapter.get_article_detail("email-5")

    assert article is not None
    assert article.id == "email-5"
    assert article.content == "A campus-wide notice for students."
    assert service.ensure_calls == [(5, "INBOX")]


@pytest.mark.asyncio
async def test_adapter_ignores_non_email_news_id() -> None:
    adapter = EmailNewsAdapter(FakeEmailService([]))  # type: ignore[arg-type]

    article = await adapter.get_article_detail("news-001")

    assert article is None
