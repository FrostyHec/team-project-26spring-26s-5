"""Shared email service provider — single source for the EmailService singleton.

Both the REST API layer (via ``dependencies.py``) and the LLM Tool layer
import from here, so that business logic is never duplicated.

The provider lazily constructs an :class:`EmailService` backed by an
:class:`EmailStore`, :class:`ProfileStore`, and :class:`EmailClient`.
"""

from pathlib import Path

from agent_core.logging_utils import get_logger
from agent_core.persistence.email_store import EmailStore
from agent_core.persistence.profile_store import ProfileStore
from agent_core.services.email_client import EmailClient
from agent_core.services.email_service import EmailService

logger = get_logger("persistence.email_provider")

# ---------------------------------------------------------------------------
# Module-level singletons (initialised lazily)
# ---------------------------------------------------------------------------
_email_store: EmailStore | None = None
_email_service: EmailService | None = None


async def get_email_store() -> EmailStore:
    """Return (and lazily initialise) the email store singleton."""
    global _email_store
    if _email_store is None:
        try:
            from agent_core.config import AgentConfig

            cfg = AgentConfig.from_env()
            db_path = str(Path(cfg.db_path).with_name("email.db"))
        except Exception:
            db_path = ":memory:"
        _email_store = EmailStore(db_path)
        await _email_store.initialize()
    return _email_store


async def get_email_service() -> EmailService:
    """Return (and lazily initialise) the email service singleton.

    The service is wired to the shared :class:`EmailStore`,
    :class:`ProfileStore`, and :class:`EmailClient`.
    """
    global _email_service
    if _email_service is not None:
        return _email_service

    store = await get_email_store()

    # Profile store — reuse the API-level singleton if available,
    # else create a standalone one.
    try:
        from agent_core.api.dependencies import get_profile_store

        profile_store = get_profile_store()
    except RuntimeError:
        from agent_core.config import AgentConfig

        cfg = AgentConfig.from_env()
        profile_store = ProfileStore(cfg.db_path)
        await profile_store.initialize()

    try:
        from agent_core.config import AgentConfig

        cfg = AgentConfig.from_env()
        data_root = str(Path(cfg.db_path).parent)
    except Exception:
        data_root = "."

    client = EmailClient(data_root=data_root)
    _email_service = EmailService(
        email_store=store,
        profile_store=profile_store,
        email_client=client,
        data_root=data_root,
    )
    return _email_service


async def set_email_store(store: EmailStore | None) -> None:
    """Replace or clear the module-level email store (used by DI / tests)."""
    global _email_store, _email_service
    _email_store = store
    _email_service = None  # force re-creation of service


async def set_email_service(service: EmailService | None) -> None:
    """Replace or clear the module-level email service (used by DI / tests)."""
    global _email_service
    _email_service = service
