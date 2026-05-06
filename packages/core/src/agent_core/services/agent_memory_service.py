"""Business logic for file-backed agent memory topics."""

from __future__ import annotations

from datetime import UTC, datetime

from agent_core.models.agent_memory import (
    MemoryDocument,
    MemoryFrontmatter,
    MemoryTopicSummary,
    MemoryUpdateMode,
)
from agent_core.persistence.agent_memory_store import AgentMemoryStore


class AgentMemoryService:
    """Orchestrate memory topic CRUD operations for tools and routes."""

    def __init__(self, store: AgentMemoryStore) -> None:
        self._store = store

    @property
    def memory_root(self) -> str:
        """Return the filesystem root used for persisted memory topics."""
        return str(self._store.memory_root)

    async def list_topics(self) -> list[MemoryTopicSummary]:
        """List all stored memory topics as routing summaries."""
        documents = await self._store.list_documents()
        return [self._to_topic_summary(document) for document in documents]

    async def read_memory_file(self, filename: str) -> str:
        """Return the raw Markdown text for one topic."""
        return await self._store.read_markdown(filename)

    async def create_memory_file(
        self,
        filename: str,
        title: str,
        tags: list[str],
        summary: str,
        content: str,
    ) -> MemoryTopicSummary:
        """Create a new memory topic with backend-generated frontmatter."""
        document = await self._store.create_document(
            filename=filename,
            frontmatter=MemoryFrontmatter(
                title=title.strip(),
                tags=[tag.strip() for tag in tags if tag.strip()],
                summary=summary.strip(),
                last_updated=self._timestamp(),
            ),
            content=content,
        )
        return self._to_topic_summary(document)

    async def update_memory_file(
        self,
        filename: str,
        mode: MemoryUpdateMode,
        content: str,
        title: str | None = None,
        tags: list[str] | None = None,
        summary: str | None = None,
    ) -> MemoryTopicSummary:
        """Append to or rewrite one topic while optionally updating metadata."""
        document = await self._store.update_document(
            filename=filename,
            mode=mode,
            content=content,
            timestamp=self._timestamp(),
            title=title.strip() if title is not None else None,
            tags=[tag.strip() for tag in tags if tag.strip()]
            if tags is not None
            else None,
            summary=summary.strip() if summary is not None else None,
        )
        return self._to_topic_summary(document)

    def _to_topic_summary(self, document: MemoryDocument) -> MemoryTopicSummary:
        return MemoryTopicSummary(
            filename=document.filename,
            title=document.frontmatter.title,
            tags=document.frontmatter.tags,
            summary=document.frontmatter.summary,
            last_updated=document.frontmatter.last_updated,
        )

    def _timestamp(self) -> str:
        return datetime.now(UTC).isoformat(timespec="seconds")
