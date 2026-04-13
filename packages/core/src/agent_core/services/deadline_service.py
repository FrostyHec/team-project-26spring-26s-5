"""Deadline management service — single source of truth for deadline business logic.

Encapsulates business-rule validation, datetime sanitisation, record construction,
and CRUD orchestration.  Both the REST API controller and the LLM tool
functions delegate to this service so that business rules are defined
in exactly one place.

Architecture note (validation layers):
  - Controller/DTO: format validation (Pydantic ``datetime`` type, enum types)
  - Service (this file): semantic/business validation (range checks, logic)
  - Store: pure executor — receives well-typed objects, never validates format
"""

import uuid
from datetime import datetime
from typing import Any

from agent_core.logging_utils import get_logger
from agent_core.models.deadline import (
    DateType,
    DeadlinePriority,
    DeadlineRecord,
    DeadlineSource,
    parse_datetime_field,
)
from agent_core.persistence.deadline_store import DeadlineStore

logger = get_logger("services.deadline")

# ---------------------------------------------------------------------------
# Constants (single source — no longer duplicated across modules)
# ---------------------------------------------------------------------------

VALID_DATE_TYPES = ", ".join(dt.value for dt in DateType)
VALID_PRIORITIES = ", ".join(p.value for p in DeadlinePriority)


# ---------------------------------------------------------------------------
# Pure helpers (stateless — can be imported/tested independently)
# ---------------------------------------------------------------------------


def sanitise_date_fields(
    due_date: datetime | None,
    start_date: datetime | None,
    date_type: DateType,
) -> tuple[datetime | None, datetime | None, DateType, list[str]]:
    """Sanitise already-parsed datetime values and enforce business rules.

    This helper is called by the Service layer after Pydantic / the tool
    layer has already parsed raw strings into ``datetime`` objects (or
    ``None``).  It applies business-level corrections only:

    - Downgrade ``date_type`` to ``NO_DATE`` when ``due_date`` is absent
    - Clear ``start_date`` when it is after ``due_date``

    Args:
        due_date: Parsed end datetime, or ``None`` for tasks with no date.
        start_date: Parsed start datetime, or ``None``.
        date_type: The date classification to use/validate.

    Returns:
        ``(due_date, start_date, date_type, warnings)`` where *warnings*
        collects human-readable messages about corrections applied.
    """
    warnings: list[str] = []

    # Downgrade date_type when due_date is absent
    if due_date is None and date_type != DateType.NO_DATE:
        warnings.append("due_date is empty — date_type automatically set to 'no_date'.")
        date_type = DateType.NO_DATE

    # Date range: start must not be after due
    if start_date is not None and due_date is not None and start_date > due_date:
        warnings.append(
            f"start_date '{start_date}' is after due_date '{due_date}'. "
            "start_date must be on or before due_date. "
            "Cleared start_date to None."
        )
        start_date = None

    return due_date, start_date, date_type, warnings


