"""Email business-logic service — single source of truth for email operations.

Orchestrates :class:`~agent_core.services.email_client.EmailClient` (protocol)
and :class:`~agent_core.persistence.email_store.EmailStore` (persistence).
Both the REST API routes and the LLM tool functions delegate here so that
business rules live in exactly one place.

Architecture::

    api/routes/email.py (REST) ─┐
                                 ├→ EmailService ─┬→ EmailStore  (SQLite)
    tools/email.py  (LLM Tool) ─┘                └→ EmailClient (IMAP/SMTP)
"""

from __future__ import annotations

import shutil
from pathlib import Path

from agent_core.logging_utils import get_logger
from agent_core.models.email import (
    ATTACHMENT_CACHE_DIR,
    HTML_CACHE_DIR,
    AttachmentRecord,
    ClearCacheResult,
    EmailConnectionTestResult,
    EmailDetail,
    EmailFlag,
    EmailSettingsInfo,
    EmailSummary,
    EmailSyncResult,
    MailboxFolder,
    SendEmailRequest,
    now_iso,
    record_to_summary,
)
from agent_core.persistence.email_store import EmailStore
from agent_core.persistence.profile_store import ProfileStore
from agent_core.services.email_client import EmailClient

logger = get_logger("services.email")


class AttachmentNotFoundError(ValueError):
    """Raised when a requested attachment ID does not exist in the store."""

    def __init__(self, att_id: int) -> None:
        self.att_id = att_id
        super().__init__(f"Attachment {att_id} not found")


