"""Alarm (deadline reminder) data models.

Defines enums and Pydantic models for the deadline alarm feature.
All settings are global (no per-task overrides).

Architecture note:
  ``AlarmSettings`` is a plain Pydantic ``BaseModel`` (not SQLModel table).
  Persistence is handled by ``AlarmStore`` using a KV table in sessions.db.
"""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum

from pydantic import BaseModel, model_validator

from agent_core.models.deadline import DateType, DeadlinePriority

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AlarmLeadTime(StrEnum):
    """How far before the due date to send a reminder.

    Hour-based values are only effective for tasks with hour:minute precision
    (``DateType.MOMENT_HM`` / ``DateType.PERIOD_HM``).
    Day/week-based values are effective for all task types.
    """

    HOUR_1 = "hour_1"
    HOUR_3 = "hour_3"
    HOUR_6 = "hour_6"
    HOUR_12 = "hour_12"
    DAY_1 = "day_1"
    DAY_3 = "day_3"
    WEEK_1 = "week_1"


class AlarmChannel(StrEnum):
    """Notification delivery channel."""

    IN_APP = "in_app"
    EMAIL = "email"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Timedelta corresponding to each lead time value.
LEAD_TIME_DELTAS: dict[AlarmLeadTime, timedelta] = {
    AlarmLeadTime.HOUR_1: timedelta(hours=1),
    AlarmLeadTime.HOUR_3: timedelta(hours=3),
    AlarmLeadTime.HOUR_6: timedelta(hours=6),
    AlarmLeadTime.HOUR_12: timedelta(hours=12),
    AlarmLeadTime.DAY_1: timedelta(days=1),
    AlarmLeadTime.DAY_3: timedelta(days=3),
    AlarmLeadTime.WEEK_1: timedelta(weeks=1),
}

#: Lead times that only apply to hour:minute-precision tasks.
HOUR_BASED_LEAD_TIMES: frozenset[AlarmLeadTime] = frozenset(
    {
        AlarmLeadTime.HOUR_1,
        AlarmLeadTime.HOUR_3,
        AlarmLeadTime.HOUR_6,
        AlarmLeadTime.HOUR_12,
    }
)

#: DateType values that carry hour:minute precision.
HM_DATE_TYPES: frozenset[DateType] = frozenset({DateType.MOMENT_HM, DateType.PERIOD_HM})


# ---------------------------------------------------------------------------
# Settings model
# ---------------------------------------------------------------------------


class AlarmSettings(BaseModel):
    """Global deadline alarm configuration.

    When ``enabled`` is ``True``, all three selection lists must be
    non-empty (enforced by ``model_validator``).

    Attributes:
        enabled: Master switch — when False, no reminders are sent.
        lead_times: Which advance-notice windows to use (multi-select).
        channels: Notification delivery channels (multi-select).
        enabled_priorities: Which priority levels trigger reminders (multi-select).
    """

    enabled: bool = True
    lead_times: list[AlarmLeadTime] = [AlarmLeadTime.DAY_1]
    channels: list[AlarmChannel] = [AlarmChannel.IN_APP]
    enabled_priorities: list[DeadlinePriority] = [
        DeadlinePriority.HIGH,
        DeadlinePriority.MEDIUM,
    ]

    @model_validator(mode="after")
    def _validate_enabled_requires_selections(self) -> AlarmSettings:
        """Enforce at least one selection in each list when enabled."""
        if self.enabled:
            if not self.lead_times:
                raise ValueError(
                    "At least one lead_time is required when alarm is enabled."
                )
            if not self.channels:
                raise ValueError(
                    "At least one channel is required when alarm is enabled."
                )
            if not self.enabled_priorities:
                raise ValueError(
                    "At least one priority is required when alarm is enabled."
                )
        return self


# ---------------------------------------------------------------------------
# Pending notification model (returned by the API)
# ---------------------------------------------------------------------------


class PendingNotification(BaseModel):
    """A single in-app notification that has not yet been acknowledged.

    Attributes:
        id: UUID string — used for acknowledgement.
        message: Localised summary (e.g. "You have 3 upcoming deadline(s)").
        details: List of task-level detail strings.
        created_at: ISO-8601 timestamp when the notification was created.
    """

    id: str
    message: str
    details: list[str] = []
    created_at: str
