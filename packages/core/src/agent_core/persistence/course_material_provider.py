"""Course material store — singleton provider for CourseMaterialStore."""

from pathlib import Path

from agent_core.logging_utils import get_logger
from agent_core.persistence.course_material_store import CourseMaterialStore

logger = get_logger("persistence.course_material_provider")

_store: CourseMaterialStore | None = None


async def get_course_material_store() -> CourseMaterialStore:
    """Return (and lazily initialise) the course material store singleton."""
    global _store
    if _store is None or not _store.is_connected:
        try:
            from agent_core.config import AgentConfig

            cfg = AgentConfig.from_env()
            db_path = str(Path(cfg.db_path).with_name("course_materials.db"))
            max_size_bytes = cfg.course_material_max_size_mb * 1024 * 1024
            allowed_extensions = frozenset(
                ext.strip().lower()
                for ext in cfg.course_material_allowed_extensions.split(",")
                if ext.strip()
            )
        except Exception:
            db_path = ":memory:"
            max_size_bytes = None
            allowed_extensions = None
        _store = CourseMaterialStore(db_path, max_size_bytes, allowed_extensions)
        await _store.initialize()
    return _store


async def set_course_material_store(store: CourseMaterialStore | None) -> None:
    """Replace or clear the module-level store (used by DI / tests)."""
    global _store
    _store = store
