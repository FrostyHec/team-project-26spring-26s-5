"""Deadline management tools — fetch, extract, store, and display academic deadlines.

External data sources (Blackboard, Email, TAS) are currently mocked.
All tools follow the ``register_*_tools(registry)`` convention so they
are auto-discovered by :func:`agent_core.tools.auto_discover_and_register`.

Business logic lives in :mod:`agent_core.services.deadline_service`.
This module is a thin adapter: it parses LLM string inputs into typed
values, delegates to the service, and formats results as JSON strings.
"""

import json
from typing import Any

from agent_core.logging_utils import get_logger
from agent_core.models.deadline import DateType, DeadlinePriority, DeadlineSource
from agent_core.persistence.deadline_provider import (
    get_deadline_store,
)
from agent_core.persistence.deadline_provider import (
    set_deadline_store as set_deadline_store,  # noqa: F401 — re-export
)
from agent_core.services.deadline_service import (
    VALID_DATE_TYPES as _VALID_DATE_TYPES,
)
from agent_core.services.deadline_service import (
    VALID_PRIORITIES as _VALID_PRIORITIES,
)
from agent_core.services.deadline_service import (
    DeadlineNotFoundError,
    DeadlineService,
    DeadlineValidationError,
)
from agent_core.services.deadline_service import (
    sanitise_date_fields as _sanitise_date_fields,  # noqa: F401
)
from agent_core.tools.registry import ToolRegistry, ToolSensitivity
from agent_core.tools.widgets import CalendarWidgetData

logger = get_logger("tools.deadline")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_DEFAULT_SINCE_DAYS = 7


# ---------------------------------------------------------------------------
# Helper: obtain a service instance
# ---------------------------------------------------------------------------


async def _get_service() -> DeadlineService:
    """Build a :class:`DeadlineService` backed by the shared store."""
    store = await get_deadline_store()
    return DeadlineService(store)


# Keep legacy alias so existing callers (if any) still work.
_get_store = get_deadline_store


# ---------------------------------------------------------------------------
# Mock external data sources
# ---------------------------------------------------------------------------

_MOCK_ANNOUNCEMENTS: list[dict[str, str]] = [
    {
        "course": "CS302",
        "title": "Project 1 Due",
        "content": "Project 1 is due on 2026-04-15. Please submit via Blackboard.",
        "date": "2026-04-01",
    },
    {
        "course": "CS302",
        "title": "Midterm Exam Reminder",
        "content": "Midterm exam will be held on 2026-04-20 in Room 301.",
        "date": "2026-04-02",
    },
    {
        "course": "MATH201",
        "title": "Homework 5 Posted",
        "content": "Homework 5 is due on 2026-04-10. Topics: integration.",
        "date": "2026-04-01",
    },
]

_MOCK_EMAILS: list[dict[str, str]] = [
    {
        "from": "prof.wang@university.edu",
        "subject": "CS302 — Group Presentation Schedule",
        "body": (
            "Your group presentation is scheduled"
            " for 2026-04-18. Prepare 15-min slides."
        ),
        "date": "2026-03-30",
    },
    {
        "from": "ta.zhang@university.edu",
        "subject": "PHYS101 Lab Report Reminder",
        "body": "Lab report #4 is due 2026-04-12. Submit PDF on Blackboard.",
        "date": "2026-03-31",
    },
]

_MOCK_EXAMS: list[dict[str, str]] = [
    {
        "course": "CS302",
        "title": "Midterm Exam",
        "date": "2026-04-20",
        "location": "Room 301",
    },
    {
        "course": "MATH201",
        "title": "Final Exam",
        "date": "2026-05-15",
        "location": "Hall A",
    },
    {
        "course": "PHYS101",
        "title": "Quiz 3",
        "date": "2026-04-08",
        "location": "Lab 102",
    },
]


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def get_announcements() -> str:
    """Fetch course announcements from Blackboard (mock).

    Returns:
        JSON array of announcement objects with course, title, content, date.
    """
    return json.dumps(_MOCK_ANNOUNCEMENTS, ensure_ascii=False)


