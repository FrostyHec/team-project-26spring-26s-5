"""Shared deadline store provider — single source for the DeadlineStore singleton.

Both the REST API layer and the LLM Tool layer import from here,
eliminating the previous reverse-dependency where routes imported
from tools to reach the store.
"""

from pathlib import Path

from agent_core.logging_utils import get_logger
from agent_core.persistence.deadline_store import DeadlineStore

logger = get_logger("persistence.deadline_provider")

# ---------------------------------------------------------------------------
# Module-level store singleton (initialized lazily)
# ---------------------------------------------------------------------------
_store: DeadlineStore | None = None


async def get_deadline_store() -> DeadlineStore:
    """Return (and lazily initialise) the deadline store singleton.

    If the module-level store has been closed externally (e.g. in tests),
    its internal ``_db`` attribute is ``None``.  In that case we recreate
    and reinitialise a fresh store so callers always receive a usable
    instance.
    """
    global _store
    if _store is None or not _store.is_connected:
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

    Passing ``None`` resets the singleton so the next
    :func:`get_deadline_store` call will create a fresh store.
    """
    global _store
    _store = store
