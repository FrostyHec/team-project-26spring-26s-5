"""Email tools — LLM-callable functions for reading and managing email.

All tools follow the ``register_*_tools(registry)`` convention for
auto-discovery.  Business logic delegates to
:class:`~agent_core.services.email_service.EmailService`.

Sensitivity levels
~~~~~~~~~~~~~~~~~~
* **SAFE** — read-only: list, read, get settings
* **SENSITIVE** — write: send, update flags, sync, change settings
"""

import json

from agent_core.logging_utils import get_logger
from agent_core.models.email import EmailFlag, SendEmailRequest
from agent_core.persistence.email_provider import get_email_service
from agent_core.tools.registry import ToolRegistry, ToolSensitivity

logger = get_logger("tools.email")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


async def _service():  # noqa: ANN202
    """Shortcut to obtain the email service singleton."""
    return await get_email_service()


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


async def list_emails(
    limit: int = 20,
    offset: int = 0,
    flagged_only: bool = False,
    unseen_only: bool = False,
) -> str:
    """List email summaries from the local store.

    Args:
        limit: Maximum number of results (default 20).
        offset: Pagination offset.
        flagged_only: Only return starred emails.
        unseen_only: Only return unread emails.

    Returns:
        JSON array of email summaries.
    """
    svc = await _service()
    summaries = await svc.list_emails(
        limit=limit,
        offset=offset,
        flagged_only=flagged_only,
        unseen_only=unseen_only,
    )
    return json.dumps([s.model_dump() for s in summaries], ensure_ascii=False, indent=2)


async def read_email(uid: int) -> str:
    """Read the full content of an email by UID.

    Args:
        uid: The IMAP UID of the email.

    Returns:
        JSON object with email detail (subject, body, attachments, etc.).
    """
    svc = await _service()
    detail = await svc.get_email_detail(uid)
    if detail is None:
        return json.dumps({"error": f"Email UID {uid} not found"})
    return json.dumps(detail.model_dump(), ensure_ascii=False, indent=2)


async def count_emails() -> str:
    """Return the total number of locally stored emails.

    Returns:
        JSON object with ``total`` count.
    """
    svc = await _service()
    total = await svc.count_emails()
    return json.dumps({"total": total})


async def sync_emails(days: int | None = None) -> str:
    """Pull new emails from the mail server via IMAP.

    Args:
        days: How far back to fetch. None uses the configured default.

    Returns:
        JSON object with sync result (new, updated, total counts).
    """
    svc = await _service()
    result = await svc.sync_emails(days=days)
    return json.dumps(result.model_dump(), ensure_ascii=False, indent=2)


async def update_email_flag(uid: int, flag: str, value: bool) -> str:
    """Set or clear a flag on an email (seen/flagged/answered).

    Args:
        uid: The IMAP UID.
        flag: One of 'seen', 'flagged', 'answered'.
        value: True to set, False to clear.

    Returns:
        JSON object with ``success`` boolean.
    """
    try:
        email_flag = EmailFlag(flag)
    except ValueError:
        return json.dumps(
            {"error": f"Invalid flag '{flag}'. Must be one of: seen, flagged, answered"}
        )
    svc = await _service()
    ok = await svc.update_flag(uid, email_flag, value)
    return json.dumps({"success": ok})


async def send_email(
    to: str,
    subject: str,
    body: str,
    cc: str = "",
    in_reply_to: str = "",
) -> str:
    """Send an email via SMTP.

    Args:
        to: Comma-separated recipient addresses.
        subject: Email subject line.
        body: Plain-text body content.
        cc: Comma-separated CC addresses.
        in_reply_to: Message-ID for reply threading.

    Returns:
        JSON confirmation.
    """
    svc = await _service()
    request = SendEmailRequest(
        to=to,
        cc=cc,
        subject=subject,
        plain_body=body,
        in_reply_to=in_reply_to,
    )
    await svc.send_email(request)
    return json.dumps({"status": "sent", "to": to, "subject": subject})


async def get_email_settings() -> str:
    """Return current email settings (fetch_days, auto_sync).

    Returns:
        JSON object with settings.
    """
    svc = await _service()
    info = await svc.get_email_settings()
    return json.dumps(info.model_dump(), ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_email_tools(registry: ToolRegistry) -> None:
    """Register all email tools with the given registry.

    Called automatically by :func:`agent_core.tools.auto_discover_and_register`.
    """

    @registry.register(
        description=(
            "List email summaries from the local mailbox. "
            "Returns subject, sender, date, flags, and a short preview. "
            "Supports pagination and filtering by flagged/unseen."
        ),
        sensitivity=ToolSensitivity.SAFE,
        name="list_emails",
    )
    async def _list_emails(
        limit: int = 20,
        offset: int = 0,
        flagged_only: bool = False,
        unseen_only: bool = False,
    ) -> str:
        return await list_emails(limit, offset, flagged_only, unseen_only)

    @registry.register(
        description=(
            "Read the full content of an email by its UID. "
            "Returns subject, sender, recipients, body text, and attachment list."
        ),
        sensitivity=ToolSensitivity.SAFE,
        name="read_email",
    )
    async def _read_email(uid: int) -> str:
        return await read_email(uid)

    @registry.register(
        description="Return the total count of locally stored emails.",
        sensitivity=ToolSensitivity.SAFE,
        name="count_emails",
    )
    async def _count_emails() -> str:
        return await count_emails()

    @registry.register(
        description=(
            "Sync (pull) new emails from the IMAP mail server. "
            "Optionally specify how many days back to fetch."
        ),
        sensitivity=ToolSensitivity.SENSITIVE,
        name="sync_emails",
    )
    async def _sync_emails(days: int | None = None) -> str:
        return await sync_emails(days)

    @registry.register(
        description=(
            "Set or clear a flag on an email. "
            "flag must be one of: 'seen', 'flagged', 'answered'. "
            "value=true to set, value=false to clear."
        ),
        sensitivity=ToolSensitivity.SENSITIVE,
        name="update_email_flag",
    )
    async def _update_email_flag(uid: int, flag: str, value: bool) -> str:
        return await update_email_flag(uid, flag, value)

    @registry.register(
        description=(
            "Send an email via SMTP. Requires 'to' (recipient) and 'subject'. "
            "Optionally provide 'cc' and 'in_reply_to' for replies."
        ),
        sensitivity=ToolSensitivity.SENSITIVE,
        name="send_email",
    )
    async def _send_email(
        to: str,
        subject: str,
        body: str,
        cc: str = "",
        in_reply_to: str = "",
    ) -> str:
        return await send_email(to, subject, body, cc, in_reply_to)

    @registry.register(
        description="Return current email settings (fetch_days, auto_sync).",
        sensitivity=ToolSensitivity.SAFE,
        name="get_email_settings",
    )
    async def _get_email_settings() -> str:
        return await get_email_settings()