def query_email(since_days: int = _DEFAULT_SINCE_DAYS) -> str:
    """Query recent emails that may contain deadline information (mock).

    Args:
        since_days: Number of days to look back. Currently ignored in mock.

    Returns:
        JSON array of email objects with from, subject, body, date fields.
    """
    return json.dumps(_MOCK_EMAILS, ensure_ascii=False)


def get_exams() -> str:
    """Fetch exam schedule from TAS system (mock).

    Returns:
        JSON array of exam objects with course, title, date, location fields.
    """
    return json.dumps(_MOCK_EXAMS, ensure_ascii=False)


async def save_deadlines(deadlines_json: str) -> str:
    """Persist a batch of extracted deadlines (SENSITIVE — requires HITL approval).

    The LLM should call this after extracting structured deadline data
    from announcements / emails / exams.  The frontend will display the
    list for user confirmation before this tool actually executes.

    Args:
        deadlines_json: JSON array of deadline objects.  Each must have
            at least ``title`` and ``due_date``; optional ``course``,
            ``priority``, ``source``, ``description``.

    Returns:
        Confirmation message with the number of saved items.
    """
    try:
        items = json.loads(deadlines_json)
    except (json.JSONDecodeError, TypeError):
        return json.dumps({"error": "Invalid JSON input for deadlines."})

    if not isinstance(items, list):
        items = [items]

    svc = await _get_service()
    saved, all_warnings, skipped = await svc.save_batch(items)

    result: dict[str, Any] = {
        "status": "success",
        "count": len(saved),
        "deadlines": [r.model_dump(mode="json") for r in saved],
    }
    if skipped:
        result["skipped"] = skipped
    if all_warnings:
        result["warnings"] = all_warnings
    return json.dumps(result, ensure_ascii=False)


async def list_deadlines(course: str = "", priority: str = "") -> str:
    """List stored deadlines with optional filters.

    Args:
        course: Filter by course name/code (case-insensitive). Empty = all.
        priority: Filter by priority level (high/medium/low). Empty = all.

    Returns:
        JSON array of matching deadline records.
    """
    svc = await _get_service()
    pri: DeadlinePriority | None = None
    if priority:
        try:
            pri = DeadlinePriority(priority.strip().lower())
        except ValueError:
            pri = None
    records = await svc.list_deadlines(
        course=course or None,
        priority=pri,
    )
    return json.dumps(
        [r.model_dump(mode="json") for r in records],
        ensure_ascii=False,
    )


async def add_deadline(
    title: str,
    course: str = "",
    due_date: str = "",
    priority: str = DeadlinePriority.MEDIUM.value,
    description: str = "",
    date_type: str = DateType.MOMENT_DAY.value,
    start_date: str = "",
) -> str:
    """Add a single deadline from natural language input.

    The LLM extracts structured fields from the user's message and
    calls this tool to persist a single deadline entry.

    Args:
        title: Short description of the task (required, non-empty).
        course: Course code or name (e.g. "CS302"). Empty if not applicable.
        due_date: ISO-8601 date or datetime string, e.g. "2026-04-15" or
            "2026-04-15T14:30:00".  **Must be a valid date string or empty.**
            If the date is unknown or not yet decided, leave this empty and
            set date_type to "no_date".  Do NOT pass natural language like
            "undecided" or "TBD" as a date value.
        priority: One of: high, medium, low.  Defaults to "medium".
        description: Optional longer notes about the task.
        date_type: Date classification — must be one of:
            "no_date" (no date, shown in backlog),
            "moment_day" (specific date, day precision),
            "moment_hm" (specific datetime, hour:minute precision),
            "period_day" (date range, day precision),
            "period_hm" (datetime range, hour:minute precision).
            When due_date is empty, this MUST be "no_date".
        start_date: ISO-8601 start date for period types only
            (e.g. "2026-04-10").  Required when date_type is "period_day"
            or "period_hm"; ignored for other types.

    Returns:
        JSON object of the created deadline record.  If any date values
        were invalid, a "warnings" list is included explaining corrections.
    """
    data: dict[str, Any] = {
        "title": title,
        "course": course,
        "due_date": due_date,
        "priority": priority,
        "description": description,
        "date_type": date_type,
        "start_date": start_date,
        "source": DeadlineSource.MANUAL.value,
    }
    svc = await _get_service()
    record, warnings = await svc.create_from_dict(data, source=DeadlineSource.MANUAL)
    result: dict[str, Any] = record.model_dump(mode="json")
    if warnings:
        result["warnings"] = warnings
    return json.dumps(result, ensure_ascii=False)


