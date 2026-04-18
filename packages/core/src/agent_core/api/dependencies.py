"""Dependency injection for FastAPI routes.

Provides the shared ReactAgent instance and SessionStore via
FastAPI's Depends system, analogous to Spring Boot's @Autowired.
"""

from typing import Any

from langchain_openai import ChatOpenAI

from agent_core.api.approval import make_api_approval_handler
from agent_core.config import AgentConfig
from agent_core.engine.agent import ReactAgent
from agent_core.logging_utils import get_logger
from agent_core.persistence.alarm_store import AlarmStore
from agent_core.persistence.deadline_store import DeadlineStore
from agent_core.persistence.email_store import EmailStore
from agent_core.persistence.profile_store import ProfileStore
from agent_core.persistence.session_store import SessionStore
from agent_core.security.encryption import reset_fernet
from agent_core.services.alarm_scheduler import AlarmScheduler
from agent_core.services.alarm_service import AlarmService
from agent_core.services.email_client import EmailClient
from agent_core.services.email_service import EmailService
from agent_core.services.profile_service import ProfileService
from agent_core.skills import get_system_prompt_for_skill
from agent_core.tools import auto_discover_and_register
from agent_core.tools.registry import ToolRegistry

logger = get_logger("api.dependencies")

# Module-level singletons (initialized during app lifespan)
_agent: ReactAgent | None = None
_store: SessionStore | None = None
_profile_store: ProfileStore | None = None
_profile_service: ProfileService | None = None
_email_store: EmailStore | None = None
_email_service: EmailService | None = None
_alarm_store: AlarmStore | None = None
_alarm_service: AlarmService | None = None
_alarm_scheduler: AlarmScheduler | None = None
_config: AgentConfig | None = None
_llm: ChatOpenAI | None = None


def _create_tool_registry() -> ToolRegistry:
    """Create a ToolRegistry with all available tools registered.

    Uses :func:`auto_discover_and_register` to scan every module in
    ``agent_core.tools`` and call any ``register_*_tools`` functions
    found, so new tool modules are picked up automatically.

    Returns:
        Fully populated ToolRegistry.
    """
    registry = ToolRegistry()
    auto_discover_and_register(registry)
    return registry


def create_agent(
    config: AgentConfig | None = None,
    skill_id: str | None = None,
    language: str = "en",
) -> ReactAgent:
    """Create and configure a ReactAgent instance.

    Args:
        config: Optional configuration. Uses env if not provided.
        skill_id: Optional skill ID for system prompt override.
        language: Language code for multi-language skills (default "en").

    Returns:
        Configured ReactAgent.
    """
    if config is None:
        config = AgentConfig.from_env()

    llm_kwargs: dict[str, Any] = {
        "model": config.model_name,
        "temperature": config.temperature,
    }
    if config.openai_api_key:
        llm_kwargs["api_key"] = config.openai_api_key
    if config.openai_base_url:
        llm_kwargs["base_url"] = config.openai_base_url

    llm = ChatOpenAI(**llm_kwargs)
    registry = _create_tool_registry()

    # Use skill-specific system prompt if provided (with language support)
    system_prompt = (
        get_system_prompt_for_skill(skill_id, language) or config.system_prompt
    )

    return ReactAgent(
        llm=llm,
        tool_registry=registry,
        system_prompt=system_prompt,
    )


async def init_dependencies(config: AgentConfig | None = None) -> None:
    """Initialize all singletons (called during lifespan startup).

    Args:
        config: Optional configuration.
    """
    global _llm
    global _agent, _store, _profile_store, _profile_service
    global _email_store, _email_service, _alarm_store, _alarm_service
    global _alarm_scheduler, _config
    _config = config or AgentConfig.from_env()

    # Configure encryption key if provided
    if _config.encryption_key:
        reset_fernet(_config.encryption_key)

    _store = SessionStore(_config.db_path)
    await _store.initialize()

    _profile_store = ProfileStore(_config.db_path)
    await _profile_store.initialize()
    _profile_service = ProfileService(_profile_store)

    # Email subsystem
    import tempfile
    from pathlib import Path

    if _config.db_path == ":memory:":
        email_db = ":memory:"
        data_root = tempfile.mkdtemp()
    else:
        email_db = str(Path(_config.db_path).with_name("email.db"))
        data_root = str(Path(_config.db_path).parent)
    _email_store = EmailStore(email_db)
    await _email_store.initialize()
    _email_service = EmailService(
        email_store=_email_store,
        profile_store=_profile_store,
        email_client=EmailClient(data_root=data_root),
        data_root=data_root,
    )
    # Register the singletons in the provider module so tools can access them
    from agent_core.persistence.email_provider import (
        set_email_service,
        set_email_store,
    )

    await set_email_store(_email_store)
    await set_email_service(_email_service)

    # Alarm subsystem
    _alarm_store = AlarmStore(_config.db_path)
    await _alarm_store.initialize()

    # Adapter: bridge AlarmService's (subject, body) → EmailService.send_email()
    async def _alarm_send_email(subject: str, body: str) -> None:
        from agent_core.models.email import SendEmailRequest

        profile = await _profile_store.get_profile()
        if not profile.email_account:
            logger.warning(
                "Cannot send alarm email: no email account configured in profile"
            )
            return
        logger.info("Sending alarm email to %s", profile.email_account)
        await _email_service.send_email(
            SendEmailRequest(to=profile.email_account, subject=subject, plain_body=body)
        )
        logger.info("Alarm email sent to %s", profile.email_account)

    _alarm_service = AlarmService(
        deadline_store=await _init_deadline_store_for_alarm(_config.db_path),
        alarm_store=_alarm_store,
        send_email_fn=_alarm_send_email,
    )
    _alarm_scheduler = AlarmScheduler(_alarm_service)
    await _alarm_scheduler.start()

    _agent = create_agent(_config)
    _agent.session_store = _store
    _agent.approval_handler = make_api_approval_handler

    # Create shared LLM instance for direct use (e.g., evaluation)
    llm_kwargs: dict[str, Any] = {
        "model": _config.model_name,
        "temperature": 0.3,  # Lower temp for evaluation
    }
    if _config.openai_api_key:
        llm_kwargs["api_key"] = _config.openai_api_key
    if _config.openai_base_url:
        llm_kwargs["base_url"] = _config.openai_base_url
    _llm = ChatOpenAI(**llm_kwargs)