class EmailService:
    """High-level email operations consumed by controllers and tools.

    Args:
        email_store: Persistence layer for email records.
        profile_store: User credential store (provides decrypted passwords).
        email_client: Protocol-level IMAP/SMTP client.
        data_root: Project root for cache directories.
    """

    def __init__(
        self,
        email_store: EmailStore,
        profile_store: ProfileStore,
        email_client: EmailClient,
        *,
        data_root: str = ".",
    ) -> None:
        self._store = email_store
        self._profile = profile_store
        self._client = email_client
        self._data_root = Path(data_root)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_credentials(self) -> tuple[str, str]:
        """Fetch the email account and decrypted password.

        Raises:
            ValueError: If the account or password is not configured.
        """
        profile = await self._profile.get_profile()
        account = profile.email_account
        password = await self._profile.get_decrypted_email_password()
        if not account or not password:
            raise ValueError(
                "Email credentials not configured. "
                "Please set email_account and email_password in Settings."
            )
        return account, password

    # ------------------------------------------------------------------
    # Sync (IMAP pull)
    # ------------------------------------------------------------------

    async def sync_emails(
        self, *, days: int | None = None, folder: str = "INBOX"
    ) -> EmailSyncResult:
        """Pull new emails from IMAP and upsert into the local store.

        Args:
            days: Number of days to look back.  ``None`` → use the
                stored ``email_fetch_days`` setting.
            folder: IMAP mailbox to sync (default ``INBOX``).

        Returns:
            An :class:`EmailSyncResult` with counts.
        """
        account, password = await self._get_credentials()
        if days is None:
            days = await self._store.get_fetch_days()

        existing_uids = await self._store.get_all_uids(folder=folder)
        records = await self._client.fetch_emails(
            account, password, days=days, folder=folder
        )
        att_records = self._client.get_last_attachment_records()

        new_count = 0
        updated_count = 0
        for rec in records:
            if rec.uid in existing_uids:
                updated_count += 1
            else:
                new_count += 1
            await self._store.upsert_email(rec)

        # Save attachment metadata
        for att in att_records:
            await self._store.upsert_attachment(att)

        total = await self._store.count_emails()
        synced_at = now_iso()

        logger.info(
            "Sync complete: %d new, %d updated, %d total",
            new_count,
            updated_count,
            total,
        )
        return EmailSyncResult(
            new_count=new_count,
            updated_count=updated_count,
            total_count=total,
            synced_at=synced_at,
        )

    # ------------------------------------------------------------------
    # List / detail
    # ------------------------------------------------------------------

    async def list_emails(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        flagged_only: bool = False,
        unseen_only: bool = False,
        folder: str | None = None,
    ) -> list[EmailSummary]:
        """Return a paginated list of email summaries from the local store."""
        records = await self._store.list_emails(
            limit=limit,
            offset=offset,
            flagged_only=flagged_only,
            unseen_only=unseen_only,
            folder=folder,
        )
        return [record_to_summary(r) for r in records]

    async def get_email_detail(
        self, uid: int, folder: str = "INBOX"
    ) -> EmailDetail | None:
        """Get full email detail including attachments.

        Returns ``None`` if the UID is not in the local store.
        """
        record = await self._store.get_email(uid, folder=folder)
        if record is None:
            return None
        attachments = await self._store.get_attachments(uid, email_folder=folder)
        return EmailDetail(
            uid=record.uid,
            message_id=record.message_id,
            subject=record.subject,
            sender=record.sender,
            sender_name=record.sender_name,
            recipients=record.recipients,
            cc=record.cc,
            date=record.date,
            body_text=record.body_text,
            html_local_path=record.html_local_path,
            is_seen=record.is_seen,
            is_flagged=record.is_flagged,
            is_answered=record.is_answered,
            has_attachments=record.has_attachments,
            attachments=attachments,
        )

    async def ensure_email_content_fetched(
        self, uid: int, folder: str = "INBOX"
    ) -> EmailDetail | None:
        """Return full email detail, fetching HTML and attachments on demand.

        Implements the lazy-fetch pattern from the A005 spec:

        1. If the email is not in the local store → return ``None``.
        2. If ``content_fetched`` is ``True`` → return cached detail.
        3. Otherwise → open IMAP, download HTML + attachments, cache them,
           mark the record as fetched, then return the updated detail.

        If the IMAP fetch fails (e.g. credentials missing, network error),
        the error is **propagated** — the caller is responsible for surfacing
        it to the user.

        Args:
            uid: IMAP UID of the email.

        Returns:
            :class:`~agent_core.models.email.EmailDetail`, or ``None`` if
            the email is not in the local store.

        Raises:
            ValueError: If email credentials are not configured.
            RuntimeError: If the IMAP fetch fails.
        """
        record = await self._store.get_email(uid, folder=folder)
        if record is None:
            return None

        if not record.content_fetched:
            account, password = await self._get_credentials()
            result = await self._client.fetch_email_content(
                uid, account, password, folder=record.folder
            )
            html_local_path, att_records, body_text = result
            # Persist attachment records
            for att in att_records:
                await self._store.upsert_attachment(att)
            # Mark the email record as fetched (also persists body_text)
            await self._store.mark_content_fetched(
                uid, html_local_path, body_text=body_text, folder=folder
            )
            # Explicitly mark the email as read on the IMAP server.
            # RFC 3501 says RFC822 fetch in R/W mode SHOULD set \Seen
            # implicitly, but Tencent Enterprise Email (and some other
            # servers) may not honour this.  An explicit STORE is the
            # only reliable cross-server mechanism.
            if not record.is_seen:
                await self._client.set_flag(
                    account, password, uid, EmailFlag.SEEN, True, folder=folder
                )
                await self._store.update_flags(uid, current_folder=folder, is_seen=True)
            logger.info(
                "Lazy-fetched content for UID %d: html=%r, attachments=%d",
                uid,
                html_local_path,
                len(att_records),
            )

        return await self.get_email_detail(uid, folder=folder)

    async def count_emails(self) -> int:
        """Return the total number of locally stored emails."""
        return await self._store.count_emails()

    # ------------------------------------------------------------------
    # Flags
    # ------------------------------------------------------------------

    async def update_flag(
        self, uid: int, flag: EmailFlag, value: bool, folder: str = "INBOX"
    ) -> bool:
        """Update a flag both on IMAP and in the local store.

        Returns True on success.
        """
        account, password = await self._get_credentials()
        record = await self._store.get_email(uid, folder=folder)
        if record is None:
            return False

        if flag == EmailFlag.DELETED and value:
            # Move to trash: set \Deleted on IMAP + EXPUNGE
            imap_ok = await self._client.set_flag(
                account, password, uid, flag, True, folder=folder
            )
            if imap_ok:
                await self._client.expunge(account, password, uid, folder=folder)
            # Move folder tag to trash in local DB
            await self._store.update_flags(
                uid, current_folder=folder, folder=MailboxFolder.TRASH
            )
            return imap_ok

        if flag == EmailFlag.SPAM and value:
            # Copy to Junk then delete from current folder
            await self._client.copy_to_folder(
                account, password, uid, src_folder=folder, dst_folder=MailboxFolder.SPAM
            )
            await self._client.set_flag(
                account, password, uid, EmailFlag.DELETED, True, folder=folder
            )
            await self._client.expunge(account, password, uid, folder=folder)
            await self._store.update_flags(
                uid, current_folder=folder, folder=MailboxFolder.SPAM
            )
            return True

        # Standard flag update (SEEN / FLAGGED / ANSWERED)
        imap_ok = await self._client.set_flag(
            account, password, uid, flag, value, folder=folder
        )
        if not imap_ok:
            logger.warning(
                "IMAP flag update failed for UID %d flag=%s value=%s; "
                "updating local store anyway",
                uid,
                flag,
                value,
            )

        # Update local store
        kwargs: dict[str, bool] = {}
        if flag == EmailFlag.SEEN:
            kwargs["is_seen"] = value
        elif flag == EmailFlag.FLAGGED:
            kwargs["is_flagged"] = value
        elif flag == EmailFlag.ANSWERED:
            kwargs["is_answered"] = value
        store_ok = await self._store.update_flags(uid, current_folder=folder, **kwargs)
        return store_ok

    # ------------------------------------------------------------------
    # Send / reply
    # ------------------------------------------------------------------

    async def send_email(self, request: SendEmailRequest) -> None:
        """Send an email via SMTP.

        Args:
            request: Fully populated send request.

        Raises:
            ValueError: If credentials are not configured.
        """
        account, password = await self._get_credentials()
        await self._client.send_email(
            account,
            password,
            to=request.to,
            cc=request.cc,
            subject=request.subject,
            html_body=request.html_body,
            plain_body=request.plain_body,
            in_reply_to=request.in_reply_to,
            references=request.references,
            attachment_paths=request.attachment_paths,
        )
        logger.info("Email sent via service to %s", request.to)

    # ------------------------------------------------------------------
    # Attachment download (on-demand)
    # ------------------------------------------------------------------

    async def download_attachment(
        self, uid: int, att_id: int, folder: str = "INBOX"
    ) -> AttachmentRecord:
        """Download a single attachment from IMAP and persist metadata.

        Args:
            uid: IMAP UID of the parent email.
            att_id: Surrogate PK of the AttachmentRecord.

        Returns:
            Updated :class:`AttachmentRecord` with ``is_downloaded=True``.

        Raises:
            AttachmentNotFoundError: If the attachment ID does not exist.
            ValueError: If credentials are not configured.
            RuntimeError: If the IMAP download fails.
        """
        att = await self._store.get_attachment(att_id)
        if att is None:
            raise AttachmentNotFoundError(att_id)
        if att.is_downloaded and att.local_path:
            return att  # already cached

        account, password = await self._get_credentials()

        local_path, file_size = await self._client.download_attachment_file(
            uid, att.filename, account, password, folder=folder
        )
        updated = await self._store.mark_attachment_downloaded(
            att_id, local_path, file_size
        )
        if updated is None:
            raise RuntimeError(f"Failed to update attachment {att_id} after download")
        logger.info("Downloaded attachment %s for UID %d", att.filename, uid)
        return updated

    # ------------------------------------------------------------------
    # Connection test
    # ------------------------------------------------------------------

    async def test_connection(self) -> EmailConnectionTestResult:
        """Test IMAP and SMTP with the stored credentials."""
        account, password = await self._get_credentials()
        return await self._client.test_connection(account, password)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    async def get_email_settings(self) -> EmailSettingsInfo:
        """Return current email-specific settings."""
        fetch_days = await self._store.get_fetch_days()
        auto_sync = await self._store.get_auto_sync()
        return EmailSettingsInfo(
            email_fetch_days=fetch_days,
            auto_sync=auto_sync,
        )

    async def update_email_settings(
        self, *, fetch_days: int | None = None, auto_sync: bool | None = None
    ) -> EmailSettingsInfo:
        """Update email settings.  Only non-None values are changed."""
        if fetch_days is not None:
            await self._store.set_fetch_days(fetch_days)
        if auto_sync is not None:
            await self._store.set_auto_sync(auto_sync)
        return await self.get_email_settings()

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    async def clear_cache(self) -> ClearCacheResult:
        """Delete all cached HTML and attachment files, and DB records.

        Returns:
            A :class:`ClearCacheResult` with stats.
        """
        cleared_files = 0
        cleared_bytes = 0

        for cache_dir_name in (HTML_CACHE_DIR, ATTACHMENT_CACHE_DIR):
            cache_dir = self._data_root / cache_dir_name
            if cache_dir.exists():
                for fpath in cache_dir.rglob("*"):
                    if fpath.is_file():
                        cleared_files += 1
                        cleared_bytes += fpath.stat().st_size
                shutil.rmtree(cache_dir)

        # Clear DB attachment records
        await self._store.delete_all_attachments()
        # Reset html_local_path / content_fetched so the UI stays consistent.
        # Note: has_attachments is preserved — it reflects IMAP truth, not cache state.
        await self._store.reset_cache_fields()

        logger.info("Cache cleared: %d files, %d bytes", cleared_files, cleared_bytes)
        return ClearCacheResult(
            cleared_files=cleared_files,
            cleared_bytes=cleared_bytes,
        )

    async def delete_all_data(self) -> int:
        """Delete ALL email data (records + cache). Returns email count deleted."""
        count = await self._store.delete_all_emails()
        await self._store.delete_all_attachments()
        # Remove cache directories
        for cache_dir_name in (HTML_CACHE_DIR, ATTACHMENT_CACHE_DIR):
            cache_dir = self._data_root / cache_dir_name
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
        logger.info("Deleted all email data: %d emails", count)
        return count

    async def get_html_with_cid_replacement(
        self, uid: int, folder: str = "INBOX"
    ) -> str | None:
        """Get HTML body with CID references replaced by API URLs.

        Args:
            uid: Email UID.
            folder: IMAP folder the email belongs to.

        Returns:
            HTML content with rewritten CID refs, or None if not found.
        """
        import re

        detail = await self.get_email_detail(uid, folder=folder)
        if not detail or not detail.html_local_path:
            return None

        html_path = self._data_root / detail.html_local_path
        if not html_path.is_file():
            return None

        html_content = html_path.read_text(encoding="utf-8")

        # Build CID -> attachment API URL mapping
        cid_map: dict[str, str] = {}
        for att in detail.attachments:
            if att.content_id and att.id is not None:
                url = f"/api/email/{uid}/attachments/{att.id}"
                cid_map[att.content_id] = url
            if att.id is not None:
                url = f"/api/email/{uid}/attachments/{att.id}"
                cid_map[att.filename] = url

        def replace_cid(match: re.Match[str]) -> str:
            cid = match.group(1).strip("<>")
            # Try exact content_id match first, then filename
            if cid in cid_map:
                return f'src="{cid_map[cid]}"'
            # Fuzzy match: CID may contain or be contained by filename
            for key, url in cid_map.items():
                if cid in key or key in cid:
                    return f'src="{url}"'
            return match.group(0)

        html_content = re.sub(
            r'src=["\']cid:([^"\']+)["\']',
            replace_cid,
            html_content,
            flags=re.IGNORECASE,
        )

        return html_content