async def show_deadline_dashboard() -> str:
    """Display the deadline dashboard in the CalendarWidget.

    Fetches all stored deadlines and returns a CalendarWidgetData
    payload so the frontend renders the calendar view automatically.

    Returns:
        CalendarWidgetData JSON (triggers widget display).
    """
    svc = await _get_service()
    records = await svc.list_deadlines()
    events: list[dict[str, Any]] = [
        {
            "title": r.title,
            "date": r.due_date.isoformat() if r.due_date else "",
            "priority": r.priority.value,
            "course": r.course,
        }
        for r in records
    ]
    return CalendarWidgetData(events=events).model_dump_json()


async def delete_deadline(deadline_id: str) -> str:
    """Delete a deadline by its ID.

    Args:
        deadline_id: The unique ID of the deadline to delete.

    Returns:
        JSON confirmation or error message.
    """
    svc = await _get_service()
    try:
        await svc.delete(deadline_id)
    except DeadlineNotFoundError:
        return json.dumps({"error": f"Deadline '{deadline_id}' not found."})
    return json.dumps({"status": "deleted", "id": deadline_id})


async def update_deadline(
    deadline_id: str,
    title: str = "",
    course: str = "",
    due_date: str = "",
    priority: str = "",
    description: str = "",
    date_type: str = "",
    start_date: str = "",
) -> str:
    """Update one or more fields of an existing deadline.

    Only non-empty arguments are applied; omitted or empty-string
    arguments leave the existing value unchanged.

    Args:
        deadline_id: The unique ID of the deadline to update.
        title: New title (leave empty to keep current).
        course: New course (leave empty to keep current).
        due_date: New ISO-8601 due date (leave empty to keep current).
        priority: New priority (high/medium/low; leave empty to keep current).
        description: New description (leave empty to keep current).
        date_type: New date type (leave empty to keep current).
        start_date: New ISO-8601 start date (leave empty to keep current).

    Returns:
        JSON of the updated deadline record, or an error message.
    """
    svc = await _get_service()
    try:
        updated, warnings = await svc.update_from_tool(
            deadline_id,
            title=title,
            course=course,
            due_date=due_date,
            priority=priority,
            description=description,
            date_type=date_type,
            start_date=start_date,
        )
    except DeadlineNotFoundError:
        return json.dumps({"error": f"Deadline '{deadline_id}' not found."})
    except DeadlineValidationError as exc:
        return json.dumps({"error": exc.detail})

    result: dict[str, Any] = updated.model_dump(mode="json")
    if (
        not any(
            v
            for k, v in {
                "title": title,
                "course": course,
                "due_date": due_date,
                "priority": priority,
                "description": description,
                "date_type": date_type,
                "start_date": start_date,
            }.items()
        )
        and not warnings
    ):
        result["info"] = "No fields to update."

    if warnings:
        result["warnings"] = warnings
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_TOOL_DESCRIPTIONS: list[tuple[Any, str, ToolSensitivity]] = [
    (
        get_announcements,
        "Fetch course announcements from Blackboard. Returns a JSON array of "
        "announcement objects with course, title, content, and date fields. "
        "Call this when the user wants to sync deadlines from Blackboard.",
        ToolSensitivity.SAFE,
    ),
    (
        query_email,
        "Query recent emails that may contain deadline information. Returns a "
        "JSON array of email objects. Call this when syncing deadlines from email.",
        ToolSensitivity.SAFE,
    ),
    (
        get_exams,
        "Fetch the exam schedule from the TAS system. Returns a JSON array of "
        "exam objects with course, title, date, and location. Call this when "
        "the user wants to see upcoming exams.",
        ToolSensitivity.SAFE,
    ),
    (
        save_deadlines,
        "Save a batch of extracted deadlines to the database. Pass a JSON array "
        "of deadline objects. Each object must have: title (string), "
        "due_date (ISO-8601 string like '2026-04-15' or '' if unknown), "
        "course (string), priority (one of: high, medium, low), "
        "date_type (one of: no_date, moment_day, moment_hm, period_day, period_hm), "
        "start_date (ISO-8601 string, only for period types), "
        "source (one of: blackboard, email, tas, manual). "
        "IMPORTANT: due_date must be a valid ISO-8601 date or empty string. "
        "Never pass natural language like 'undecided' or 'TBD' as a date \u2014 use "
        "date_type='no_date' with due_date='' instead. "
        "This is a SENSITIVE operation \u2014 the user must confirm before saving.",
        ToolSensitivity.SENSITIVE,
    ),
    (
        list_deadlines,
        "List all stored deadlines. Optionally filter by course name or priority "
        "level (high/medium/low). Returns a JSON array of deadline records.",
        ToolSensitivity.SAFE,
    ),
    (
        add_deadline,
        "Add a single deadline. Extract these fields from the user's message: "
        "title (required string), course (string, e.g. 'CS302'), "
        "due_date (ISO-8601 date like '2026-04-15' or '2026-04-15T14:30:00'; "
        "leave EMPTY '' if unknown), "
        f"priority (one of: {_VALID_PRIORITIES}; default 'medium'), "
        f"date_type (one of: {_VALID_DATE_TYPES}; use 'no_date' when "
        "due_date is empty), "
        "start_date (ISO-8601 for period types only), "
        "description (optional notes). "
        "CRITICAL: due_date must be a valid ISO-8601 string or empty ''. "
        "Never pass natural language dates like 'undecided', 'TBD', 'next week' "
        "\u2014 convert to ISO-8601 or use date_type='no_date' with due_date=''.",
        ToolSensitivity.SAFE,
    ),
    (
        show_deadline_dashboard,
        "Display the deadline dashboard in the calendar widget. Fetches all "
        "stored deadlines and renders them visually. Call this when the user "
        "wants to see an overview of their deadlines or says 'show my deadlines'.",
        ToolSensitivity.SAFE,
    ),
    (
        delete_deadline,
        "Delete a deadline by its ID. Call this when the user wants to remove "
        "a task. Requires the deadline_id parameter (UUID string). Returns a "
        "confirmation or error message.",
        ToolSensitivity.SENSITIVE,
    ),
    (
        update_deadline,
        "Update one or more fields of an existing deadline. Requires "
        "deadline_id (UUID string). Optional fields: title, course, "
        "due_date (ISO-8601 or ''), priority (high/medium/low), "
        f"date_type (one of: {_VALID_DATE_TYPES}), "
        "start_date (ISO-8601 for period types), description. "
        "Only provide the fields you want to change; empty strings are ignored. "
        "CRITICAL: due_date/start_date must be valid ISO-8601 or empty.",
        ToolSensitivity.SAFE,
    ),
]


def register_deadline_tools(registry: ToolRegistry) -> None:
    """Register all deadline management tools with the given registry."""
    for func, description, sensitivity in _TOOL_DESCRIPTIONS:
        registry.add_tool(func=func, description=description, sensitivity=sensitivity)