def build_record_from_dict(
    data: dict[str, Any],
    *,
    source: DeadlineSource = DeadlineSource.MANUAL,
) -> tuple[DeadlineRecord, list[str]]:
    """Construct a sanitised :class:`DeadlineRecord` from a loose dict.

    This path is used by the LLM tool layer (``save_deadlines`` batch and
    ``add_deadline``), where inputs arrive as untyped dicts from JSON.
    Enum values are parsed with safe fallback defaults; date strings are
    converted to ``datetime | None`` objects via :func:`parse_datetime_field`.

    Args:
        data: Loose dictionary of deadline fields.
        source: Default source when the dict does not specify one.

    Returns:
        ``(record, warnings)`` where *warnings* lists human-readable
        corrections applied (e.g. invalid dates cleared).
    """
    title = str(data.get("title", "")).strip() or "Untitled"
    course = str(data.get("course", "")).strip()
    description = str(data.get("description", "")).strip()

    # -- enum parsing with safe fallbacks --
    _default_pri = DeadlinePriority.MEDIUM.value
    raw_priority = str(data.get("priority", _default_pri)).strip().lower()
    try:
        priority = DeadlinePriority(raw_priority)
    except ValueError:
        priority = DeadlinePriority.MEDIUM

    raw_dt = str(data.get("date_type", DateType.MOMENT_DAY.value)).strip().lower()
    try:
        date_type = DateType(raw_dt)
    except ValueError:
        date_type = DateType.MOMENT_DAY

    raw_source = str(data.get("source", source.value)).strip().lower()
    try:
        src = DeadlineSource(raw_source)
    except ValueError:
        src = source

    # -- date parsing (string → date | None) --
    warnings: list[str] = []
    raw_due = data.get("due_date", "")
    raw_start = data.get("start_date", "")

    due_date = parse_datetime_field(raw_due)
    start_date = parse_datetime_field(raw_start)

    # Emit warnings for non-empty values that failed to parse
    if raw_due and not due_date:
        warnings.append(
            f"due_date '{raw_due}' is not a valid ISO-8601 string "
            "(expected YYYY-MM-DD or YYYY-MM-DDTHH:MM). "
            "Set to None and date_type changed to 'no_date'. "
            "If the date is unknown, use date_type='no_date' with due_date=''."
        )
    if raw_start and not start_date:
        warnings.append(
            f"start_date '{raw_start}' is not a valid ISO-8601 string. Set to None."
        )

    # -- business-level sanitisation (range, downgrade) --
    due_date, start_date, date_type, extra_warnings = sanitise_date_fields(
        due_date, start_date, date_type
    )
    warnings.extend(extra_warnings)

    record = DeadlineRecord(
        id=str(uuid.uuid4()),
        title=title,
        course=course,
        due_date=due_date,
        priority=priority,
        source=src,
        description=description,
        date_type=date_type,
        start_date=start_date,
    )
    return record, warnings


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DeadlineNotFoundError(Exception):
    """Raised when a deadline ID does not exist in the store."""

    def __init__(self, deadline_id: str) -> None:
        self.deadline_id = deadline_id
        super().__init__(f"Deadline '{deadline_id}' not found.")


