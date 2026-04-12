"""Deadline management tools — fetch, extract, store, and display academic deadlines.

External data sources (Blackboard, Email, TAS) are currently mocked.
All tools follow the ``register_*_tools(registry)`` convention so they
are auto-discovered by :func:`agent_core.tools.auto_discover_and_register`.
"""

import json
import uuid
from pathlib import Path
from typing import Any

from agent_core.logging_utils import get_logger
from agent_core.models.deadline import DeadlinePriority, DeadlineRecord, DeadlineSource
from agent_core.persistence.deadline_store import DeadlineStore
from agent_core.tools.registry import ToolRegistry, ToolSensitivity
from agent_core.tools.widgets import CalendarWidgetData

logger = get_logger("tools.deadline")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_DEFAULT_TITLE = "Untitled"
_DEFAULT_SINCE_DAYS = 7

# ---------------------------------------------------------------------------
# Module-level store singleton (initialized lazily)
# ---------------------------------------------------------------------------
_store: DeadlineStore | None = None


async def _get_store() -> DeadlineStore:
    """Return (and lazily initialise) the deadline store singleton.

    If the module-level store has been closed externally (e.g. in tests),
    its internal ``_db`` attribute is ``None``.  In that case we recreate and
    reinitialise a fresh store so callers always receive a usable instance.
    """
    global _store
    if _store is None or _store._db is None:
        # Derive a persistent path from AgentConfig so deadlines survive
        # process restarts.  Fall back to :memory: if config is unavailable.
        try:
            from agent_core.config import AgentConfig

            cfg = AgentConfig.from_env()
            # Place the deadline DB beside the session DB
            db_path = str(Path(cfg.db_path).with_name("deadlines.db"))
        except Exception:
            db_path = ":memory:"
        _store = DeadlineStore(db_path)
        await _store.initialize()
    return _store


async def set_deadline_store(store: DeadlineStore | None) -> None:
    """Replace or clear the module-level store (used by DI / tests).

    Passing ``None`` resets the singleton so the next :func:`_get_store`
    call will create a fresh in-memory store.
    """
    global _store
    _store = store


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
    store = await _get_store()
    try:
        items = json.loads(deadlines_json)
    except (json.JSONDecodeError, TypeError):
        return json.dumps({"error": "Invalid JSON input for deadlines."})

    if not isinstance(items, list):
        items = [items]

    saved: list[DeadlineRecord] = []
    skipped: list[str] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            skipped.append(f"item[{i}] is not a dict")
            continue
        try:
            raw_priority = item.get("priority", DeadlinePriority.MEDIUM)
            try:
                priority = DeadlinePriority(raw_priority)
            except ValueError:
                logger.warning(
                    "Invalid priority %r, defaulting to medium", raw_priority
                )
                priority = DeadlinePriority.MEDIUM

            raw_source = item.get("source", DeadlineSource.MANUAL)
            try:
                source = DeadlineSource(raw_source)
            except ValueError:
                logger.warning("Invalid source %r, defaulting to manual", raw_source)
                source = DeadlineSource.MANUAL

            record = DeadlineRecord(
                id=item.get("id", str(uuid.uuid4())),
                title=item.get("title", _DEFAULT_TITLE),
                course=item.get("course", ""),
                due_date=item.get("due_date", ""),
                priority=priority,
                source=source,
                description=item.get("description", ""),
            )
            await store.add(record)
            saved.append(record)
        except Exception as exc:  # noqa: BLE001
            skipped.append(f"item[{i}]: {exc}")
            logger.warning("Skipped malformed deadline item[%d]: %s", i, exc)

    result: dict[str, Any] = {
        "status": "success",
        "count": len(saved),
        "deadlines": [r.model_dump() for r in saved],
    }
    if skipped:
        result["skipped"] = skipped
    return json.dumps(result, ensure_ascii=False)


async def list_deadlines(course: str = "", priority: str = "") -> str:
    """List stored deadlines with optional filters.

    Args:
        course: Filter by course name/code (case-insensitive). Empty = all.
        priority: Filter by priority level (high/medium/low). Empty = all.

    Returns:
        JSON array of matching deadline records.
    """
    store = await _get_store()
    records = await store.list_all(
        course=course or None,
        priority=priority or None,
    )
    return json.dumps(
        [r.model_dump() for r in records],
        ensure_ascii=False,
    )


async def add_deadline(
    title: str,
    course: str = "",
    due_date: str = "",
    priority: str = "medium",
    description: str = "",
) -> str:
    """Add a single deadline from natural language input.

    The LLM extracts structured fields from the user's message and
    calls this tool to persist a single deadline entry.

    Args:
        title: Short description of the task.
        course: Course code or name.
        due_date: ISO-8601 date or datetime string.
        priority: Urgency level (high / medium / low).
        description: Optional longer notes.

    Returns:
        JSON object of the created deadline record.
    """
    store = await _get_store()
    record = DeadlineRecord(
        id=str(uuid.uuid4()),
        title=title,
        course=course,
        due_date=due_date,
        priority=DeadlinePriority(priority),
        source=DeadlineSource.MANUAL,
        description=description,
    )
    await store.add(record)
    return json.dumps(record.model_dump(), ensure_ascii=False)


async def show_deadline_dashboard() -> str:
    """Display the deadline dashboard in the CalendarWidget.

    Fetches all stored deadlines and returns a CalendarWidgetData
    payload so the frontend renders the calendar view automatically.

    Returns:
        CalendarWidgetData JSON (triggers widget display).
    """
    store = await _get_store()
    records = await store.list_all()
    events: list[dict[str, Any]] = [
        {
            "title": r.title,
            "date": r.due_date,
            "priority": r.priority.value,
            "course": r.course,
        }
        for r in records
    ]
    return CalendarWidgetData(events=events).model_dump_json()


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
        "of deadline objects (each with title, due_date, course, priority, source). "
        "This is a SENSITIVE operation — the user must confirm before saving. "
        "Call this after extracting deadlines from announcements/emails/exams.",
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
        "Add a single deadline. Extract title, course, due_date, and priority "
        "from the user's natural language input and pass them as arguments. "
        "Call this when the user mentions a specific upcoming task or deadline.",
        ToolSensitivity.SAFE,
    ),
    (
        show_deadline_dashboard,
        "Display the deadline dashboard in the calendar widget. Fetches all "
        "stored deadlines and renders them visually. Call this when the user "
        "wants to see an overview of their deadlines or says 'show my deadlines'.",
        ToolSensitivity.SAFE,
    ),
]


def register_deadline_tools(registry: ToolRegistry) -> None:
    """Register all deadline management tools with the given registry."""
    for func, description, sensitivity in _TOOL_DESCRIPTIONS:
        registry.add_tool(func=func, description=description, sensitivity=sensitivity)
