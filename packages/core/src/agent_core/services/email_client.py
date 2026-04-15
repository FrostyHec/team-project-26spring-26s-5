"""IMAP/SMTP email client for Tencent Exmail enterprise mailbox.

Handles protocol-level operations: IMAP SSL fetch, SMTP SSL send,
attachment downloading, and HTML body caching.

All blocking I/O (imaplib / smtplib) is offloaded to a thread via
``asyncio.to_thread`` so that the FastAPI event loop stays responsive.
"""

from __future__ import annotations

import asyncio
import email
import imaplib
import re
import smtplib
import ssl
from datetime import UTC, datetime, timedelta
from email import policy
from email.header import decode_header as email_decode_header
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import Any

from pathvalidate import sanitize_filename as _sanitize_filename

from agent_core.logging_utils import get_logger
from agent_core.models.email import (
    ATTACHMENT_CACHE_DIR,
    HTML_CACHE_DIR,
    AttachmentRecord,
    EmailConnectionTestResult,
    EmailRecord,
    ImapDefaults,
    now_iso,
)

logger = get_logger("services.email_client")

_UID_PATTERN = re.compile(r"UID\s+(\d+)")
_FLAGS_PATTERN = re.compile(r"FLAGS\s+\(([^)]*)\)")


# ---------------------------------------------------------------------------
# Helper functions (pure, no I/O)
# ---------------------------------------------------------------------------


def _decode_header(header: str | None) -> str:
    """Decode an RFC-2047 encoded email header to plain text."""
    if not header:
        return ""
    decoded_parts = email_decode_header(header)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(charset or "utf-8", errors="replace"))
            except (LookupError, UnicodeDecodeError):
                result.append(part.decode("utf-8", errors="replace"))
        else:
            result.append(str(part))
    return "".join(result)


def _parse_address(addr_str: str | None) -> tuple[str, str]:
    """Parse 'Name <email@example.com>' into (name, email)."""
    if not addr_str:
        return "", ""
    name, email_addr = parseaddr(addr_str)
    return _decode_header(name), email_addr


def _parse_address_list(addr_str: str | None) -> str:
    """Parse comma-separated address list into comma-separated emails."""
    if not addr_str:
        return ""
    addresses = []
    for part in addr_str.split(","):
        _, email_addr = _parse_address(part.strip())
        if email_addr:
            addresses.append(email_addr)
    return ", ".join(addresses)


def _parse_date(date_str: str | None) -> str:
    """Parse RFC-2822 date to ISO-8601 string."""
    if not date_str:
        return ""
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.isoformat()
    except (ValueError, TypeError):
        return date_str


def _imap_quote(folder: str) -> str:
    """Quote an IMAP mailbox name that contains spaces or special characters."""
    if folder.startswith('"'):
        return folder
    if " " in folder or any(c in folder for c in "()%*\\"):
        return f'"{folder}"'
    return folder


# ---------------------------------------------------------------------------
# EmailClient class
# ---------------------------------------------------------------------------


