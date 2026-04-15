"""SQLite-backed email persistence — powered by SQLModel async ORM.

Provides async CRUD for email records and attachments using SQLModel +
SQLAlchemy async engine, following the same pattern as
:class:`~agent_core.persistence.deadline_store.DeadlineStore`.

The Store layer is a pure executor: it receives well-typed model
objects from the Service layer and translates them into DB operations.
No business logic lives here.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from agent_core.logging_utils import get_logger
from agent_core.models.email import (
    DEFAULT_FETCH_DAYS,
    AttachmentRecord,
    EmailRecord,
    EmailSettingsRecord,
)

logger = get_logger("persistence.email")

# ---------------------------------------------------------------------------
# Setting key constants (used in email_settings table)
# ---------------------------------------------------------------------------

_KEY_FETCH_DAYS = "email_fetch_days"
_KEY_AUTO_SYNC = "auto_sync"


class EmailStore:
    """Async SQLite store for emails, attachments, and email settings.

    Uses SQLModel + SQLAlchemy async engine — all queries are expressed
    via the ORM with no hand-written SQL.

    Usage::

        store = EmailStore(":memory:")
        await store.initialize()
        await store.upsert_email(record)
        emails = await store.list_emails()
        await store.close()
    """

    def __init__(self, db_path: str = "email.db") -> None:
        self.db_path = db_path
        self._engine = None  # type: ignore[assignment]

    @property
    def is_connected(self) -> bool:
        """Return *True* if the engine has been initialised."""
        return self._engine is not None

    async def initialize(self) -> None:
        """Create the async engine and ensure the schema exists."""
        url = f"sqlite+aiosqlite:///{self.db_path}"
        self._engine = create_async_engine(url, echo=False)
        async with self._engine.begin() as conn:
            await conn.run_sync(EmailRecord.metadata.create_all)
        await self._migrate()
        logger.info("Email store initialised at %s", self.db_path)

    async def _migrate(self) -> None:
        """Apply forward-only schema migrations for new columns and PK changes.

        Uses SQLite's ``PRAGMA table_info`` to detect missing columns and
        adds them via ``ALTER TABLE … ADD COLUMN`` so existing databases
        are upgraded in-place without data loss.

        Also recreates the ``emails`` table if it still uses the old
        single-column primary key on ``uid`` so that emails from different
        IMAP mailboxes (INBOX, Sent, …) can share the same UID value.
        """
        if self._engine is None:
            return

        import sqlalchemy

        async with self._engine.connect() as conn:
            # Step 1 — column additions (must run before PK recreation so the
            # backup table already has all expected columns).
            col_migrations: list[tuple[str, str, str]] = [
                ("emails", "folder", "TEXT DEFAULT 'INBOX'"),
                ("emails", "content_fetched", "INTEGER DEFAULT 0"),
                ("attachments", "is_downloaded", "INTEGER DEFAULT 0"),
                ("attachments", "email_folder", "TEXT DEFAULT 'INBOX'"),
            ]
            for table, column, sql_type in col_migrations:
                result = await conn.execute(
                    sqlalchemy.text(f"PRAGMA table_info({table})")
                )
                columns = {row[1] for row in result.fetchall()}
                if column not in columns:
                    await conn.execute(
                        sqlalchemy.text(
                            f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"
                        )
                    )
                    await conn.commit()
                    logger.info("Migration: added column %s.%s", table, column)

            # Step 2 — composite PK migration for the emails table.
            pk_result = await conn.execute(sqlalchemy.text("PRAGMA table_info(emails)"))
            rows = pk_result.fetchall()
            pk_cols = [row[1] for row in rows if row[5] > 0]
            if pk_cols == ["uid"]:
                logger.info(
                    "Migration: recreating emails table with composite PK (uid, folder)"
                )
                await conn.execute(
                    sqlalchemy.text("ALTER TABLE emails RENAME TO emails_old")
                )
                await conn.execute(
                    sqlalchemy.text("""
                        CREATE TABLE emails (
                            uid       INTEGER NOT NULL,
                            message_id VARCHAR DEFAULT '',
                            subject    VARCHAR DEFAULT '',
                            sender     VARCHAR DEFAULT '',
                            sender_name VARCHAR DEFAULT '',
                            recipients VARCHAR DEFAULT '',
                            cc         VARCHAR DEFAULT '',
                            date       VARCHAR DEFAULT '',
                            body_text  VARCHAR DEFAULT '',
                            html_local_path VARCHAR DEFAULT '',
                            is_seen         INTEGER DEFAULT 0,
                            is_flagged      INTEGER DEFAULT 0,
                            is_answered     INTEGER DEFAULT 0,
                            has_attachments INTEGER DEFAULT 0,
                            content_fetched INTEGER DEFAULT 0,
                            folder     VARCHAR DEFAULT 'INBOX',
                            synced_at  VARCHAR DEFAULT '',
                            PRIMARY KEY (uid, folder)
                        )
                    """)
                )
                await conn.execute(
                    sqlalchemy.text("""
                        INSERT INTO emails (
                            uid, message_id, subject, sender, sender_name,
                            recipients, cc, date, body_text, html_local_path,
                            is_seen, is_flagged, is_answered, has_attachments,
                            content_fetched, folder, synced_at
                        )
                        SELECT
                            uid, message_id, subject, sender, sender_name,
                            recipients, cc, date, body_text, html_local_path,
                            is_seen, is_flagged, is_answered, has_attachments,
                            COALESCE(content_fetched, 0),
                            COALESCE(folder, 'INBOX'),
                            synced_at
                        FROM emails_old
                    """)
                )
                await conn.execute(sqlalchemy.text("DROP TABLE emails_old"))
                await conn.commit()
                logger.info("Migration: composite PK migration complete")

    async def close(self) -> None:
        """Dispose the engine and release connections."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None

    def _session(self) -> AsyncSession:
        """Return a new async ORM session."""
        if self._engine is None:
            raise RuntimeError("EmailStore not initialised — call initialize() first")
        return AsyncSession(self._engine)

    # ------------------------------------------------------------------
    # Email CRUD
    # ------------------------------------------------------------------

    async def upsert_email(self, record: EmailRecord) -> EmailRecord:
        """Insert or update an email record (keyed by ``(uid, folder)``).

        On conflict the existing row is updated with the new data in-place.
        Two emails from different IMAP mailboxes may share the same ``uid``
        value, so the lookup always uses the composite key.
        """
        async with self._session() as session:
            result = await session.exec(
                select(EmailRecord).where(
                    EmailRecord.uid == record.uid,
                    EmailRecord.folder == record.folder,
                )
            )
            existing = result.first()
            if existing is not None:
                # Update fields from the incoming (IMAP-derived) record, but
                # preserve locally-computed fields that are never populated by
                # the header-only sync fetch.
                # NOTE: is_seen is intentionally NOT preserved so that a
                # "mark unread" action from another client (which clears
                # \Seen on the IMAP server) is reflected correctly on the
                # next sync.
                _preserve_if_truthy = frozenset(
                    {"content_fetched", "html_local_path", "body_text"}
                )
                for field_name in EmailRecord.model_fields:
                    if field_name in ("uid", "folder"):
                        continue
                    new_val = getattr(record, field_name)
                    if field_name in _preserve_if_truthy and not new_val:
                        # Don't overwrite a truthy local value with a falsy sync value
                        continue
                    setattr(existing, field_name, new_val)
                session.add(existing)
                await session.commit()
                await session.refresh(existing)
                return existing
            else:
                session.add(record)
                await session.commit()
                await session.refresh(record)
                return record

    async def get_email(self, uid: int, folder: str = "INBOX") -> EmailRecord | None:
        """Fetch a single email by its composite key ``(uid, folder)``."""
        async with self._session() as session:
            result = await session.exec(
                select(EmailRecord).where(
                    EmailRecord.uid == uid,
                    EmailRecord.folder == folder,
                )
            )
            return result.first()

    async def list_emails(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        flagged_only: bool = False,
        unseen_only: bool = False,
        folder: str | None = None,
    ) -> list[EmailRecord]:
        """Return a paginated list of emails, newest first."""
        statement = select(EmailRecord)
        if flagged_only:
            statement = statement.where(EmailRecord.is_flagged == True)  # noqa: E712
        if unseen_only:
            statement = statement.where(EmailRecord.is_seen == False)  # noqa: E712
        if folder is not None:
            statement = statement.where(EmailRecord.folder == folder)
        statement = (
            statement.order_by(col(EmailRecord.date).desc()).offset(offset).limit(limit)
        )
        async with self._session() as session:
            results = await session.exec(statement)
            return list(results.all())

    async def count_emails(self) -> int:
        """Return the total number of stored emails."""
        async with self._session() as session:
            result = await session.exec(select(func.count()).select_from(EmailRecord))
            return result.one()

    async def get_max_uid(self, folder: str = "INBOX") -> int:
        """Return the highest UID in the given folder, or 0 if empty."""
        async with self._session() as session:
            result = await session.exec(
                select(func.max(EmailRecord.uid)).where(EmailRecord.folder == folder)
            )
            val = result.one()
            return val if val is not None else 0

    async def get_all_uids(self, folder: str = "INBOX") -> set[int]:
        """Return the set of all stored email UIDs in the given folder."""
        async with self._session() as session:
            result = await session.exec(
                select(EmailRecord.uid).where(EmailRecord.folder == folder)
            )
            return set(result.all())

    async def update_flags(
        self,
        uid: int,
        *,
        current_folder: str = "INBOX",
        is_seen: bool | None = None,
        is_flagged: bool | None = None,
        is_answered: bool | None = None,
        folder: str | None = None,
    ) -> bool:
        """Update flag columns for a single email.

        Uses the composite key ``(uid, current_folder)`` for the lookup.
        The optional *folder* kwarg, when set, moves the email to a new
        mailbox folder in the local store (e.g. Trash or Spam).
        Only non-``None`` arguments are applied.  Returns ``True`` if
        at least one flag was changed.
        """
        updates: dict = {}
        if is_seen is not None:
            updates["is_seen"] = is_seen
        if is_flagged is not None:
            updates["is_flagged"] = is_flagged
        if is_answered is not None:
            updates["is_answered"] = is_answered
        if folder is not None:
            updates["folder"] = folder

        if not updates:
            return False

        async with self._session() as session:
            result = await session.exec(
                select(EmailRecord).where(
                    EmailRecord.uid == uid,
                    EmailRecord.folder == current_folder,
                )
            )
            record = result.first()
            if record is None:
                return False
            for key, value in updates.items():
                setattr(record, key, value)
            session.add(record)
            await session.commit()
        return True

    async def delete_email(self, uid: int, folder: str = "INBOX") -> bool:
        """Delete a single email (composite key).  Returns ``True`` if removed."""
        async with self._session() as session:
            result = await session.exec(
                select(EmailRecord).where(
                    EmailRecord.uid == uid,
                    EmailRecord.folder == folder,
                )
            )
            record = result.first()
            if record is None:
                return False
            await session.delete(record)
            await session.commit()
        return True

    async def delete_all_emails(self) -> int:
        """Delete all emails.  Returns the number of rows removed."""
        async with self._session() as session:
            result = await session.exec(select(EmailRecord))
            records = list(result.all())
            count = len(records)
            for record in records:
                await session.delete(record)
            await session.commit()
        return count

    async def reset_cache_fields(self) -> int:
        """Reset cached-file references in all EmailRecords.

        Clears ``html_local_path`` and sets ``content_fetched = False`` so
        the next detail-view triggers a lazy re-fetch from IMAP.
        ``has_attachments`` is intentionally preserved because it reflects
        the IMAP MIME structure (golden truth), not the local cache state.
        After a cache clear, attachment rows are deleted by
        :meth:`delete_all_attachments`.  Returns the number of records updated.
        """
        async with self._session() as session:
            result = await session.exec(select(EmailRecord))
            records = list(result.all())
            for record in records:
                record.html_local_path = ""
                record.content_fetched = False
                session.add(record)
            # Also reset all attachment is_downloaded flags
            att_result = await session.exec(select(AttachmentRecord))
            for att in att_result.all():
                att.is_downloaded = False
                att.local_path = ""
                session.add(att)
            await session.commit()
        return len(records)

    async def mark_content_fetched(
        self,
        uid: int,
        html_local_path: str,
        body_text: str = "",
        folder: str = "INBOX",
    ) -> bool:
        """Mark an email's content as fetched, store the HTML path and body text.

        Called by the service layer after a successful on-demand IMAP fetch.
        Uses the composite key ``(uid, folder)``.
        *body_text* is optional; when provided it is persisted so the record
        can serve text snippets without further I/O.
        Returns *True* if the record was found and updated.
        """
        async with self._session() as session:
            result = await session.exec(
                select(EmailRecord).where(
                    EmailRecord.uid == uid,
                    EmailRecord.folder == folder,
                )
            )
            record = result.first()
            if record is None:
                return False
            record.html_local_path = html_local_path
            record.content_fetched = True
            if body_text:
                record.body_text = body_text
            session.add(record)
            await session.commit()
        return True

    # ------------------------------------------------------------------
    # Attachment CRUD
    # ------------------------------------------------------------------

    async def get_attachment(self, att_id: int) -> AttachmentRecord | None:
        """Fetch a single attachment row by its surrogate primary key."""
        async with self._session() as session:
            return await session.get(AttachmentRecord, att_id)

    async def mark_attachment_downloaded(
        self, att_id: int, local_path: str, file_size: int
    ) -> AttachmentRecord | None:
        """Mark attachment as downloaded and store its local path and size."""
        async with self._session() as session:
            att = await session.get(AttachmentRecord, att_id)
            if att is None:
                return None
            att.local_path = local_path
            att.file_size = file_size
            att.is_downloaded = True
            session.add(att)
            await session.commit()
            await session.refresh(att)
            return att

    async def upsert_attachment(self, att: AttachmentRecord) -> AttachmentRecord:
        """Insert or update an attachment (dedup by uid + folder + filename).

        If an attachment with the same ``email_uid``, ``email_folder``, and
        ``filename`` already exists, the existing row is updated.  This prevents
        duplicate attachment records on repeated syncs.
        """
        async with self._session() as session:
            statement = select(AttachmentRecord).where(
                AttachmentRecord.email_uid == att.email_uid,
                AttachmentRecord.email_folder == att.email_folder,
                AttachmentRecord.filename == att.filename,
            )
            result = await session.exec(statement)
            existing = result.first()

            if existing is not None:
                # Update mutable fields
                existing.content_type = att.content_type
                existing.local_path = att.local_path
                existing.file_size = att.file_size
                existing.download_time = att.download_time
                existing.content_id = att.content_id
                session.add(existing)
                await session.commit()
                await session.refresh(existing)
                return existing
            else:
                session.add(att)
                await session.commit()
                await session.refresh(att)
                return att

    async def get_attachments(
        self, email_uid: int, email_folder: str = "INBOX"
    ) -> list[AttachmentRecord]:
        """Return all attachments for a given ``(email_uid, email_folder)``."""
        async with self._session() as session:
            result = await session.exec(
                select(AttachmentRecord).where(
                    AttachmentRecord.email_uid == email_uid,
                    AttachmentRecord.email_folder == email_folder,
                )
            )
            return list(result.all())

    async def delete_attachments_for_email(self, email_uid: int) -> int:
        """Delete all attachments for a given email UID."""
        async with self._session() as session:
            result = await session.exec(
                select(AttachmentRecord).where(AttachmentRecord.email_uid == email_uid)
            )
            records = list(result.all())
            count = len(records)
            for record in records:
                await session.delete(record)
            await session.commit()
        return count

    async def delete_all_attachments(self) -> int:
        """Delete all attachment records."""
        async with self._session() as session:
            result = await session.exec(select(AttachmentRecord))
            records = list(result.all())
            count = len(records)
            for record in records:
                await session.delete(record)
            await session.commit()
        return count

    # ------------------------------------------------------------------
    # Settings (key-value in email_settings table)
    # ------------------------------------------------------------------

    async def get_setting(self, key: str, default: str = "") -> str:
        """Read a setting value, returning *default* if absent."""
        async with self._session() as session:
            record = await session.get(EmailSettingsRecord, key)
            return record.value if record is not None else default

    async def set_setting(self, key: str, value: str) -> None:
        """Write a setting value (upsert)."""
        async with self._session() as session:
            record = await session.get(EmailSettingsRecord, key)
            if record is not None:
                record.value = value
                session.add(record)
            else:
                session.add(EmailSettingsRecord(key=key, value=value))
            await session.commit()

    async def get_fetch_days(self) -> int:
        """Return the configured fetch-days window."""
        raw = await self.get_setting(_KEY_FETCH_DAYS, str(DEFAULT_FETCH_DAYS))
        try:
            return int(raw)
        except ValueError:
            return DEFAULT_FETCH_DAYS

    async def set_fetch_days(self, days: int) -> None:
        """Persist the fetch-days window."""
        await self.set_setting(_KEY_FETCH_DAYS, str(days))

    async def get_auto_sync(self) -> bool:
        """Return whether auto-sync is enabled (default ``True``)."""
        raw = await self.get_setting(_KEY_AUTO_SYNC, "true")
        return raw.lower() == "true"

    async def set_auto_sync(self, enabled: bool) -> None:
        """Persist the auto-sync flag."""
        await self.set_setting(_KEY_AUTO_SYNC, str(enabled).lower())


__all__ = ["EmailStore"]
