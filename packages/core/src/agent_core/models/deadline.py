"""Deadline data models — structured types for academic deadline management.

Provides enums and SQLModel/Pydantic models used by the deadline tools,
persistence layer (SQLModel table), and API routes.

Architecture note:
  ``DeadlineRecord`` is the single canonical model shared by all layers.
  It serves as the SQLModel ORM table *and* the Pydantic response schema.
  Date/time fields use ``datetime.datetime`` — the ``date_type`` column
  acts as a Type Discriminator that tells the presentation layer whether
  to interpret the value at day precision or hour:minute precision.
  Format validation is fully delegated to Pydantic — no regex needed.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

import sqlalchemy as sa
from pydantic import field_validator
from sqlalchemy import String, event
from sqlmodel import Field, SQLModel

# ---------------------------------------------------------------------------
# Custom SQLAlchemy type for lenient datetime storage
# ---------------------------------------------------------------------------


class LenientDateTime(sa.TypeDecorator[datetime | None]):
    """SQLAlchemy type that tolerates legacy non-ISO strings in SQLite.

    SQLite stores ``DATETIME`` as plain ``TEXT``.  Older data may contain
    empty strings ``''``, localised placeholders (e.g. ``'TBD'``), or
    other non-ISO values.  The default ``DateTime`` type processor calls
    ``datetime.fromisoformat()`` which raises ``ValueError`` on anything
    that is not a valid ISO-8601 string.

    This decorator:

    - **bind** (Python → DB): stores ``datetime`` as ISO-8601 text, or
      ``NULL`` for ``None``.
    - **result** (DB → Python): parses valid ISO-8601 strings to
      ``datetime``; returns ``None`` for ``NULL``, empty strings, or
      any unparseable text.
    """

    impl = sa.Text
    cache_ok = True

    def process_bind_param(
        self,
        value: datetime | None,
        dialect: sa.Dialect,
    ) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return datetime(value.year, value.month, value.day).isoformat()
        # Safety net: if somehow a raw string slips through, store as-is
        return str(value) if value else None  # type: ignore[unreachable]

    def process_result_value(
        self,
        value: str | None,
        dialect: sa.Dialect,
    ) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        text = str(value).strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text)
        except (ValueError, TypeError):
            return None


class DeadlinePriority(StrEnum):
    """Urgency level for a deadline item."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DeadlineSource(StrEnum):
    """Origin of a deadline entry.

    Indicates where the deadline information was collected from.
    """

    BLACKBOARD = "blackboard"
    EMAIL = "email"
    TAS = "tas"
    MANUAL = "manual"


class DateType(StrEnum):
    """Date classification for a deadline task.

    Determines how the task is displayed on the timeline:

    - NO_DATE: no explicit date, shown in backlog section
    - MOMENT_DAY: deadline is a specific date (day precision)
    - MOMENT_HM: deadline is a specific datetime (hour:minute precision)
    - PERIOD_DAY: task spans a date range (day precision)
    - PERIOD_HM: task spans a datetime range (hour:minute precision)
    """

    NO_DATE = "no_date"
    MOMENT_DAY = "moment_day"
    MOMENT_HM = "moment_hm"
    PERIOD_DAY = "period_day"
    PERIOD_HM = "period_hm"


class DeadlineRecord(SQLModel, table=True):
    """A single academic deadline persisted in the store.

    Used as both the SQLModel ORM table and the Pydantic schema for API
    responses.  Date/time fields are ``datetime`` objects — the
    ``date_type`` discriminator determines interpretation:

    - ``MOMENT_DAY`` / ``PERIOD_DAY``: day precision (time part is 00:00)
    - ``MOMENT_HM`` / ``PERIOD_HM``: hour:minute precision
    - ``NO_DATE``: ``None``

    Format validation is handled automatically by Pydantic; the Store
    layer receives only well-typed values.

    Attributes:
        id: Unique identifier (UUID), primary key.
        title: Short description of the deadline item.
        course: Course code or name (e.g. "CS302").
        due_date: End date/datetime (``None`` when ``date_type`` is NO_DATE).
        priority: Urgency level.
        source: Where this deadline was collected from.
        description: Optional longer description or notes.
        date_type: How the task date should be interpreted.
        start_date: Period start date (PERIOD_DAY/PERIOD_HM only; else None).
        completed: Whether the task has been marked as done.
    """

    __tablename__ = "deadlines"  # type: ignore[assignment]

    id: str = Field(default="", primary_key=True)
    title: str
    course: str = Field(default="")
    due_date: datetime | None = Field(default=None, sa_type=LenientDateTime())
    priority: DeadlinePriority = Field(
        default=DeadlinePriority.MEDIUM, sa_type=String()
    )
    source: DeadlineSource = Field(default=DeadlineSource.MANUAL, sa_type=String())
    description: str = Field(default="")
    date_type: DateType = Field(default=DateType.MOMENT_DAY, sa_type=String())
    start_date: datetime | None = Field(default=None, sa_type=LenientDateTime())
    completed: bool = Field(default=False)