async def shutdown_dependencies() -> None:
    """Release all singletons (called during lifespan shutdown)."""
    global _llm
    global _agent, _store, _profile_store, _profile_service
    global _email_store, _email_service, _alarm_store, _alarm_service
    global _alarm_scheduler, _config
    if _alarm_scheduler:
        await _alarm_scheduler.stop()
        _alarm_scheduler = None
    if _alarm_store:
        await _alarm_store.close()
        _alarm_store = None
    _alarm_service = None
    if _store:
        await _store.close()
        _store = None
    if _profile_store:
        await _profile_store.close()
        _profile_store = None
    _profile_service = None
    if _email_store:
        await _email_store.close()
        _email_store = None
    _email_service = None
    _agent = None
    _config = None
    _llm = None
    # Reset provider-module singletons so tools don't point at closed stores
    from agent_core.persistence.email_provider import (
        set_email_service,
        set_email_store,
    )

    await set_email_store(None)
    await set_email_service(None)


def get_agent() -> ReactAgent:
    """FastAPI dependency that provides the current ReactAgent.

    Returns:
        The initialized ReactAgent.

    Raises:
        RuntimeError: If the agent has not been initialized.
    """
    if _agent is None:
        raise RuntimeError("Agent not initialized")
    return _agent


def get_agent_for_skill(skill_id: str | None, language: str = "en") -> ReactAgent:
    """Get an agent configured for a specific skill.

    If no skill_id is given (or it matches the default), returns the
    shared singleton. Otherwise creates a new agent with the skill's
    system prompt, sharing the session store and approval handler.

    Args:
        skill_id: Optional skill identifier.
        language: Language code for multi-language skills (default "en").

    Returns:
        A ReactAgent with the appropriate system prompt.
    """
    base = get_agent()
    if not skill_id:
        return base

    agent = create_agent(_config, skill_id=skill_id, language=language)
    agent.session_store = base.session_store
    agent.approval_handler = base.approval_handler
    return agent


def get_store() -> SessionStore:
    """FastAPI dependency that provides the SessionStore.

    Returns:
        The initialized SessionStore.

    Raises:
        RuntimeError: If the store has not been initialized.
    """
    if _store is None:
        raise RuntimeError("SessionStore not initialized")
    return _store


def get_llm() -> ChatOpenAI:
    """FastAPI dependency that provides a shared ChatOpenAI instance.

    Used for direct LLM calls outside the agent (e.g., quiz evaluation).

    Returns:
        A configured ChatOpenAI instance.

    Raises:
        RuntimeError: If dependencies have not been initialized.
    """
    if _llm is None:
        raise RuntimeError("LLM not initialized")
    return _llm


def get_profile_store() -> ProfileStore:
    """FastAPI dependency that provides the ProfileStore.

    Returns:
        The initialized ProfileStore.

    Raises:
        RuntimeError: If the store has not been initialized.
    """
    if _profile_store is None:
        raise RuntimeError("ProfileStore not initialized")
    return _profile_store


def get_profile_service() -> ProfileService:
    """FastAPI dependency that provides the ProfileService.

    Returns:
        The initialized ProfileService.

    Raises:
        RuntimeError: If the service has not been initialized.
    """
    if _profile_service is None:
        raise RuntimeError("ProfileService not initialized")
    return _profile_service


def get_email_service() -> EmailService:
    """FastAPI dependency that provides the EmailService.

    Returns:
        The initialized EmailService.

    Raises:
        RuntimeError: If the service has not been initialized.
    """
    if _email_service is None:
        raise RuntimeError("EmailService not initialized")
    return _email_service


def get_alarm_service() -> AlarmService:
    """FastAPI dependency that provides the AlarmService.

    Returns:
        The initialized AlarmService.

    Raises:
        RuntimeError: If the service has not been initialized.
    """
    if _alarm_service is None:
        raise RuntimeError("AlarmService not initialized")
    return _alarm_service


async def _init_deadline_store_for_alarm(db_path: str) -> DeadlineStore:
    """Create, initialize, and register the DeadlineStore singleton.

    Uses *db_path* (from the app config) so that tests using
    ``db_path=':memory:'`` share the same in-memory store across all
    routes and services — avoiding a mismatch between the deadline tool
    layer and the alarm service.
    """
    from pathlib import Path

    from agent_core.persistence.deadline_provider import set_deadline_store

    if db_path == ":memory:":
        deadline_db = ":memory:"
    else:
        deadline_db = str(Path(db_path).with_name("deadlines.db"))
    store = DeadlineStore(deadline_db)
    await store.initialize()
    await set_deadline_store(store)
    return store