class EmailClient:
    """IMAP/SMTP client for Tencent Exmail.

    This class is stateless — it does not maintain persistent connections.
    Each operation opens a fresh connection, performs the action, and closes.

    Args:
        data_root: Base directory for cache storage.
    """

    def __init__(self, data_root: str = ".") -> None:
        self._data_root = Path(data_root)
        self._last_attachment_records: list[AttachmentRecord] = []

    def get_last_attachment_records(self) -> list[AttachmentRecord]:
        """Return attachment metadata from the most recent fetch_emails() call."""
        return self._last_attachment_records

    async def fetch_emails(
        self, account: str, password: str, *, days: int = 30, folder: str = "INBOX"
    ) -> list[EmailRecord]:
        """Fetch emails from IMAP server.

        Blocking IMAP I/O is offloaded to a thread so the async event
        loop stays responsive.

        Args:
            account: Email account (e.g., user@mail.sustech.edu.cn).
            password: Email password or authorization code.
            days: Number of days to look back.

        Returns:
            List of EmailRecord objects.
        """
        return await asyncio.to_thread(
            self._sync_fetch_emails, account, password, days, folder
        )

    # ---- synchronous IMAP fetch (runs in thread) ----

    def _sync_fetch_emails(
        self, account: str, password: str, days: int, folder: str = "INBOX"
    ) -> list[EmailRecord]:
        """Synchronous IMAP fetch — called via asyncio.to_thread."""
        records: list[EmailRecord] = []
        self._last_attachment_records = []

        # Calculate date threshold
        cutoff_date = datetime.now(UTC) - timedelta(days=days)
        cutoff_str = cutoff_date.strftime("%d-%b-%Y")

        # Connect to IMAP
        context = ssl.create_default_context()
        imap = imaplib.IMAP4_SSL(
            ImapDefaults.IMAP_HOST, int(ImapDefaults.IMAP_PORT), ssl_context=context
        )

        # STARRED is a virtual "folder": search FLAGGED on INBOX
        imap_folder = "INBOX" if folder == "__STARRED__" else folder

        try:
            imap.login(account, password)
            imap.select(_imap_quote(imap_folder), readonly=True)

            # Search for emails since cutoff date
            if folder == "__STARRED__":
                _, message_numbers = imap.search(None, "FLAGGED", f"SINCE {cutoff_str}")
            else:
                _, message_numbers = imap.search(None, f"SINCE {cutoff_str}")

            if not message_numbers or not message_numbers[0]:
                logger.info("No emails found in the last %d days", days)
                return records

            msg_nums = message_numbers[0].split()
            logger.info("Found %d emails to fetch", len(msg_nums))

            for num in msg_nums:
                record = self._fetch_single_email(imap, num, account, folder=folder)
                if record:
                    records.append(record)

        finally:
            try:
                imap.close()
            except Exception:
                pass
            imap.logout()

        return records

    def _fetch_single_email(
        self,
        imap: imaplib.IMAP4_SSL,
        msg_num: bytes,
        account: str,
        folder: str = "INBOX",
    ) -> EmailRecord | None:
        """Fetch metadata for a single email (synchronous, no file I/O).

        Fetches only IMAP flags and message headers (``RFC822.HEADER``), which
        is much faster than downloading full RFC822 bodies.  HTML and
        attachment files are **not** downloaded here — they are fetched lazily
        on the first detail view via :meth:`fetch_email_content`.

        .. note::
            Tencent Exmail places ``FLAGS`` **after** the RFC822 literal in the
            combined ``FETCH (UID RFC822 FLAGS)`` response (as a trailing bytes
            item), making it invisible to the standard metadata parser.  Using
            ``(UID FLAGS RFC822.HEADER)`` forces the server to include FLAGS
            **inside** the metadata tuple where :meth:`_parse_flags_from_meta`
            can read it reliably.
        """
        try:
            # Use RFC822.HEADER (headers only, no body) with FLAGS listed first.
            # Tencent Exmail IMAP returns FLAGS inside the metadata tuple when
            # the fetch spec starts with FLAGS, but puts them in a trailing
            # unparsed bytes item when RFC822 comes first.  Header-only fetch
            # is also significantly faster for large mailboxes.
            status, msg_data = imap.fetch(msg_num, "(UID FLAGS RFC822.HEADER)")
            if status != "OK" or not msg_data:
                logger.warning(
                    "IMAP FETCH returned non-OK status for msg %s: %s",
                    msg_num,
                    status,
                )
                return None

            uid_meta, raw_header = self._extract_fetch_payload(msg_data)
            if not raw_header:
                logger.warning(
                    "Skipping email %s: missing RFC822.HEADER payload", msg_num
                )
                return None

            uid = self._parse_uid_from_meta(uid_meta)
            if uid is None:
                uid = self._fetch_uid_fallback(imap, msg_num)
            if uid is None:
                logger.warning("Skipping email %s: unable to parse UID", msg_num)
                return None

            flags_str = self._parse_flags_from_meta(uid_meta)
            if not flags_str and flags_str != "":
                # Empty string is fine (no flags set); log only when the FLAGS
                # field is genuinely absent from the response metadata.
                logger.debug(
                    "FLAGS not found in metadata for UID %s (msg %s); raw uid_meta=%r",
                    uid,
                    msg_num,
                    uid_meta[:200],
                )
            is_seen = "\\Seen" in flags_str
            is_flagged = "\\Flagged" in flags_str
            is_answered = "\\Answered" in flags_str
            logger.debug(
                "UID %s flags: seen=%s flagged=%s answered=%s (raw=%r)",
                uid,
                is_seen,
                is_flagged,
                is_answered,
                flags_str,
            )

            # Parse MIME headers (no body parts in RFC822.HEADER)
            msg = email.message_from_bytes(raw_header, policy=policy.default)

            # Extract headers
            subject = _decode_header(msg.get("Subject"))
            sender_name, sender = _parse_address(msg.get("From"))
            recipients = _parse_address_list(msg.get("To"))
            cc = _parse_address_list(msg.get("Cc"))
            date_str = _parse_date(msg.get("Date"))
            message_id = msg.get("Message-ID", "")

            # body_text is not available from header-only fetch; it will be
            # populated lazily when the user opens the email (ensure_email_
            # content_fetched → mark_content_fetched writes body_text).
            body_text = ""

            # Heuristic attachment detection from outer Content-Type header.
            # multipart/mixed is the standard container for emails with regular
            # file attachments.  This is less precise than walking the full MIME
            # tree but avoids downloading RFC822 bodies during list sync.
            has_attachments = msg.get_content_type() == "multipart/mixed"

            return EmailRecord(
                uid=uid,
                message_id=message_id,
                subject=subject,
                sender=sender,
                sender_name=sender_name,
                recipients=recipients,
                cc=cc,
                date=date_str,
                body_text=body_text,
                html_local_path="",
                is_seen=is_seen,
                is_flagged=is_flagged,
                is_answered=is_answered,
                has_attachments=has_attachments,
                content_fetched=False,
                folder=folder,
                synced_at=now_iso(),
            )
        except Exception as e:
            logger.error("Failed to fetch email %s: %s", msg_num, e)
            return None

    def _extract_fetch_payload(self, msg_data: list[Any]) -> tuple[str, bytes | None]:
        """Extract IMAP metadata line and RFC822 payload from fetch response."""
        uid_meta = ""
        raw_email: bytes | None = None

        for item in msg_data:
            if not isinstance(item, tuple) or len(item) < 2:
                continue
            meta_part, body_part = item[0], item[1]
            if isinstance(meta_part, bytes):
                uid_meta = meta_part.decode(errors="replace")
            elif meta_part is not None:
                uid_meta = str(meta_part)
            if isinstance(body_part, (bytes, bytearray)):
                raw_email = bytes(body_part)
                break

        return uid_meta, raw_email

    def _parse_uid_from_meta(self, uid_meta: str) -> int | None:
        """Parse UID from an IMAP fetch metadata line."""
        match = _UID_PATTERN.search(uid_meta)
        if not match:
            return None
        return int(match.group(1))

    def _parse_flags_from_meta(self, uid_meta: str) -> str:
        """Parse FLAGS content from an IMAP fetch metadata line."""
        match = _FLAGS_PATTERN.search(uid_meta)
        if not match:
            return ""
        return match.group(1)

    def _fetch_uid_fallback(
        self, imap: imaplib.IMAP4_SSL, msg_num: bytes
    ) -> int | None:
        """Fallback: fetch UID only when full fetch metadata is incomplete."""
        status, uid_data = imap.fetch(msg_num, "(UID)")
        if status != "OK" or not uid_data:
            return None

        for item in uid_data:
            if not isinstance(item, tuple) or not item:
                continue
            meta = item[0]
            meta_text = (
                meta.decode(errors="replace") if isinstance(meta, bytes) else str(meta)
            )
            uid = self._parse_uid_from_meta(meta_text)
            if uid is not None:
                return uid
        return None

    def _extract_body(self, msg: EmailMessage) -> tuple[str, str]:
        """Extract plain text and HTML body from email message.

        Returns:
            Tuple of (plain_text, html_body).
        """
        plain_text = ""
        html_body = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        try:
                            plain_text = payload.decode(charset, errors="replace")
                        except (LookupError, UnicodeDecodeError):
                            plain_text = payload.decode("utf-8", errors="replace")
                elif content_type == "text/html":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        try:
                            html_body = payload.decode(charset, errors="replace")
                        except (LookupError, UnicodeDecodeError):
                            html_body = payload.decode("utf-8", errors="replace")
        else:
            content_type = msg.get_content_type()
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                try:
                    decoded = payload.decode(charset, errors="replace")
                except (LookupError, UnicodeDecodeError):
                    decoded = payload.decode("utf-8", errors="replace")
                if content_type == "text/html":
                    html_body = decoded
                else:
                    plain_text = decoded

        return plain_text, html_body

    def _save_html_cache(self, uid: int, html_content: str) -> str:
        """Save HTML body to local cache (synchronous).

        Returns:
            Relative path to the cached HTML file.
        """
        cache_dir = self._data_root / HTML_CACHE_DIR
        cache_dir.mkdir(parents=True, exist_ok=True)

        html_file = cache_dir / f"{uid}.html"
        html_file.write_text(html_content, encoding="utf-8")

        return str(Path(HTML_CACHE_DIR) / f"{uid}.html")

    def _process_attachments(self, msg: EmailMessage, uid: int) -> bool:
        """Process and save attachments and inline images (synchronous).

        Saves both regular attachments (Content-Disposition: attachment)
        and inline images (Content-ID header) to the cache directory.

        Args:
            msg: Email message object.
            uid: Email UID.

        Returns:
            True if attachments were found.
        """
        has_attachments = False

        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue

            content_disposition = part.get("Content-Disposition") or ""
            content_id = part.get("Content-ID") or ""
            filename = part.get_filename()

            # Skip text/plain and text/html body parts (no CID, no disposition)
            is_attachment = "attachment" in content_disposition.lower()
            is_inline = bool(content_id) and part.get_content_maintype() == "image"

            if not is_attachment and not is_inline:
                continue

            if not filename:
                # Generate filename from content-id for inline images
                if is_inline:
                    cid = content_id.strip("<>")
                    ext = part.get_content_subtype() or "bin"
                    filename = f"{cid}.{ext}"
                else:
                    continue

            filename = _decode_header(filename)
            has_attachments = True

            # Sanitize filename to prevent path traversal
            filename = (
                _sanitize_filename(filename, platform="auto") or f"attachment_{uid}"
            )

            # Save to cache
            att_dir = self._data_root / ATTACHMENT_CACHE_DIR / f"uid_{uid}"
            att_dir.mkdir(parents=True, exist_ok=True)

            att_path = (att_dir / filename).resolve()
            # Guard against path traversal: resolved path must stay within att_dir
            if not str(att_path).startswith(str(att_dir.resolve())):
                logger.warning("Skipping attachment with unsafe path: %s", filename)
                continue

            payload = part.get_payload(decode=True)
            if payload:
                att_path.write_bytes(payload)

                local_path = str(Path(ATTACHMENT_CACHE_DIR) / f"uid_{uid}" / filename)
                record = AttachmentRecord(
                    email_uid=uid,
                    filename=filename,
                    content_type=(
                        part.get_content_type() or "application/octet-stream"
                    ),
                    local_path=local_path,
                    file_size=len(payload),
                    download_time=now_iso(),
                )
                # Store Content-ID for CID mapping (strip angle brackets)
                if content_id:
                    record.content_id = content_id.strip("<>")
                self._last_attachment_records.append(record)

        return has_attachments

    def _has_attachments(self, msg: EmailMessage) -> bool:
        """Detect whether *msg* has attachments or inline images without saving files.

        Used during metadata-only sync phase :meth:`_fetch_single_email` so
        that ``EmailRecord.has_attachments`` is set correctly without writing
        anything to disk.
        """
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            content_disposition = part.get("Content-Disposition") or ""
            content_id = part.get("Content-ID") or ""
            is_attachment = "attachment" in content_disposition.lower()
            is_inline = bool(content_id) and part.get_content_maintype() == "image"
            if is_attachment or is_inline:
                return True
        return False

    async def fetch_email_content(
        self, uid: int, account: str, password: str, folder: str = "INBOX"
    ) -> tuple[str, list[AttachmentRecord], str]:
        """Fetch and cache HTML body + attachments for a specific email UID.

        This is the on-demand half of the lazy-fetch pattern.  It opens a
        fresh IMAP connection, retrieves the full message by UID, saves the
        HTML file and attachment files, and returns their metadata so the
        service layer can persist it.

        Args:
            uid: IMAP UID of the email to fetch.
            account: Email account.
            password: Email password / auth code.

        Returns:
            ``(html_local_path, attachment_records, body_text)`` where
            *html_local_path* is the relative path to the cached HTML file
            (empty string if the email has no HTML part),
            *attachment_records* is the list of
            :class:`~agent_core.models.email.AttachmentRecord` objects for
            saved attachments, and *body_text* is the extracted plain-text
            body (empty string when unavailable).

        Raises:
            RuntimeError: If the IMAP fetch fails or the email is not found.
        """
        return await asyncio.to_thread(
            self._sync_fetch_email_content, uid, account, password, folder
        )

    def _sync_fetch_email_content(
        self, uid: int, account: str, password: str, folder: str = "INBOX"
    ) -> tuple[str, list[AttachmentRecord], str]:
        """Synchronous IMAP fetch for a single email's full content.

        Opens the mailbox in read-write mode so that the explicit
        ``UID STORE +FLAGS (\\Seen)`` call in the caller (via
        :meth:`ensure_email_content_fetched`) can mark the message as read.
        Tencent Exmail does **not** auto-set ``\\Seen`` on an RFC822 fetch,
        so the explicit STORE is the only reliable method.
        """
        context = ssl.create_default_context()
        imap = imaplib.IMAP4_SSL(
            ImapDefaults.IMAP_HOST, int(ImapDefaults.IMAP_PORT), ssl_context=context
        )
        try:
            imap.login(account, password)
            imap_folder = "INBOX" if folder == "__STARRED__" else folder
            imap.select(_imap_quote(imap_folder))

            status, data = imap.uid("fetch", str(uid).encode(), "(RFC822)")
            if status != "OK" or not data:
                raise RuntimeError(f"IMAP UID FETCH failed for UID {uid}")

            raw_email: bytes | None = None
            for item in data:
                if (
                    isinstance(item, tuple)
                    and len(item) == 2
                    and isinstance(item[1], bytes)
                ):
                    raw_email = item[1]
                    break

            if raw_email is None:
                raise RuntimeError(f"No RFC822 payload returned for UID {uid}")

            msg = email.message_from_bytes(raw_email, policy=policy.default)

            # Save HTML; also capture body_text for immediate persistence
            body_text, html_body = self._extract_body(msg)
            html_local_path = ""
            if html_body:
                html_local_path = self._save_html_cache(uid, html_body)

            # Save inline images; create stub records for regular attachments
            self._last_attachment_records = []
            self._process_body_attachments(msg, uid, folder=folder)
            attachment_records = list(self._last_attachment_records)

            return html_local_path, attachment_records, body_text
        finally:
            try:
                imap.close()
            except Exception:
                pass
            try:
                imap.logout()
            except Exception:
                pass

    async def send_email(
        self,
        account: str,
        password: str,
        *,
        to: str,
        cc: str = "",
        subject: str = "",
        html_body: str = "",
        plain_body: str = "",
        in_reply_to: str = "",
        references: str = "",
        attachment_paths: list[str] | None = None,
    ) -> None:
        """Send an email via SMTP.

        Blocking SMTP I/O is offloaded to a thread.

        Args:
            account: Sender email account.
            password: Email password or authorization code.
            to: Comma-separated recipient addresses.
            cc: Comma-separated CC addresses.
            subject: Email subject.
            html_body: HTML body content.
            plain_body: Plain text body content.
            in_reply_to: Message-ID for reply threading.
            references: References header for threading.
            attachment_paths: List of attachment file paths (not implemented yet).
        """
        await asyncio.to_thread(
            self._sync_send_email,
            account,
            password,
            to,
            cc,
            subject,
            html_body,
            plain_body,
            in_reply_to,
            references,
        )

    # ---- synchronous SMTP send (runs in thread) ----

    def _sync_send_email(
        self,
        account: str,
        password: str,
        to: str,
        cc: str,
        subject: str,
        html_body: str,
        plain_body: str,
        in_reply_to: str,
        references: str,
    ) -> None:
        """Synchronous SMTP send — called via asyncio.to_thread."""
        msg = MIMEMultipart("alternative")
        msg["From"] = account
        msg["To"] = to
        if cc:
            msg["Cc"] = cc
        msg["Subject"] = subject
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
        if references:
            msg["References"] = references

        # Add body parts
        if plain_body:
            msg.attach(MIMEText(plain_body, "plain", "utf-8"))
        if html_body:
            msg.attach(MIMEText(html_body, "html", "utf-8"))

        # Connect to SMTP and send
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(
            ImapDefaults.SMTP_HOST, int(ImapDefaults.SMTP_PORT), context=context
        ) as smtp:
            smtp.login(account, password)
            recipients = [addr.strip() for addr in to.split(",") if addr.strip()]
            if cc:
                recipients.extend(
                    [addr.strip() for addr in cc.split(",") if addr.strip()]
                )
            smtp.sendmail(account, recipients, msg.as_string())

        logger.info("Email sent to %s", to)

    async def set_flag(
        self,
        account: str,
        password: str,
        uid: int,
        flag: Any,
        value: bool,
        folder: str = "INBOX",
    ) -> bool:
        """Set or clear a flag on an email via IMAP.

        Blocking IMAP I/O is offloaded to a thread.

        Args:
            account: Email account.
            password: Email password.
            uid: Email UID.
            flag: EmailFlag enum value.
            value: True to set, False to clear.

        Returns:
            True on success.
        """
        return await asyncio.to_thread(
            self._sync_set_flag, account, password, uid, flag, value, folder
        )

    # ---- synchronous IMAP flag update (runs in thread) ----

    def _sync_set_flag(
        self,
        account: str,
        password: str,
        uid: int,
        flag: Any,
        value: bool,
        folder: str = "INBOX",
    ) -> bool:
        """Synchronous IMAP flag update — called via asyncio.to_thread."""
        from agent_core.models.email import IMAP_FLAG_MAP

        imap_flag = IMAP_FLAG_MAP.get(flag)
        if not imap_flag:
            logger.warning("Unknown flag: %s", flag)
            return False

        context = ssl.create_default_context()
        imap = imaplib.IMAP4_SSL(
            ImapDefaults.IMAP_HOST, int(ImapDefaults.IMAP_PORT), ssl_context=context
        )

        try:
            imap.login(account, password)
            imap.select(_imap_quote(folder))

            command = "+FLAGS" if value else "-FLAGS"
            result, _ = imap.uid("STORE", str(uid), command, imap_flag)

            return result == "OK"
        except Exception as e:
            logger.error("Failed to set flag %s on UID %d: %s", flag, uid, e)
            return False
        finally:
            try:
                imap.close()
            except Exception:
                pass
            imap.logout()

    def _process_body_attachments(self, msg, uid: int, folder: str = "INBOX") -> None:
        """Save inline images; create stub AttachmentRecord rows for attachments.

        Regular attachments (Content-Disposition: attachment) are NOT written to
        disk here — only a stub ``AttachmentRecord`` with ``is_downloaded=False``
        is appended to ``self._last_attachment_records``.
        """
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue

            content_disposition = part.get("Content-Disposition") or ""
            content_id = part.get("Content-ID") or ""
            filename = part.get_filename()

            is_attachment = "attachment" in content_disposition.lower()
            is_inline = bool(content_id) and part.get_content_maintype() == "image"

            if not is_attachment and not is_inline:
                continue

            if not filename:
                if is_inline:
                    cid = content_id.strip("<>")
                    ext = part.get_content_subtype() or "bin"
                    filename = f"{cid}.{ext}"
                else:
                    continue

            filename = _decode_header(filename)
            filename = (
                _sanitize_filename(filename, platform="auto") or f"attachment_{uid}"
            )

            if is_inline:
                att_dir = self._data_root / ATTACHMENT_CACHE_DIR / f"uid_{uid}"
                att_dir.mkdir(parents=True, exist_ok=True)
                att_path = (att_dir / filename).resolve()
                if not str(att_path).startswith(str(att_dir.resolve())):
                    logger.warning("Skipping unsafe inline path: %s", filename)
                    continue
                payload = part.get_payload(decode=True)
                if payload:
                    att_path.write_bytes(payload)
                    local_path = str(
                        Path(ATTACHMENT_CACHE_DIR) / f"uid_{uid}" / filename
                    )
                    record = AttachmentRecord(
                        email_uid=uid,
                        email_folder=folder,
                        filename=filename,
                        content_type=part.get_content_type()
                        or "application/octet-stream",
                        local_path=local_path,
                        file_size=len(payload),
                        download_time=now_iso(),
                        is_downloaded=True,
                        content_id=content_id.strip("<>") if content_id else "",
                    )
                    self._last_attachment_records.append(record)
            else:
                payload = part.get_payload(decode=True)
                stub_size = len(payload) if payload else 0
                record = AttachmentRecord(
                    email_uid=uid,
                    email_folder=folder,
                    filename=filename,
                    content_type=part.get_content_type() or "application/octet-stream",
                    local_path="",
                    file_size=stub_size,
                    download_time="",
                    is_downloaded=False,
                )
                self._last_attachment_records.append(record)

    async def download_attachment_file(
        self,
        uid: int,
        att_filename: str,
        account: str,
        password: str,
        folder: str = "INBOX",
    ) -> tuple[str, int]:
        """Download a single regular attachment from IMAP and save to disk.

        Returns:
            ``(local_path, file_size)``

        Raises:
            RuntimeError: If the attachment is not found or IMAP fetch fails.
        """
        return await asyncio.to_thread(
            self._sync_download_attachment_file,
            uid,
            att_filename,
            account,
            password,
            folder,
        )

    def _sync_download_attachment_file(
        self,
        uid: int,
        att_filename: str,
        account: str,
        password: str,
        folder: str = "INBOX",
    ) -> tuple[str, int]:
        """Synchronous: fetch RFC822, find MIME part matching *att_filename*, save."""
        context = ssl.create_default_context()
        imap = imaplib.IMAP4_SSL(
            ImapDefaults.IMAP_HOST, int(ImapDefaults.IMAP_PORT), ssl_context=context
        )
        try:
            imap.login(account, password)
            imap_folder = "INBOX" if folder == "__STARRED__" else folder
            imap.select(_imap_quote(imap_folder), readonly=True)

            status, data = imap.uid("fetch", str(uid).encode(), "(RFC822)")
            if status != "OK" or not data:
                raise RuntimeError(f"IMAP UID FETCH failed for UID {uid}")

            raw_email: bytes | None = None
            for item in data:
                if (
                    isinstance(item, tuple)
                    and len(item) == 2
                    and isinstance(item[1], bytes)
                ):
                    raw_email = item[1]
                    break
            if raw_email is None:
                raise RuntimeError(f"No RFC822 payload for UID {uid}")

            msg = email.message_from_bytes(raw_email, policy=policy.default)

            for part in msg.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                content_disposition = part.get("Content-Disposition") or ""
                if "attachment" not in content_disposition.lower():
                    continue
                raw_fname = part.get_filename()
                if not raw_fname:
                    continue
                decoded_fname = _decode_header(raw_fname)
                sanitized = (
                    _sanitize_filename(decoded_fname, platform="auto")
                    or f"attachment_{uid}"
                )
                if sanitized != att_filename:
                    continue

                payload = part.get_payload(decode=True)
                if not payload:
                    raise RuntimeError(f"Empty payload for attachment {att_filename}")

                att_dir = self._data_root / ATTACHMENT_CACHE_DIR / f"uid_{uid}"
                att_dir.mkdir(parents=True, exist_ok=True)
                att_path = (att_dir / att_filename).resolve()
                if not str(att_path).startswith(str(att_dir.resolve())):
                    raise RuntimeError(f"Unsafe attachment path: {att_filename}")
                att_path.write_bytes(payload)
                local_path = str(
                    Path(ATTACHMENT_CACHE_DIR) / f"uid_{uid}" / att_filename
                )
                return local_path, len(payload)

            raise RuntimeError(
                f"Attachment '{att_filename}' not found in email UID {uid}"
            )
        finally:
            try:
                imap.close()
            except Exception:
                pass
            try:
                imap.logout()
            except Exception:
                pass

    async def expunge(
        self, account: str, password: str, uid: int, folder: str = "INBOX"
    ) -> bool:
        """EXPUNGE deleted messages from *folder* via IMAP."""
        return await asyncio.to_thread(
            self._sync_expunge, account, password, uid, folder
        )

    def _sync_expunge(self, account: str, password: str, uid: int, folder: str) -> bool:
        context = ssl.create_default_context()
        imap = imaplib.IMAP4_SSL(
            ImapDefaults.IMAP_HOST, int(ImapDefaults.IMAP_PORT), ssl_context=context
        )
        try:
            imap.login(account, password)
            imap.select(_imap_quote(folder))
            imap.expunge()
            return True
        except Exception as exc:
            logger.error("Expunge failed for UID %d in %s: %s", uid, folder, exc)
            return False
        finally:
            try:
                imap.close()
            except Exception:
                pass
            try:
                imap.logout()
            except Exception:
                pass

    async def copy_to_folder(
        self,
        account: str,
        password: str,
        uid: int,
        src_folder: str,
        dst_folder: str,
    ) -> bool:
        """Copy a message by UID from *src_folder* to *dst_folder* via IMAP."""
        return await asyncio.to_thread(
            self._sync_copy_to_folder, account, password, uid, src_folder, dst_folder
        )

    def _sync_copy_to_folder(
        self,
        account: str,
        password: str,
        uid: int,
        src_folder: str,
        dst_folder: str,
    ) -> bool:
        context = ssl.create_default_context()
        imap = imaplib.IMAP4_SSL(
            ImapDefaults.IMAP_HOST, int(ImapDefaults.IMAP_PORT), ssl_context=context
        )
        try:
            imap.login(account, password)
            imap.select(_imap_quote(src_folder))
            result, _ = imap.uid("copy", str(uid).encode(), _imap_quote(dst_folder))
            return result == "OK"
        except Exception as exc:
            logger.error(
                "Copy UID %d from %s to %s failed: %s", uid, src_folder, dst_folder, exc
            )
            return False
        finally:
            try:
                imap.close()
            except Exception:
                pass
            try:
                imap.logout()
            except Exception:
                pass

    async def test_connection(
        self, account: str, password: str
    ) -> EmailConnectionTestResult:
        """Test IMAP and SMTP connectivity.

        Blocking I/O is offloaded to a thread.

        Returns:
            Connection test result with status for each protocol.
        """
        return await asyncio.to_thread(self._sync_test_connection, account, password)

    # ---- synchronous connection test (runs in thread) ----

    def _sync_test_connection(
        self, account: str, password: str
    ) -> EmailConnectionTestResult:
        """Synchronous connection test — called via asyncio.to_thread."""
        imap_ok = False
        smtp_ok = False
        messages = []

        # Test IMAP
        try:
            context = ssl.create_default_context()
            imap = imaplib.IMAP4_SSL(
                ImapDefaults.IMAP_HOST,
                int(ImapDefaults.IMAP_PORT),
                ssl_context=context,
            )
            imap.login(account, password)
            imap.select("INBOX", readonly=True)
            imap.close()
            imap.logout()
            imap_ok = True
            messages.append("IMAP connection successful")
        except Exception as e:
            messages.append(f"IMAP failed: {str(e)}")

        # Test SMTP
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(
                ImapDefaults.SMTP_HOST,
                int(ImapDefaults.SMTP_PORT),
                context=context,
            ) as smtp:
                smtp.login(account, password)
            smtp_ok = True
            messages.append("SMTP connection successful")
        except Exception as e:
            messages.append(f"SMTP failed: {str(e)}")

        success = imap_ok and smtp_ok
        return EmailConnectionTestResult(
            success=success,
            message="; ".join(messages),
            imap_ok=imap_ok,
            smtp_ok=smtp_ok,
        )
