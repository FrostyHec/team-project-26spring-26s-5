"""SQLite-backed persistence for campus news push settings, log, and prepared reports.

Tables:
    ``news_push_settings``  - single KV row storing serialised NewsPushSettings.
    ``news_push_log``       - one row per target_date; tracks email delivery status.
    ``news_push_prepared``  - one row per target_date; caches the pre-generated report
                              so the scheduled send can be instant.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from agent_core.logging_utils import get_logger
from agent_core.models.news import NewsReportResponse
from agent_core.models.news_push import (
    NewsPushLogEntry,
    NewsPushSettings,
    NewsPushStatus,
)

logger = get_logger("persistence.news_push")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS news_push_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS news_push_log (
    target_date TEXT PRIMARY KEY,
    status      TEXT NOT NULL,
    sent_at     TEXT NOT NULL,
    error       TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS news_push_prepared (
    target_date  TEXT PRIMARY KEY,
    report_json  TEXT NOT NULL,
    prepared_at  TEXT NOT NULL
);
"""

_SETTINGS_KEY = "news_push_settings_v1"


class NewsPushStore:
    """Async SQLite store for campus news email push state.

    Attributes:
        db_path: Path to the shared SQLite file (``sessions.db`` by default).
    """

    def __init__(self, db_path: str = "sessions.db") -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Open the database and create tables if they do not exist."""
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_SCHEMA_SQL)
        await self._db.commit()
        logger.info("News push store initialized at %s", self.db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        """Active database connection (raises if not initialised)."""
        if self._db is None:
            raise RuntimeError(
                "NewsPushStore not initialized - call initialize() first"
            )
        return self._db

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    async def get_settings(self) -> NewsPushSettings:
        """Return stored NewsPushSettings, or defaults if absent or corrupt."""
        async with self.db.execute(
            "SELECT value FROM news_push_settings WHERE key = ?", (_SETTINGS_KEY,)
        ) as cursor:
            row = await cursor.fetchone()
        if not row or not row["value"]:
            return NewsPushSettings()
        try:
            return NewsPushSettings.model_validate_json(row["value"])
        except Exception:
            logger.warning("Corrupt news_push_settings row - returning default.")
            return NewsPushSettings()

    async def save_settings(self, settings: NewsPushSettings) -> None:
        """Persist NewsPushSettings (upsert)."""
        await self.db.execute(
            "INSERT INTO news_push_settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (_SETTINGS_KEY, settings.model_dump_json()),
        )
        await self.db.commit()

    # ------------------------------------------------------------------
    # Delivery log (email, per target date)
    # ------------------------------------------------------------------

    async def was_sent(self, target_date: str) -> bool:
        """Return True only when this target date has a SUCCESS log row."""
        async with self.db.execute(
            "SELECT 1 FROM news_push_log WHERE target_date = ? AND status = ?",
            (target_date, NewsPushStatus.SUCCESS.value),
        ) as cursor:
            return await cursor.fetchone() is not None

    async def try_claim_send(self, target_date: str) -> bool:
        """Atomically reserve email delivery for ``target_date``.

        Succeeds when no row exists, or when the existing row's status is FAILED
        (i.e., a previous attempt that we want to retry). Returns False when a
        successful send (or another in-flight claim) is already recorded.
        """
        sent_at = datetime.now(UTC).isoformat()
        async with self.db.execute(
            "INSERT INTO news_push_log"
            " (target_date, status, sent_at, error)"
            " VALUES (?, ?, ?, '')"
            " ON CONFLICT(target_date) DO UPDATE SET"
            " status = excluded.status,"
            " sent_at = excluded.sent_at,"
            " error = excluded.error"
            " WHERE news_push_log.status = ?",
            (
                target_date,
                NewsPushStatus.IN_PROGRESS.value,
                sent_at,
                NewsPushStatus.FAILED.value,
            ),
        ) as cursor:
            claimed = cursor.rowcount > 0
        await self.db.commit()
        return claimed

    async def record_send(
        self,
        target_date: str,
        status: NewsPushStatus,
        error: str = "",
    ) -> None:
        """Record the latest email delivery result for the target date.

        A previously-SUCCESS row cannot be downgraded by a later FAILED record.
        """
        sent_at = datetime.now(UTC).isoformat()
        await self.db.execute(
            "INSERT INTO news_push_log"
            " (target_date, status, sent_at, error)"
            " VALUES (?, ?, ?, ?)"
            " ON CONFLICT(target_date) DO UPDATE SET"
            " status = excluded.status,"
            " sent_at = excluded.sent_at,"
            " error = excluded.error"
            " WHERE news_push_log.status != ? OR excluded.status = ?",
            (
                target_date,
                status.value,
                sent_at,
                error,
                NewsPushStatus.SUCCESS.value,
                NewsPushStatus.SUCCESS.value,
            ),
        )
        await self.db.commit()

    async def list_log(self) -> list[NewsPushLogEntry]:
        """Return all delivery log entries, oldest first."""
        async with self.db.execute(
            "SELECT target_date, status, sent_at, error"
            " FROM news_push_log ORDER BY sent_at ASC"
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            NewsPushLogEntry(
                target_date=row["target_date"],
                status=NewsPushStatus(row["status"]),
                sent_at=row["sent_at"],
                error=row["error"],
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Prepared (pre-generated) reports
    # ------------------------------------------------------------------

    async def get_prepared_report(self, target_date: str) -> NewsReportResponse | None:
        """Return today's pre-generated report if it exists, else None."""
        async with self.db.execute(
            "SELECT report_json FROM news_push_prepared WHERE target_date = ?",
            (target_date,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None or not row["report_json"]:
            return None
        try:
            return NewsReportResponse.model_validate_json(row["report_json"])
        except Exception:
            logger.warning("Corrupt prepared report row for %s; ignoring.", target_date)
            return None

    async def save_prepared_report(
        self, target_date: str, report: NewsReportResponse
    ) -> None:
        """Persist a generated report keyed by target date (upsert)."""
        prepared_at = datetime.now(UTC).isoformat()
        await self.db.execute(
            "INSERT INTO news_push_prepared (target_date, report_json, prepared_at)"
            " VALUES (?, ?, ?)"
            " ON CONFLICT(target_date) DO UPDATE SET"
            " report_json = excluded.report_json,"
            " prepared_at = excluded.prepared_at",
            (target_date, report.model_dump_json(), prepared_at),
        )
        await self.db.commit()
