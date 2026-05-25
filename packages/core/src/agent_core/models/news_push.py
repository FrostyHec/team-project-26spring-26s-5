"""Campus news push data models."""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class NewsPushStatus(StrEnum):
    """Result status for the daily campus news email push."""

    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


class NewsPushSettings(BaseModel):
    """Global campus news push configuration (email-only)."""

    enabled: bool = False
    push_time: str = "08:30"
    limit: int = Field(default=20, ge=1, le=50)

    @model_validator(mode="after")
    def _validate_push_settings(self) -> NewsPushSettings:
        """Validate the configured push time string."""
        if not re.fullmatch(r"\d{2}:\d{2}", self.push_time):
            raise ValueError("push_time must be a valid HH:MM time.")

        hour, minute = (int(part) for part in self.push_time.split(":"))
        if hour > 23 or minute > 59:
            raise ValueError("push_time must be a valid HH:MM time.")

        return self


class NewsPushLogEntry(BaseModel):
    """A single campus news push delivery log entry (per target date)."""

    target_date: str
    status: NewsPushStatus
    sent_at: str
    error: str = ""