def _coerce_deadline_enums(target: DeadlineRecord, _context: object) -> None:
    """Coerce raw DB strings back to StrEnum members after ORM load or refresh.

    SQLAlchemy maps ``sa_type=String()`` columns as plain ``str`` values.
    This listener runs immediately after each row is materialised (``load``
    event) or after ``session.refresh()`` (``refresh`` event) and converts
    those strings to the correct ``StrEnum`` types so the rest of the
    codebase always sees typed enum members.
    """
    if isinstance(target.priority, str):
        target.priority = DeadlinePriority(target.priority)
    if isinstance(target.source, str):
        target.source = DeadlineSource(target.source)
    if isinstance(target.date_type, str):
        target.date_type = DateType(target.date_type)


event.listen(DeadlineRecord, "load", _coerce_deadline_enums)
event.listen(
    DeadlineRecord,
    "refresh",
    lambda t, ctx, attrs: _coerce_deadline_enums(t, ctx),
)


class DeadlineRecordCreate(SQLModel):
    """DTO for creating a deadline (no table, no id required).

    Used internally by the service layer to construct new records before
    assigning an ID and persisting them. Also used in API batch import.

    Empty strings for date fields are coerced to None to handle frontend
    scenarios where unset dates are transmitted as "".
    """

    title: str
    course: str = ""
    due_date: datetime | None = None
    priority: DeadlinePriority = DeadlinePriority.MEDIUM
    source: DeadlineSource = DeadlineSource.MANUAL
    description: str = ""
    date_type: DateType = DateType.MOMENT_DAY
    start_date: datetime | None = None
    completed: bool = False

    @field_validator("due_date", "start_date", mode="before")
    @classmethod
    def coerce_empty_string_to_none(cls, v: object) -> object:
        """Convert empty string to None for datetime fields.

        This allows frontend to send "" for unset dates without triggering
        a validation error. Valid ISO-8601 strings are parsed normally.
        """
        if v == "":
            return None
        return v


def parse_datetime_field(
    value: str | date | datetime | None,
) -> datetime | None:
    """Parse a value to ``datetime | None``.

    Accepts:
    - ``None`` or empty string → ``None``
    - ISO-8601 date string ``"YYYY-MM-DD"`` → ``datetime`` (midnight)
    - ISO-8601 datetime string ``"YYYY-MM-DDTHH:MM"`` → ``datetime``
    - ``datetime`` object → pass-through
    - ``date`` object → ``datetime`` at midnight

    Returns:
        Parsed ``datetime`` or ``None`` if the value is absent/invalid.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    text = str(value).strip()
    if not text:
        return None
    # Try full datetime first (YYYY-MM-DDTHH:MM[:SS])
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    # Try date-only (YYYY-MM-DD) → midnight
    try:
        d = date.fromisoformat(text[:10])
        return datetime(d.year, d.month, d.day)
    except ValueError:
        return None


def parse_date_field(
    value: str | date | datetime | None,
) -> date | None:
    """Parse a value to ``date | None`` (day precision only).

    Thin wrapper around :func:`parse_datetime_field` that discards the
    time component.  Kept for backward compatibility where only day
    precision is needed.
    """
    dt = parse_datetime_field(value)
    return dt.date() if dt is not None else None
