"""Alarm service — core business logic for deadline reminders.

Responsibility:
  * Compute when a reminder should fire given a deadline and a lead time.
  * Poll all deadlines, compare against the current time, and dispatch
    notifications for those that are newly due for a reminder.
  * Aggregate multiple firing reminders into a single notification per channel
    (one in-app notification + one email, regardless of how many tasks fire).
  * Guard against re-sending via the alarm_log dedup table in :class:`AlarmStore`.

Architecture::

    AlarmScheduler (asyncio task)
        └→ AlarmService.check_and_dispatch(now)
               ├→ DeadlineStore.list_all()
               ├→ AlarmStore.get_settings()
               ├→ AlarmStore.is_alarm_sent()   — per (deadline_id, lead_time)
               ├→ AlarmStore.add_pending_notification()  — for IN_APP channel
               ├→ (optional) EmailService.send_email()  — for EMAIL channel
               └→ AlarmStore.mark_alarm_sent()  — per (deadline_id, lead_time)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime

from agent_core.logging_utils import get_logger
from agent_core.models.alarm import (
    HM_DATE_TYPES,
    HOUR_BASED_LEAD_TIMES,
    LEAD_TIME_DELTAS,
    AlarmChannel,
    AlarmLeadTime,
    AlarmSettings,
    PendingNotification,
)
from agent_core.models.deadline import DateType, DeadlineRecord
from agent_core.persistence.alarm_store import AlarmStore
from agent_core.persistence.deadline_store import DeadlineStore

logger = get_logger("services.alarm")

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_ALARM_EMAIL_SUBJECT = "DDL Reminder"
_MISSING_DATE_LABEL = "N/A"
_OVERDUE_MARKER = "(OVERDUE)"
_MSG_OVERDUE = "You have {n} overdue deadline(s)"
_MSG_UPCOMING = "You have {n} upcoming deadline(s)"
_MSG_MIXED = "You have {o} overdue and {u} upcoming deadline(s)"


# ---------------------------------------------------------------------------
# Pure helper
# ---------------------------------------------------------------------------


def compute_trigger_time(
    due_date: datetime | None,
    lead_time: AlarmLeadTime,
    date_type: DateType,
) -> datetime | None:
    """Return the datetime at which a reminder should fire, or ``None``.

    Returns ``None`` when:
    * ``due_date`` is ``None`` (task has no due date).
    * ``lead_time`` is hour-based *and* the task does not carry
      hour:minute precision (i.e. ``date_type`` not in ``HM_DATE_TYPES``).

    Args:
        due_date: The task's due datetime.
        lead_time: Which advance-notice window to use.
        date_type: The precision class of the task's date.

    Returns:
        Trigger datetime, or ``None`` if not applicable.
    """
    if due_date is None:
        return None
    if lead_time in HOUR_BASED_LEAD_TIMES and date_type not in HM_DATE_TYPES:
        return None
    return due_date - LEAD_TIME_DELTAS[lead_time]


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AlarmService:
    """Stateless service that drives the deadline alarm lifecycle.

    Args:
        deadline_store: Source of all deadline records.
        alarm_store: Persistence for settings, dedup log, and pending
            in-app notifications.
        send_email_fn: Optional async callback ``(subject, body) → None``
            used to send email notifications.  When ``None``, the EMAIL
            channel is skipped even if configured.
    """

    def __init__(
        self,
        deadline_store: DeadlineStore,
        alarm_store: AlarmStore,
        send_email_fn: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> None:
        self._deadlines = deadline_store
        self._alarms = alarm_store
        self._send_email = send_email_fn

    async def get_settings(self) -> AlarmSettings:
        """Return current alarm settings from the store."""
        return await self._alarms.get_settings()

    async def save_settings(self, settings: AlarmSettings) -> AlarmSettings:
        """Persist alarm settings and return the saved value."""
        await self._alarms.save_settings(settings)
        return settings

    async def get_pending_notifications(self) -> list[PendingNotification]:
        """Return all unacknowledged in-app notifications."""
        return await self._alarms.get_pending_notifications()

    async def ack_notification(self, notification_id: str) -> bool:
        """Acknowledge and remove a pending notification.

        Args:
            notification_id: UUID of the notification to dismiss.

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        return await self._alarms.ack_notification(notification_id)

    async def check_and_dispatch(self, now: datetime) -> None:
        """Scan all deadlines and dispatch any overdue reminders.

        This method is the core of the alarm loop.  It is safe to call
        multiple times — the alarm_log table prevents duplicate sends.

        Algorithm:
        1. Load settings; return immediately if ``enabled=False``.
        2. List all deadlines from the store.
        3. Filter: skip completed tasks, tasks with no due_date, tasks whose
           priority is not in ``enabled_priorities``, and tasks where
           ``created_at`` is ``None`` or ``due_date <= created_at``
           (imported-overdue heuristic).
        4. For each (deadline, lead_time) pair: compute the trigger time and
           check whether it is in the past *and* has not been sent yet.
        5. Collect all firing pairs, deduplicate by ``deadline.id`` to build
           the notification message, then dispatch one notification per channel.
        6. Mark every (deadline_id, lead_time) pair as sent in alarm_log.

        Args:
            now: The reference "current" time.  Injected so tests can freeze time.
        """
        settings = await self._alarms.get_settings()
        if not settings.enabled:
            logger.debug("Alarm disabled — skipping check_and_dispatch")
            return

        all_deadlines = await self._deadlines.list_all()

        # Filter to alarm-eligible deadlines
        eligible: list[DeadlineRecord] = []
        for ddl in all_deadlines:
            if ddl.completed:
                continue
            if ddl.due_date is None:
                continue
            if ddl.priority not in settings.enabled_priorities:
                continue
            # Skip tasks that were overdue at import time (created_at heuristic)
            if ddl.created_at is None:
                continue
            # Normalise both datetimes to UTC-aware for comparison
            due = _ensure_aware(ddl.due_date)
            created = _ensure_aware(ddl.created_at)
            if due <= created:
                continue
            eligible.append(ddl)

        # Collect all (deadline, lead_time) pairs that should fire now
        pending: list[tuple[DeadlineRecord, AlarmLeadTime]] = []
        for ddl in eligible:
            for lead_time in settings.lead_times:
                trigger = compute_trigger_time(ddl.due_date, lead_time, ddl.date_type)
                if trigger is None:
                    continue
                trigger_aware = _ensure_aware(trigger)
                if trigger_aware > now:
                    continue  # Not yet time
                already_sent = await self._alarms.is_alarm_sent(ddl.id, lead_time.value)
                if already_sent:
                    continue
                pending.append((ddl, lead_time))

        if not pending:
            logger.debug("No pending alarms at %s", now.isoformat())
            return

        # Deduplicate by deadline id for message composition
        unique_ddls: dict[str, DeadlineRecord] = {ddl.id: ddl for ddl, _ in pending}
        now_aware = _ensure_aware(now)
        overdue_ddls = [
            ddl
            for ddl in unique_ddls.values()
            if ddl.due_date and _ensure_aware(ddl.due_date) < now_aware
        ]
        upcoming_ddls = [
            ddl
            for ddl in unique_ddls.values()
            if ddl.due_date and _ensure_aware(ddl.due_date) >= now_aware
        ]
        o, u = len(overdue_ddls), len(upcoming_ddls)
        if o > 0 and u == 0:
            message = _MSG_OVERDUE.format(n=o)
        elif u > 0 and o == 0:
            message = _MSG_UPCOMING.format(n=u)
        else:
            message = _MSG_MIXED.format(o=o, u=u)
        details = _format_details(overdue_ddls, overdue=True) + _format_details(
            upcoming_ddls, overdue=False
        )

        # Dispatch per channel; track whether at least one channel succeeded
        any_dispatched = False
        for channel in settings.channels:
            if await self._dispatch(channel, message, details):
                any_dispatched = True

        # Only mark pairs as sent when at least one channel delivered.
        # If every channel failed or was skipped (e.g. EMAIL-only with no
        # send_email_fn configured), leave the pairs unmarked so the next
        # scheduler tick can retry after the issue is resolved.
        if any_dispatched:
            for ddl, lead_time in pending:
                await self._alarms.mark_alarm_sent(ddl.id, lead_time.value)

        logger.info(
            "Dispatched alarm for %d deadline(s) via %s",
            len(unique_ddls),
            [c.value for c in settings.channels],
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _dispatch(
        self, channel: AlarmChannel, message: str, details: list[str]
    ) -> bool:
        """Dispatch *message* via *channel*.

        Returns:
            ``True`` if the notification was delivered, ``False`` if it was
            skipped or failed (so the caller can decide whether to mark the
            alarm pair as sent).
        """
        if channel == AlarmChannel.IN_APP:
            await self._alarms.add_pending_notification(message, details)
            return True
        if channel == AlarmChannel.EMAIL:
            if self._send_email is not None:
                body = message + "\n\n" + "\n".join(details)
                try:
                    await self._send_email(_ALARM_EMAIL_SUBJECT, body)
                    return True
                except Exception as exc:
                    logger.warning("Failed to send alarm email: %s", exc)
                    return False
            logger.warning(
                "EMAIL channel is configured but no send_email_fn was provided;"
                " skipping email dispatch."
            )
            return False
        return False


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _ensure_aware(dt: datetime) -> datetime:
    """Return a timezone-aware copy of *dt*.

    Naive datetimes are interpreted as **local system time** (not UTC), which
    matches how deadline ``due_date`` values are stored: the frontend sends
    plain ``"YYYY-MM-DDTHH:MM:SS"`` strings without a timezone offset, and
    the DB stores them as-is.  Using ``astimezone()`` on the naive value has
    Python attach the host machine's current UTC offset, so comparisons with
    UTC-aware ``now`` values are correct.

    Args:
        dt: Any datetime, aware or naive.

    Returns:
        A timezone-aware datetime.
    """
    if dt.tzinfo is None:
        return dt.astimezone()
    return dt


def _format_details(
    deadlines: list[DeadlineRecord], *, overdue: bool = False
) -> list[str]:
    """Build human-readable detail strings for each deadline."""
    lines: list[str] = []
    for ddl in deadlines:
        due_str = (
            ddl.due_date.strftime("%Y-%m-%d %H:%M")
            if ddl.due_date
            else _MISSING_DATE_LABEL
        )
        course = f"[{ddl.course}] " if ddl.course else ""
        marker = f" {_OVERDUE_MARKER}" if overdue else ""
        lines.append(f"{course}{ddl.title} — {due_str}{marker}")
    return lines