class DeadlineValidationError(Exception):
    """Raised when a request payload fails business-rule validation."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class DeadlineService:
    """Stateless service encapsulating all deadline business logic.

    Each method receives its parameters explicitly — no hidden globals.
    The caller (API route or tool function) is responsible for:
    * HTTP status codes / JSON serialisation
    * Tool-specific formatting (e.g. ``json.dumps`` for LLM responses)

    Raises:
        DeadlineNotFoundError: When a referenced deadline ID does not exist.
        DeadlineValidationError: When a field value violates a business rule.
    """

    def __init__(self, store: DeadlineStore) -> None:
        self._store = store

    # ----- Create -----

    async def create_from_dict(
        self,
        data: dict[str, Any],
        *,
        source: DeadlineSource = DeadlineSource.MANUAL,
    ) -> tuple[DeadlineRecord, list[str]]:
        """Create a deadline from a loose dict (used by tools).

        Enum values are parsed with safe fallbacks; invalid dates are
        sanitised.

        Returns:
            ``(saved_record, warnings)``
        """
        record, warnings = build_record_from_dict(data, source=source)
        for w in warnings:
            logger.warning("create_from_dict: %s", w)
        saved = await self._store.add(record)
        return saved, warnings

    async def create(
        self,
        *,
        title: str,
        course: str = "",
        due_date: datetime | None = None,
        priority: DeadlinePriority = DeadlinePriority.MEDIUM,
        description: str = "",
        date_type: DateType = DateType.MOMENT_DAY,
        start_date: datetime | None = None,
        source: DeadlineSource = DeadlineSource.MANUAL,
    ) -> tuple[DeadlineRecord, list[str]]:
        """Create a deadline with typed parameters (used by API).

        The Controller layer (Pydantic) already validated format.
        This method applies only business-rule validation (date range).

        Args:
            title: Short description of the deadline.
            course: Course code or name.
            due_date: End datetime (``None`` for NO_DATE tasks).
            priority: Urgency level.
            description: Optional longer notes.
            date_type: Date classification.
            start_date: Period start datetime (for PERIOD types).
            source: Origin of the deadline.

        Returns:
            ``(saved_record, warnings)``

        Raises:
            DeadlineValidationError: If date range is invalid.
        """
        _validate_date_range(start_date, due_date)
        due_date, start_date, date_type, warnings = sanitise_date_fields(
            due_date, start_date, date_type
        )

        record = DeadlineRecord(
            id=str(uuid.uuid4()),
            title=title,
            course=course,
            due_date=due_date,
            priority=priority,
            source=source,
            description=description,
            date_type=date_type,
            start_date=start_date,
        )
        saved = await self._store.add(record)
        return saved, warnings

    # ----- Read -----

    async def list_deadlines(
        self,
        *,
        course: str | None = None,
        priority: DeadlinePriority | None = None,
    ) -> list[DeadlineRecord]:
        """List deadlines, optionally filtered by course or priority."""
        return await self._store.list_all(course=course, priority=priority)

    async def get(self, deadline_id: str) -> DeadlineRecord:
        """Fetch a single deadline or raise :class:`DeadlineNotFoundError`."""
        record = await self._store.get(deadline_id)
        if record is None:
            raise DeadlineNotFoundError(deadline_id)
        return record

    # ----- Update -----

    async def update(
        self,
        deadline_id: str,
        update_fields: dict[str, object],
    ) -> tuple[DeadlineRecord, list[str]]:
        """Apply a partial update to an existing deadline.

        *update_fields* maps field names to strongly-typed values
        (e.g. ``date`` for date fields, enum instances for enum fields).
        Empty dict returns the current record unchanged.

        Returns:
            ``(updated_record, warnings)``

        Raises:
            DeadlineNotFoundError: If the deadline does not exist.
            DeadlineValidationError: If date range is violated.
        """
        existing = await self._store.get(deadline_id)
        if existing is None:
            raise DeadlineNotFoundError(deadline_id)

        if not update_fields:
            return existing, []

        # Business-rule: validate effective date range
        effective_start: datetime | None = update_fields.get(  # type: ignore[assignment]
            "start_date", existing.start_date
        )
        effective_due: datetime | None = update_fields.get(  # type: ignore[assignment]
            "due_date", existing.due_date
        )
        _validate_date_range(effective_start, effective_due)

        updated = await self._store.update(deadline_id, update_fields)
        if updated is None:  # pragma: no cover — should not happen
            raise DeadlineNotFoundError(deadline_id)
        return updated, []

    async def update_from_tool(
        self,
        deadline_id: str,
        *,
        title: str = "",
        course: str = "",
        due_date: str = "",
        priority: str = "",
        description: str = "",
        date_type: str = "",
        start_date: str = "",
    ) -> tuple[DeadlineRecord, list[str]]:
        """Update a deadline from LLM tool parameters (string inputs).

        Empty-string parameters are treated as "no change".  Invalid
        enum values raise :class:`DeadlineValidationError`; invalid date
        strings are sanitised with warnings (not rejected).

        Returns:
            ``(updated_record, warnings)``

        Raises:
            DeadlineNotFoundError: If the deadline does not exist.
            DeadlineValidationError: For invalid enum values.
        """
        existing = await self._store.get(deadline_id)
        if existing is None:
            raise DeadlineNotFoundError(deadline_id)

        fields: dict[str, object] = {}
        all_warnings: list[str] = []

        if title:
            fields["title"] = title
        if course:
            fields["course"] = course
        if description:
            fields["description"] = description

        if priority:
            try:
                fields["priority"] = DeadlinePriority(priority)
            except ValueError:
                raise DeadlineValidationError(
                    f"Invalid priority '{priority}'. Use: {VALID_PRIORITIES}."
                ) from None

        if date_type:
            try:
                fields["date_type"] = DateType(date_type)
            except ValueError:
                raise DeadlineValidationError(
                    f"Invalid date_type '{date_type}'. Use: {VALID_DATE_TYPES}."
                ) from None

        # Parse and sanitise date strings
        if due_date or start_date:
            parsed_due = (
                parse_datetime_field(due_date) if due_date else existing.due_date
            )
            parsed_start = (
                parse_datetime_field(start_date) if start_date else existing.start_date
            )

            if due_date and not parsed_due:
                all_warnings.append(
                    f"due_date '{due_date}' is not a valid ISO-8601 string. "
                    "Left unchanged."
                )
            if start_date and not parsed_start:
                all_warnings.append(
                    f"start_date '{start_date}' is not a valid ISO-8601 string. "
                    "Left unchanged."
                )

            eff_dt = DateType(
                fields.get("date_type", existing.date_type)  # type: ignore[arg-type]
            )
            validated_due, validated_start, eff_dt, range_warnings = (
                sanitise_date_fields(
                    parsed_due if due_date else existing.due_date,
                    parsed_start if start_date else existing.start_date,
                    eff_dt,
                )
            )
            for w in range_warnings:
                logger.warning("update_from_tool: %s", w)
            all_warnings.extend(range_warnings)

            if due_date and parsed_due:
                fields["due_date"] = validated_due
            if start_date and parsed_start:
                fields["start_date"] = validated_start
            if range_warnings:
                fields["date_type"] = eff_dt

        if not fields:
            return existing, all_warnings

        updated = await self._store.update(deadline_id, fields)
        if updated is None:  # pragma: no cover
            raise DeadlineNotFoundError(deadline_id)
        return updated, all_warnings

    # ----- Delete -----

    async def delete(self, deadline_id: str) -> bool:
        """Delete a deadline. Returns *True* if a record was removed.

        Raises:
            DeadlineNotFoundError: If the deadline does not exist.
        """
        deleted = await self._store.delete(deadline_id)
        if not deleted:
            raise DeadlineNotFoundError(deadline_id)
        return True

    # ----- Toggle completed -----

    async def toggle_completed(
        self,
        deadline_id: str,
        completed: bool,
    ) -> DeadlineRecord:
        """Set the completed flag on a deadline.

        Raises:
            DeadlineNotFoundError: If the deadline does not exist.
        """
        updated = await self._store.toggle_completed(deadline_id, completed)
        if updated is None:
            raise DeadlineNotFoundError(deadline_id)
        return updated

    # ----- Sync (preview + commit) -----

    async def sync_preview(
        self,
        candidates: list[DeadlineRecord],
    ) -> tuple[list[DeadlineRecord], list[dict[str, Any]]]:
        """Preview which candidates are new vs duplicates.

        Returns:
            ``(new_tasks, duplicate_entries)`` where each duplicate
            entry has ``candidate`` and ``existing_id`` keys.
        """
        new_tasks: list[DeadlineRecord] = []
        duplicates: list[dict[str, Any]] = []

        for candidate in candidates:
            existing = await self._store.find_duplicate(
                candidate.title, candidate.due_date
            )
            if existing:
                duplicates.append({"candidate": candidate, "existing_id": existing.id})
            else:
                new_tasks.append(candidate)

        return new_tasks, duplicates

    async def sync_commit(
        self,
        tasks: list[DeadlineRecord],
    ) -> list[DeadlineRecord]:
        """Persist a batch of confirmed tasks."""
        added: list[DeadlineRecord] = []
        for task in tasks:
            saved = await self._store.add(task)
            added.append(saved)
        return added

    # ----- Batch save (from tools) -----

    async def save_batch(
        self,
        items: list[dict[str, Any]],
    ) -> tuple[list[DeadlineRecord], list[str], list[str]]:
        """Save a batch of loose dicts as deadlines.

        Skips items that are not dicts.

        Returns:
            ``(saved_records, all_warnings, skipped_reasons)``
        """
        saved: list[DeadlineRecord] = []
        all_warnings: list[str] = []
        skipped: list[str] = []

        for item in items:
            if not isinstance(item, dict):
                skipped.append(f"Skipped non-dict item: {item!r}")
                continue

            record, warnings = build_record_from_dict(item)
            for w in warnings:
                logger.warning("save_batch: %s", w)
            all_warnings.extend(warnings)
            persisted = await self._store.add(record)
            saved.append(persisted)

        return saved, all_warnings, skipped


# ---------------------------------------------------------------------------
# Module-level business-rule validator
# ---------------------------------------------------------------------------


def _validate_date_range(
    start_date: datetime | None,
    due_date: datetime | None,
) -> None:
    """Raise :class:`DeadlineValidationError` if *start_date* > *due_date*."""
    if start_date is not None and due_date is not None and start_date > due_date:
        raise DeadlineValidationError(
            f"start_date '{start_date}' must be on or before due_date '{due_date}'."
        )
