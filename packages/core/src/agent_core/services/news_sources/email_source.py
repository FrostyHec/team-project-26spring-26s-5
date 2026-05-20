"""Email-backed campus news source adapter.

This adapter intentionally reads from :class:`EmailService` only. It does not
connect to IMAP or trigger email sync by itself; the Email feature remains
responsible for fetching mail, while Campus News interprets cached mail as
news-like content.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from html import unescape
from importlib.resources import files
from typing import cast

from agent_core.models.email import EmailDetail, EmailSummary
from agent_core.models.news import NewsArticle, NewsArticleDetail, NewsSourceType
from agent_core.services.email_service import EmailService


def _load_news_lexicon() -> dict[str, object]:
    """Load optional locale-specific news keyword resources."""
    try:
        resource = files("agent_core.resources").joinpath("news_lexicon.zh-CN.json")
        payload = json.loads(resource.read_text(encoding="utf-8"))
    except (FileNotFoundError, ModuleNotFoundError, json.JSONDecodeError):
        return {}
    if isinstance(payload, dict):
        return cast("dict[str, object]", payload)
    return {}


def _lexicon_list(lexicon: dict[str, object], key: str) -> tuple[str, ...]:
    """Return a normalized string tuple from a lexicon list entry."""
    value = lexicon.get(key)
    if not isinstance(value, list):
        return ()
    return tuple(
        item.strip().lower() for item in value if isinstance(item, str) and item.strip()
    )


def _category_lexicon_list(
    lexicon: dict[str, object],
    category: str,
) -> tuple[str, ...]:
    """Return normalized keywords for one category from the lexicon."""
    categories = lexicon.get("category_keywords")
    if not isinstance(categories, dict):
        return ()
    value = cast("dict[str, object]", categories).get(category)
    if not isinstance(value, list):
        return ()
    return tuple(
        item.strip().lower() for item in value if isinstance(item, str) and item.strip()
    )


_NEWS_LEXICON = _load_news_lexicon()

_STRONG_NEWS_KEYWORDS: tuple[str, ...] = (
    "announcement",
    "notice",
    "newsletter",
    "bulletin",
    "digest",
    "campus news",
) + _lexicon_list(_NEWS_LEXICON, "strong_news_keywords")

_TOPIC_NEWS_KEYWORDS: tuple[str, ...] = (
    "event",
    "seminar",
    "career",
    "workshop",
    "volunteer",
    "library",
    "registration",
    "lecture",
    "forum",
) + _lexicon_list(_NEWS_LEXICON, "topic_news_keywords")

_OFFICIAL_SENDER_HINTS: tuple[str, ...] = (
    "office",
    "center",
    "centre",
    "department",
    "school",
    "college",
    "library",
    "registrar",
    "career",
    "student affairs",
    "graduate",
    "undergraduate",
    "campus",
    "newsletter",
    "announcement",
    "admin",
) + _lexicon_list(_NEWS_LEXICON, "official_sender_hints")

_NON_NEWS_KEYWORDS: tuple[str, ...] = (
    "verification code",
    "verify your",
    "password reset",
    "security alert",
    "login alert",
    "invoice",
    "receipt",
    "payment",
    "delivery",
    "unsubscribe",
) + _lexicon_list(_NEWS_LEXICON, "non_news_keywords")

_PERSONAL_SUBJECT_PREFIXES: tuple[str, ...] = (
    "re:",
    "fw:",
    "fwd:",
) + _lexicon_list(_NEWS_LEXICON, "personal_subject_prefixes")

_CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "opportunity",
        ("career", "job", "internship")
        + _category_lexicon_list(_NEWS_LEXICON, "opportunity"),
    ),
    (
        "event",
        ("event", "seminar", "workshop", "lecture", "forum")
        + _category_lexicon_list(_NEWS_LEXICON, "event"),
    ),
    (
        "announcement",
        ("announcement", "notice", "registration")
        + _category_lexicon_list(_NEWS_LEXICON, "announcement"),
    ),
)


def _date_only(value: str) -> str:
    """Return the YYYY-MM-DD portion from an email date string."""
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError:
        return value[:10]


def _matches_news_keywords(email: EmailSummary) -> bool:
    """Heuristically decide whether an email looks like campus news."""
    subject = email.subject.lower()
    preview = email.preview.lower()
    sender_text = " ".join([email.sender, email.sender_name]).lower()
    content_text = " ".join([subject, preview])
    full_text = " ".join([content_text, sender_text])

    if any(keyword in full_text for keyword in _NON_NEWS_KEYWORDS):
        return False

    # Replies/forwards are usually conversations rather than publishable news.
    if subject.strip().startswith(_PERSONAL_SUBJECT_PREFIXES):
        has_explicit_news_signal = any(
            keyword in content_text for keyword in _STRONG_NEWS_KEYWORDS
        )
        if not has_explicit_news_signal:
            return False

    strong_hits = sum(1 for keyword in _STRONG_NEWS_KEYWORDS if keyword in content_text)
    topic_hits = sum(1 for keyword in _TOPIC_NEWS_KEYWORDS if keyword in content_text)
    official_sender_hits = sum(
        1 for keyword in _OFFICIAL_SENDER_HINTS if keyword in sender_text
    )

    # Be conservative: a generic official sender alone is not enough, and a
    # single weak topic word from a personal sender is not enough either.
    if strong_hits > 0:
        return True
    return topic_hits >= 2 or (topic_hits >= 1 and official_sender_hits >= 1)


def _infer_category(email: EmailSummary | EmailDetail) -> str:
    """Infer a coarse news category from email text."""
    text = " ".join(
        [
            email.subject,
            email.sender,
            email.sender_name,
            getattr(email, "preview", ""),
            getattr(email, "body_text", ""),
        ]
    ).lower()
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(keyword.lower() in text for keyword in keywords):
            return category
    return "announcement"


def _clean_email_text(text: str) -> str:
    """Decode common HTML entities and normalize email whitespace."""
    decoded = unescape(text).replace("\xa0", " ")
    decoded = re.sub(r"[ \t\f\v]+", " ", decoded)
    decoded = re.sub(r" *\n *", "\n", decoded)
    decoded = re.sub(r"\n{3,}", "\n\n", decoded)
    return decoded.strip()


def _summary_from_text(text: str, max_length: int = 220) -> str:
    """Create a compact single-line summary from email text."""
    compact = " ".join(_clean_email_text(text).split())
    if len(compact) <= max_length:
        return compact
    return compact[: max_length - 3].rstrip() + "..."


def email_summary_to_news_article(email: EmailSummary) -> NewsArticle:
    """Convert an email list summary into a compact news article."""
    source = email.sender_name or email.sender or "Email"
    category = _infer_category(email)
    return NewsArticle(
        id=f"email-{email.uid}",
        title=email.subject or "(No subject)",
        date=_date_only(email.date),
        category=category,
        summary=_summary_from_text(email.preview or email.subject),
        source=source,
        url="",
        source_type=NewsSourceType.EMAIL,
        source_name=source,
        source_id=email.sender,
        external_id=str(email.uid),
        author=source,
        tags=["email", category],
        raw_metadata={
            "uid": email.uid,
            "sender": email.sender,
            "sender_name": email.sender_name,
            "has_attachments": email.has_attachments,
        },
    )


def email_detail_to_news_article(email: EmailDetail) -> NewsArticleDetail:
    """Convert a full email detail into a news article detail."""
    source = email.sender_name or email.sender or "Email"
    category = _infer_category(email)
    content = _clean_email_text(email.body_text)
    return NewsArticleDetail(
        id=f"email-{email.uid}",
        title=email.subject or "(No subject)",
        date=_date_only(email.date),
        category=category,
        summary=_summary_from_text(content or email.subject),
        source=source,
        url="",
        source_type=NewsSourceType.EMAIL,
        source_name=source,
        source_id=email.sender,
        external_id=email.message_id or str(email.uid),
        author=source,
        tags=["email", category],
        raw_metadata={
            "uid": email.uid,
            "message_id": email.message_id,
            "sender": email.sender,
            "sender_name": email.sender_name,
            "recipients": email.recipients,
            "cc": email.cc,
            "has_attachments": email.has_attachments,
            "html_local_path": email.html_local_path,
        },
        content=content,
    )


class EmailNewsAdapter:
    """Read cached emails and expose news-like messages as news articles."""

    source_type = NewsSourceType.EMAIL

    def __init__(self, email_service: EmailService) -> None:
        self._email_service = email_service

    async def list_articles(
        self,
        *,
        limit: int = 50,
        folder: str | None = "INBOX",
        include_unmatched: bool = False,
    ) -> list[NewsArticle]:
        """Return cached email messages converted to news articles."""
        emails = await self._email_service.list_emails(limit=limit, folder=folder)
        selected = [
            email
            for email in emails
            if include_unmatched or _matches_news_keywords(email)
        ]
        return [email_summary_to_news_article(email) for email in selected]

    async def get_article_detail(
        self,
        news_id: str,
        *,
        folder: str = "INBOX",
    ) -> NewsArticleDetail | None:
        """Return full detail for an ``email-{uid}`` news article."""
        prefix = "email-"
        if not news_id.startswith(prefix):
            return None
        try:
            uid = int(news_id.removeprefix(prefix))
        except ValueError:
            return None

        detail = await self._email_service.ensure_email_content_fetched(
            uid,
            folder=folder,
        )
        if detail is None:
            return None
        return email_detail_to_news_article(detail)
