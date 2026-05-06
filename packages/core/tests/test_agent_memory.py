"""Focused tests for the Agent Memory Markdown tool slice."""

from __future__ import annotations

import json
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_core.config import AgentConfig
from agent_core.models.agent_memory import MemoryUpdateMode
from agent_core.persistence.agent_memory_provider import (
    get_agent_memory_service,
    set_agent_memory_service,
    set_agent_memory_store,
)
from agent_core.persistence.agent_memory_store import AgentMemoryStore
from agent_core.services.agent_memory_service import AgentMemoryService
from agent_core.tools.agent_memory import (
    create_memory_file,
    list_memory_topics,
    read_memory_file,
    update_memory_file,
)


@pytest.fixture(autouse=True)
async def reset_agent_memory_provider() -> AsyncGenerator[None, None]:
    """Keep the provider singleton isolated across tests."""
    await set_agent_memory_service(None)
    await set_agent_memory_store(None)
    yield
    await set_agent_memory_service(None)
    await set_agent_memory_store(None)


@pytest.mark.asyncio
async def test_agent_memory_service_creates_lists_reads_and_appends(
    tmp_path: Path,
) -> None:
    """Service operations should preserve metadata and append body content."""
    service = AgentMemoryService(AgentMemoryStore(tmp_path))

    created = await service.create_memory_file(
        filename="user_food",
        title="User Food",
        tags=["preference", "food"],
        summary="Diet preferences",
        content="- likes noodles",
    )

    assert created.filename == "user_food.md"
    assert created.title == "User Food"
    assert created.tags == ["preference", "food"]

    topics = await service.list_topics()
    assert topics == [created]

    raw_markdown = await service.read_memory_file("user_food")
    assert raw_markdown.startswith("---\n")
    assert "title: User Food" in raw_markdown

    updated = await service.update_memory_file(
        filename="user_food",
        mode=MemoryUpdateMode.APPEND,
        content="- avoids peanuts",
    )

    assert updated.filename == "user_food.md"
    appended_markdown = await service.read_memory_file("user_food.md")
    assert "- likes noodles" in appended_markdown
    assert "- avoids peanuts" in appended_markdown
    assert updated.summary == "Diet preferences"


@pytest.mark.asyncio
async def test_agent_memory_rewrite_creates_backup_and_preserves_frontmatter(
    tmp_path: Path,
) -> None:
    """Rewrite mode should back up the previous file before replacing the body."""
    store = AgentMemoryStore(tmp_path)
    service = AgentMemoryService(store)
    await service.create_memory_file(
        filename="project_notes",
        title="Project Notes",
        tags=["project"],
        summary="Working notes",
        content="old body",
    )

    updated = await service.update_memory_file(
        filename="project_notes",
        mode=MemoryUpdateMode.REWRITE,
        content="new body",
    )

    backup_files = list(store.backup_root.glob("*.md"))
    assert len(backup_files) == 1
    assert backup_files[0].read_text(encoding="utf-8").endswith("old body\n")

    rewritten_markdown = await service.read_memory_file("project_notes")
    assert "new body" in rewritten_markdown
    assert "old body" not in rewritten_markdown
    assert updated.title == "Project Notes"
    assert updated.tags == ["project"]


