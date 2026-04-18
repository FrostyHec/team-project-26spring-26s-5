"""SQLite-backed persistence for alarm settings, dedup log, and pending notifications.

All three tables live in the same ``sessions.db`` database that is shared
with the profile and session stores.

Tables:
    ``alarm_settings``       — single KV row storing serialised :class:`AlarmSettings`.
    ``alarm_log``            — deduplication log; one row per (deadline_id, lead_time)
                               that has already been dispatched.
    ``pending_notifications`` — in-app notifications waiting to be acknowledged.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from agent_core.logging_utils import get_logger
from agent_core.models.alarm import AlarmSettings, PendingNotification

logger = get_logger("persistence.alarm")

# ---------------------------------------------------------------------------
# Schema SQL
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS alarm_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS alarm_log (
    deadline_id TEXT NOT NULL,
    lead_time   TEXT NOT NULL,
    sent_at     TEXT NOT NULL,
    PRIMARY KEY (deadline_id, lead_time)
);

CREATE TABLE IF NOT EXISTS pending_notifications (
    id         TEXT PRIMARY KEY,
    message    TEXT NOT NULL,
    details    TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
"""

_SETTINGS_KEY = "alarm_settings_v1"


class AlarmStore:
    """Async SQLite store for alarm settings, dedup log, and pending notifications.

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
        logger.info("Alarm store initialized at %s", self.db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        """Active database connection (raises if not initialised)."""
        if self._db is None:
            raise RuntimeError("AlarmStore not initialized — call initialize() first")
        return self._db

    # ------------------------------------------------------------------
    # Alarm settings
    # ------------------------------------------------------------------

    async def get_settings(self) -> AlarmSettings:
        """Return the stored :class:`AlarmSettings`, or the default if absent."""
        async with self.db.execute(
            "SELECT value FROM alarm_settings WHERE key = ?", (_SETTINGS_KEY,)
        ) as cursor:
            row = await cursor.fetchone()
        if not row or not row["value"]:
            return AlarmSettings()
        try:
            return AlarmSettings.model_validate_json(row["value"])
        except Exception:
            logger.warning("Corrupt alarm_settings row — returning default.")
            return AlarmSettings()

    async def save_settings(self, settings: AlarmSettings) -> None:
        """Persist :class:`AlarmSettings` (upsert)."""
        value = settings.model_dump_json()
        await self.db.execute(
            "INSERT INTO alarm_settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (_SETTINGS_KEY, value),
        )
        await self.db.commit()

    # ------------------------------------------------------------------
    # Alarm dedup log
    # ------------------------------------------------------------------

    async def is_alarm_sent(self, deadline_id: str, lead_time: str) -> bool:
        """Return ``True`` if this (deadline_id, lead_time) pair was already sent."""
        async with self.db.execute(
            "SELECT 1 FROM alarm_log WHERE deadline_id = ? AND lead_time = ?",
            (deadline_id, lead_time),
        ) as cursor:
            row = await cursor.fetchone()
        return row is not None

    async def mark_alarm_sent(self, deadline_id: str, lead_time: str) -> None:
        """Record that a reminder for (deadline_id, lead_time) was dispatched."""
        sent_at = datetime.now(UTC).isoformat()
        await self.db.execute(
            "INSERT OR IGNORE INTO alarm_log (deadline_id, lead_time, sent_at)"
            " VALUES (?, ?, ?)",
            (deadline_id, lead_time, sent_at),
        )
        await self.db.commit()

    # ------------------------------------------------------------------
    # Pending (in-app) notifications
    # ------------------------------------------------------------------

    async def add_pending_notification(self, message: str, details: list[str]) -> str:
        """Store a pending notification and return its UUID string id."""
        nid = str(uuid.uuid4())
        created_at = datetime.now(UTC).isoformat()
        details_json = json.dumps(details, ensure_ascii=False)
        await self.db.execute(
            "INSERT INTO pending_notifications (id, message, details, created_at)"
            " VALUES (?, ?, ?, ?)",
            (nid, message, details_json, created_at),
        )
        await self.db.commit()
        return nid

    async def get_pending_notifications(self) -> list[PendingNotification]:
        """Return all unacknowledged notifications, oldest first."""
        async with self.db.execute(
            "SELECT id, message, details, created_at"
            " FROM pending_notifications ORDER BY created_at ASC"
        ) as cursor:
            rows = await cursor.fetchall()
        result: list[PendingNotification] = []
        for row in rows:
            try:
                details: list[str] = json.loads(row["details"])
            except Exception:
                details = []
            result.append(
                PendingNotification(
                    id=row["id"],
                    message=row["message"],
                    details=details,
                    created_at=row["created_at"],
                )
            )
        return result

    async def ack_notification(self, notification_id: str) -> bool:
        """Delete a notification by id.

        Returns:
            ``True`` if a row was deleted, ``False`` if id was not found.
        """
        cursor = await self.db.execute(
            "DELETE FROM pending_notifications WHERE id = ?", (notification_id,)
        )
        await self.db.commit()
        return cursor.rowcount > 0
