"""Email data models — SQLModel ORM tables and Pydantic DTOs.

Follows the same architecture as :mod:`agent_core.models.deadline`:

- ``EmailRecord`` / ``AttachmentRecord`` are **SQLModel tables** used by
  both the ORM persistence layer and the API response schema.
- Pure Pydantic ``BaseModel`` classes are used for request DTOs and
  computed response objects that do not map 1-to-1 to a DB row.
- Enums eliminate magic strings for flags, sync directions, and IMAP
  server defaults.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel
from sqlmodel import Field, SQLModel

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EmailFlag(StrEnum):
    """IMAP flag identifiers used by the flag-toggle API."""

    SEEN = "seen"
    FLAGGED = "flagged"
    ANSWERED = "answered"
    DELETED = "deleted"
    SPAM = "spam"


class MailboxFolder(StrEnum):
    """Named IMAP mailbox folders for Tencent Exmail.

    ``STARRED`` is a virtual folder backed by the ``\\Flagged`` search on
    INBOX rather than a physical IMAP mailbox.
    """

    INBOX = "INBOX"
    SENT = "Sent Messages"
    TRASH = "Deleted Messages"
    SPAM = "Junk"
    STARRED = "__STARRED__"  # virtual — SEARCH FLAGGED on INBOX


class ImapDefaults(StrEnum):
    """Tencent Exmail IMAP/SMTP connection parameters.

    Centralises server addresses and ports so they are never scattered
    as magic strings throughout the codebase.
    """

    IMAP_HOST = "imap.exmail.qq.com"
    IMAP_PORT = "993"
    SMTP_HOST = "smtp.exmail.qq.com"
    SMTP_PORT = "465"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Default look-back window for IMAP fetching (days).
DEFAULT_FETCH_DAYS: int = 30

#: Default page size for email listing.
DEFAULT_PAGE_SIZE: int = 50

#: Preview text truncation length (characters).
PREVIEW_LENGTH: int = 200

#: Relative cache directory for saved HTML bodies.
HTML_CACHE_DIR: str = "cache/email/html"

#: Relative cache directory for saved attachment files.
ATTACHMENT_CACHE_DIR: str = "cache/email/attachments"

#: IMAP flag string ↔ :class:`EmailFlag` mapping.
IMAP_FLAG_MAP: dict[EmailFlag, str] = {
    EmailFlag.SEEN: "\\Seen",
    EmailFlag.FLAGGED: "\\Flagged",
    EmailFlag.ANSWERED: "\\Answered",
    EmailFlag.DELETED: "\\Deleted",
}


# ---------------------------------------------------------------------------
# SQLModel ORM tables
# ---------------------------------------------------------------------------


class EmailRecord(SQLModel, table=True):
    """An email message persisted in the local SQLite store.

    Serves as both the SQLModel ORM table **and** the Pydantic schema
    for internal data transfer (same dual-role pattern as
    :class:`~agent_core.models.deadline.DeadlineRecord`).

    Attributes:
        uid: IMAP UID — the natural primary key.
        message_id: RFC-2822 ``Message-ID`` header.
        subject: Decoded subject line.
        sender: Sender email address.
        sender_name: Decoded display name of the sender.
        recipients: Comma-separated ``To`` addresses.
        cc: Comma-separated ``Cc`` addresses.
        date: ISO-8601 date string from the ``Date`` header.
        body_text: Plain-text body (or HTML→text fallback).
        html_local_path: Relative path to the cached HTML file.
        is_seen: Whether the ``\\Seen`` flag is set.
        is_flagged: Whether the ``\\Flagged`` flag is set.
        is_answered: Whether the ``\\Answered`` flag is set.
        has_attachments: Convenience flag for quick list display.
        content_fetched: True after HTML and attachments have been downloaded
            on-demand.  False until the first detail view triggers a fetch,
            and reset to False after a cache clear so the next detail view
            re-fetches.
        synced_at: ISO-8601 timestamp of last sync.
    """

    __tablename__ = "emails"  # type: ignore[assignment]

    uid: int = Field(primary_key=True)
    message_id: str = Field(default="")
    subject: str = Field(default="")
    sender: str = Field(default="")
    sender_name: str = Field(default="")
    recipients: str = Field(default="")
    cc: str = Field(default="")
    date: str = Field(default="")
    body_text: str = Field(default="")
    html_local_path: str = Field(default="")
    is_seen: bool = Field(default=False)
    is_flagged: bool = Field(default=False)
    is_answered: bool = Field(default=False)
    has_attachments: bool = Field(default=False)
    content_fetched: bool = Field(default=False)
    #: IMAP mailbox folder — second half of the composite primary key.
    folder: str = Field(default="INBOX", primary_key=True)
    synced_at: str = Field(default="")


class AttachmentRecord(SQLModel, table=True):
    """Metadata for a cached email attachment.

    Attributes:
        id: Auto-increment surrogate key.
        email_uid: Foreign key referencing :attr:`EmailRecord.uid`.
        filename: Original attachment filename.
        content_type: MIME type (e.g. ``application/pdf``).
        content_id: RFC-2392 Content-ID for inline images (CID).
        local_path: Relative path under :data:`ATTACHMENT_CACHE_DIR`.
        file_size: Size in bytes.
        download_time: ISO-8601 timestamp when downloaded.
    """

    __tablename__ = "attachments"  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)
    email_uid: int = Field(default=0, index=True)
    email_folder: str = Field(default="INBOX")
    filename: str = Field(default="")
    content_type: str = Field(default="")
    content_id: str = Field(default="")
    local_path: str = Field(default="")
    file_size: int = Field(default=0)
    download_time: str = Field(default="")
    is_downloaded: bool = Field(default=False)


class EmailSettingsRecord(SQLModel, table=True):
    """Key-value settings specific to the email subsystem.

    Stored in the same SQLite database as emails so that
    :class:`~agent_core.persistence.email_store.EmailStore` can
    manage everything with one engine.
    """

    __tablename__ = "email_settings"  # type: ignore[assignment]

    key: str = Field(primary_key=True)
    value: str = Field(default="")


# ---------------------------------------------------------------------------
# Pydantic DTO / API models (no table)
# ---------------------------------------------------------------------------


class EmailSummary(BaseModel):
    """Lightweight email entry for list views.

    Computed from :class:`EmailRecord` via :func:`record_to_summary`.
    """

    uid: int
    subject: str = ""
    sender: str = ""
    sender_name: str = ""
    date: str = ""
    preview: str = ""
    is_seen: bool = False
    is_flagged: bool = False
    is_answered: bool = False
    has_attachments: bool = False


class EmailDetail(BaseModel):
    """Full email content with attachment list — used by detail view."""

    uid: int
    message_id: str = ""
    subject: str = ""
    sender: str = ""
    sender_name: str = ""
    recipients: str = ""
    cc: str = ""
    date: str = ""
    body_text: str = ""
    html_local_path: str = ""
    is_seen: bool = False
    is_flagged: bool = False
    is_answered: bool = False
    has_attachments: bool = False
    attachments: list[AttachmentRecord] = []


class SendEmailRequest(BaseModel):
    """Request body for the send-email endpoint / tool."""

    to: str
    cc: str = ""
    subject: str = ""
    html_body: str = ""
    plain_body: str = ""
    in_reply_to: str = ""
    references: str = ""
    attachment_paths: list[str] = []


class UpdateFlagRequest(BaseModel):
    """Request body for the flag-update endpoint."""

    flag: EmailFlag
    value: bool


class EmailSyncResult(BaseModel):
    """Summary returned after an IMAP sync operation."""

    new_count: int = 0
    updated_count: int = 0
    total_count: int = 0
    synced_at: str = ""


class EmailConnectionTestResult(BaseModel):
    """Result of an IMAP/SMTP connectivity test."""

    success: bool
    message: str = ""
    imap_ok: bool = False
    smtp_ok: bool = False


class EmailSettingsInfo(BaseModel):
    """Public-facing email settings (no credentials)."""

    email_fetch_days: int = DEFAULT_FETCH_DAYS
    auto_sync: bool = True


class ClearCacheResult(BaseModel):
    """Summary returned after clearing the attachment/HTML cache."""

    cleared_files: int = 0
    cleared_bytes: int = 0


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def record_to_summary(record: EmailRecord) -> EmailSummary:
    """Convert an :class:`EmailRecord` to a lightweight :class:`EmailSummary`.

    Truncates ``body_text`` to :data:`PREVIEW_LENGTH` characters.
    """
    text = record.body_text or ""
    preview = text[:PREVIEW_LENGTH] + "..." if len(text) > PREVIEW_LENGTH else text

    return EmailSummary(
        uid=record.uid,
        subject=record.subject,
        sender=record.sender,
        sender_name=record.sender_name,
        date=record.date,
        preview=preview,
        is_seen=record.is_seen,
        is_flagged=record.is_flagged,
        is_answered=record.is_answered,
        has_attachments=record.has_attachments,
    )
