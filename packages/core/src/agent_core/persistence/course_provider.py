"""Shared course store provider — single source for the CourseStore singleton."""

from agent_core.config import database_file
from agent_core.logging_utils import get_logger
from agent_core.persistence.course_store import CourseStore

logger = get_logger("persistence.course_provider")

_store: CourseStore | None = None


async def get_course_store() -> CourseStore:
    """Return (and lazily initialise) the course store singleton."""
    global _store
    if _store is None or not _store.is_connected:
        try:
            from agent_core.config import AgentConfig

            cfg = AgentConfig.from_env()
            db_path = database_file(cfg.db_path, "courses.db")
        except Exception:
            db_path = ":memory:"
        _store = CourseStore(db_path)
        await _store.initialize()
    return _store


async def set_course_store(store: CourseStore | None) -> None:
    """Replace or clear the module-level store (used by DI / tests)."""
    global _store
    _store = store