@pytest.mark.asyncio
async def test_agent_memory_rewrite_absorbs_embedded_frontmatter(
    tmp_path: Path,
) -> None:
    """Rewrite should consume embedded Markdown frontmatter.

    This prevents duplicated YAML blocks after a full-Markdown rewrite.
    """
    title_text = "\u5b66\u751f\u6863\u6848 - \u8f6f\u4ef6\u5de5\u7a0b\u5b66\u4e60\u8005"
    initial_tags = [
        "\u5b66\u751f",
        "\u5927\u4e09",
        "\u8f6f\u4ef6\u5de5\u7a0b",
    ]
    updated_tags = [
        "\u5b66\u751f",
        "\u5927\u56db",
        "\u8f6f\u4ef6\u5de5\u7a0b",
        "\u9762\u5411\u5bf9\u8c61",
        "\u8bbe\u8ba1\u6a21\u5f0f",
    ]
    initial_summary = (
        "\u8bb0\u5f55\u7528\u6237\u662f\u4e00\u540d\u5927\u4e09"
        "\u8f6f\u4ef6\u5de5\u7a0b\u5b66\u751f"
    )
    updated_summary = (
        "\u8bb0\u5f55\u7528\u6237\u662f\u4e00\u540d\u5927\u56db\u8f6f\u4ef6\u5de5"
        "\u7a0b\u5b66\u751f\uff0c\u5bf9\u9762\u5411\u5bf9\u8c61\u548c\u8bbe\u8ba1"
        "\u6a21\u5f0f\u611f\u5174\u8da3"
    )
    initial_body = (
        "# \u5b66\u751f\u6863\u6848\n\n- **\u8eab\u4efd**: \u5927\u4e09\u5b66\u751f"
    )
    updated_body = (
        "# \u5b66\u751f\u6863\u6848\n\n- **\u8eab\u4efd**: \u5927\u56db\u5b66\u751f"
    )

    service = AgentMemoryService(AgentMemoryStore(tmp_path))
    await service.create_memory_file(
        filename="student_profile",
        title=title_text,
        tags=initial_tags,
        summary=initial_summary,
        content=initial_body,
    )

    full_markdown = (
        "---\n"
        f"title: {title_text}\n"
        "tags:\n"
        f"- {updated_tags[0]}\n"
        f"- {updated_tags[1]}\n"
        f"- {updated_tags[2]}\n"
        f"- {updated_tags[3]}\n"
        f"- {updated_tags[4]}\n"
        f"summary: {updated_summary}\n"
        "last_updated: '2026-05-06'\n"
        "---\n\n"
        f"{updated_body}\n"
    )
    updated = await service.update_memory_file(
        filename="student_profile",
        mode=MemoryUpdateMode.REWRITE,
        content=full_markdown,
    )

    rewritten_markdown = await service.read_memory_file("student_profile")
    assert updated.tags == updated_tags
    assert updated.summary == updated_summary
    assert rewritten_markdown.count(f"title: {title_text}") == 1
    assert rewritten_markdown.count("\n---\n") == 1
    assert rewritten_markdown.endswith(f"{updated_body.splitlines()[-1]}\n")


@pytest.mark.asyncio
async def test_agent_memory_tools_return_stable_json_errors(tmp_path: Path) -> None:
    """Tool helpers should expose machine-readable success and error payloads."""
    await set_agent_memory_service(AgentMemoryService(AgentMemoryStore(tmp_path)))

    created_payload = json.loads(
        await create_memory_file(
            filename="travel_notes",
            title="Travel Notes",
            tags=["travel"],
            summary="Trip checklist",
            content="- passport",
        )
    )
    assert created_payload["filename"] == "travel_notes.md"

    topics_payload = json.loads(await list_memory_topics())
    assert topics_payload == [created_payload]

    read_payload = await read_memory_file("travel_notes")
    assert "Trip checklist" in read_payload

    missing_payload = json.loads(await read_memory_file("missing_topic"))
    assert missing_payload == {"error": "Memory file not found: missing_topic.md"}

    invalid_payload = json.loads(
        await create_memory_file(
            filename="../bad",
            title="Bad",
            tags=None,
            summary="",
            content="",
        )
    )
    assert invalid_payload["error"]

    rewrite_payload = json.loads(
        await update_memory_file(
            "travel_notes",
            "rewrite",
            "- tickets",
            title="Travel Notes Updated",
            tags=["travel", "updated"],
            summary="Updated summary",
        )
    )
    assert rewrite_payload["filename"] == "travel_notes.md"
    assert rewrite_payload["title"] == "Travel Notes Updated"
    assert rewrite_payload["tags"] == ["travel", "updated"]
    assert rewrite_payload["summary"] == "Updated summary"

    rewritten_payload = await read_memory_file("travel_notes")
    assert "title: Travel Notes Updated" in rewritten_payload
    assert "summary: Updated summary" in rewritten_payload

    invalid_mode_payload = json.loads(
        await update_memory_file("travel_notes", "bad-mode", "- ignored")
    )
    assert invalid_mode_payload == {
        "error": "Invalid update mode. Use 'append' or 'rewrite'."
    }


@pytest.mark.asyncio
async def test_agent_memory_provider_uses_temp_root_for_in_memory_db() -> None:
    """The lazy provider should isolate memory files when db_path is :memory:."""
    with patch.object(
        AgentConfig,
        "from_env",
        return_value=AgentConfig(db_path=":memory:"),
    ):
        service = await get_agent_memory_service()
        created = await service.create_memory_file(
            filename="session_pref",
            title="Session Pref",
            tags=[],
            summary="",
            content="- temporary",
        )

    memory_root = Path(service.memory_root)
    assert created.filename == "session_pref.md"
    assert memory_root.name == "agent_memory"
    assert str(memory_root.parent).startswith(tempfile.gettempdir())
    assert (memory_root / "session_pref.md").exists()
