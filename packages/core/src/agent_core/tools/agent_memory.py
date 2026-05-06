"""LLM-callable tools for file-backed agent memory topics."""

from __future__ import annotations

import json

from agent_core.models.agent_memory import MemoryUpdateMode
from agent_core.persistence.agent_memory_provider import get_agent_memory_service
from agent_core.tools.registry import ToolRegistry, ToolSensitivity

ERROR_KEY = "error"
INVALID_UPDATE_MODE_MESSAGE = "Invalid update mode. Use 'append' or 'rewrite'."


async def _service():  # noqa: ANN202
    return await get_agent_memory_service()


async def list_memory_topics() -> str:
    """List all memory topics as a JSON array of summaries."""
    service = await _service()
    topics = await service.list_topics()
    return json.dumps(
        [topic.model_dump() for topic in topics],
        ensure_ascii=False,
        indent=2,
    )


async def read_memory_file(filename: str) -> str:
    """Read the full Markdown text for one memory topic."""
    service = await _service()
    try:
        return await service.read_memory_file(filename)
    except (FileNotFoundError, ValueError) as exc:
        return json.dumps({ERROR_KEY: str(exc)}, ensure_ascii=False)


async def create_memory_file(
    filename: str,
    title: str,
    tags: list[str] | None,
    summary: str,
    content: str,
) -> str:
    """Create a new memory topic with structured metadata."""
    service = await _service()
    try:
        topic = await service.create_memory_file(
            filename=filename,
            title=title,
            tags=tags or [],
            summary=summary,
            content=content,
        )
    except (FileExistsError, ValueError) as exc:
        return json.dumps({ERROR_KEY: str(exc)}, ensure_ascii=False)
    return json.dumps(topic.model_dump(), ensure_ascii=False, indent=2)


async def update_memory_file(
    filename: str,
    mode: str,
    content: str,
    title: str | None = None,
    tags: list[str] | None = None,
    summary: str | None = None,
) -> str:
    """Append to or rewrite an existing memory topic."""
    service = await _service()
    try:
        if mode not in {MemoryUpdateMode.APPEND.value, MemoryUpdateMode.REWRITE.value}:
            raise ValueError(INVALID_UPDATE_MODE_MESSAGE)
        update_mode = MemoryUpdateMode(mode)
        topic = await service.update_memory_file(
            filename=filename,
            mode=update_mode,
            content=content,
            title=title,
            tags=tags,
            summary=summary,
        )
    except (FileNotFoundError, ValueError) as exc:
        return json.dumps({ERROR_KEY: str(exc)}, ensure_ascii=False)
    return json.dumps(topic.model_dump(), ensure_ascii=False, indent=2)


def register_agent_memory_tools(registry: ToolRegistry) -> None:
    """Register the agent memory tools through auto-discovery."""

    @registry.register(
        description=(
            "List all persisted memory topics. Returns filename, title, tags, "
            "summary, and last_updated for each Markdown memory file."
        ),
        sensitivity=ToolSensitivity.SAFE,
        name="list_memory_topics",
    )
    async def _list_memory_topics() -> str:
        return await list_memory_topics()

    @registry.register(
        description=(
            "Read one persisted memory topic by filename and return the full "
            "Markdown text, including YAML frontmatter."
        ),
        sensitivity=ToolSensitivity.SAFE,
        name="read_memory_file",
    )
    async def _read_memory_file(filename: str) -> str:
        return await read_memory_file(filename)

    @registry.register(
        description=(
            "Create a new persisted memory topic as a Markdown file. Provide a "
            "filename, title, tags, summary, and Markdown body content."
        ),
        sensitivity=ToolSensitivity.SENSITIVE,
        name="create_memory_file",
    )
    async def _create_memory_file(
        filename: str,
        title: str,
        tags: list[str] | None = None,
        summary: str = "",
        content: str = "",
    ) -> str:
        return await create_memory_file(filename, title, tags, summary, content)

    @registry.register(
        description=(
            "Update an existing memory topic. mode='append' adds content to the "
            "end of the body. mode='rewrite' replaces the body after creating a "
            "backup of the previous file. Optional title, tags, and summary "
            "fields can update YAML metadata; rewrite also accepts full Markdown "
            "with embedded frontmatter."
        ),
        sensitivity=ToolSensitivity.SENSITIVE,
        name="update_memory_file",
    )
    async def _update_memory_file(
        filename: str,
        mode: str,
        content: str,
        title: str | None = None,
        tags: list[str] | None = None,
        summary: str | None = None,
    ) -> str:
        return await update_memory_file(filename, mode, content, title, tags, summary)
