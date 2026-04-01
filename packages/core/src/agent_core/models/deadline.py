"""Deadline data models — structured types for academic deadline management.

Provides enums and Pydantic models used by the deadline tools, persistence
layer, and API routes.
"""

from enum import StrEnum

from pydantic import BaseModel


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


class DeadlineRecord(BaseModel):
    """A single academic deadline persisted in the store.

    Attributes:
        id: Unique identifier (UUID).
        title: Short description of the deadline item.
        course: Course code or name (e.g. "CS302").
        due_date: ISO-8601 date/datetime string.
        priority: Urgency level.
        source: Where this deadline was collected from.
        description: Optional longer description or notes.
    """

    id: str = ""
    title: str
    course: str = ""
    due_date: str = ""
    priority: DeadlinePriority = DeadlinePriority.MEDIUM
    source: DeadlineSource = DeadlineSource.MANUAL
    description: str = ""
