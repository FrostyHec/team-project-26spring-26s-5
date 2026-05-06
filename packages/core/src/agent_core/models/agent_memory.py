"""Typed models for file-backed agent memory topics."""

from enum import StrEnum

from pydantic import BaseModel, Field


class MemoryUpdateMode(StrEnum):
    """Supported update behaviors for an existing memory topic."""

    APPEND = "append"
    REWRITE = "rewrite"


class MemoryFrontmatter(BaseModel):
    """YAML frontmatter stored at the top of each memory Markdown file."""

    title: str = ""
    tags: list[str] = Field(default_factory=list)
    summary: str = ""
    last_updated: str = ""


class MemoryTopicSummary(BaseModel):
    """Compact topic summary returned to the LLM for routing decisions."""

    filename: str
    title: str = ""
    tags: list[str] = Field(default_factory=list)
    summary: str = ""
    last_updated: str = ""


class MemoryDocument(BaseModel):
    """A parsed memory Markdown file with frontmatter and body."""

    filename: str
    frontmatter: MemoryFrontmatter
    content: str = ""
