"""Shared provider for the agent memory store and service singletons."""

from __future__ import annotations

import tempfile
from pathlib import Path

from agent_core.config import AgentConfig
from agent_core.persistence.agent_memory_store import AgentMemoryStore
from agent_core.services.agent_memory_service import AgentMemoryService

_memory_store: AgentMemoryStore | None = None
_memory_service: AgentMemoryService | None = None


def _resolve_data_root() -> str:
    try:
        from agent_core.api.dependencies import get_config

        config = get_config()
    except RuntimeError:
        config = AgentConfig.from_env()

    if config.db_path == ":memory:":
        return tempfile.mkdtemp(prefix="agent-memory-")
    return str(Path(config.db_path).parent)


async def get_agent_memory_store() -> AgentMemoryStore:
    """Return the shared memory store, creating it lazily."""
    global _memory_store
    if _memory_store is None:
        _memory_store = AgentMemoryStore(_resolve_data_root())
    return _memory_store


async def get_agent_memory_service() -> AgentMemoryService:
    """Return the shared memory service, creating it lazily."""
    global _memory_service
    if _memory_service is None:
        store = await get_agent_memory_store()
        _memory_service = AgentMemoryService(store)
    return _memory_service


async def set_agent_memory_store(store: AgentMemoryStore | None) -> None:
    """Replace or clear the shared memory store singleton."""
    global _memory_store, _memory_service
    _memory_store = store
    _memory_service = None


async def set_agent_memory_service(service: AgentMemoryService | None) -> None:
    """Replace or clear the shared memory service singleton."""
    global _memory_service
    _memory_service = service
