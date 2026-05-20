"""Dependency injection for FastAPI routes.

Provides the shared ReactAgent instance and SessionStore via
FastAPI's Depends system, analogous to Spring Boot's @Autowired.
"""

from dataclasses import replace
from typing import Any

from fastapi import HTTPException
from langchain_openai import ChatOpenAI

from agent_core.api.approval import make_api_approval_handler
from agent_core.config import AgentConfig, database_file, load_llm_settings
from agent_core.engine.agent import ReactAgent
from agent_core.logging_utils import get_logger
from agent_core.models.llm_settings import DEFAULT_MODEL_NAME
from agent_core.persistence.alarm_store import AlarmStore
from agent_core.persistence.conversation_tree_store import ConversationTreeStore
from agent_core.persistence.course_material_store import CourseMaterialStore
from agent_core.persistence.course_store import CourseStore
from agent_core.persistence.deadline_store import DeadlineStore
from agent_core.persistence.email_store import EmailStore
from agent_core.persistence.profile_store import ProfileStore
from agent_core.persistence.session_store import SessionStore
from agent_core.policy_search.config import PolicySearchConfig
from agent_core.policy_search.retriever import set_index_dir
from agent_core.security.encryption import reset_fernet
from agent_core.services.alarm_scheduler import AlarmScheduler
from agent_core.services.alarm_service import AlarmService
from agent_core.services.conversation_tree_service import ConversationTreeService
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
_conversation_tree_store: ConversationTreeStore | None = None
_conversation_tree_service: ConversationTreeService | None = None
_profile_store: ProfileStore | None = None
_profile_service: ProfileService | None = None
_email_store: EmailStore | None = None
_email_service: EmailService | None = None
_alarm_store: AlarmStore | None = None
_alarm_service: AlarmService | None = None
_alarm_scheduler: AlarmScheduler | None = None
_config: AgentConfig | None = None
_llm: ChatOpenAI | None = None
_course_store: CourseStore | None = None
_course_material_store: CourseMaterialStore | None = None


def _resolve_runtime_config(
    config: AgentConfig,
    provider_id: str | None = None,
) -> AgentConfig:
    """Resolve the concrete LLM runtime config for the requested provider."""
    llm_settings = load_llm_settings(config.llm_settings_path)
    provider = None
    normalized_provider_id = provider_id.strip() if provider_id else None

    if normalized_provider_id:
        selected_provider = llm_settings.provider_by_id(normalized_provider_id)
        if selected_provider is None:
            raise ValueError(f"Unknown provider_id: {provider_id}")
        if not selected_provider.enabled:
            raise ValueError(f"Provider is disabled: {provider_id}")
        provider = selected_provider
    elif llm_settings.providers:
        provider = llm_settings.default_provider()

    if provider is not None:
        if not provider.api_key.strip():
            raise ValueError(f"Provider '{provider.id}' is enabled but has no API key")
        return replace(
            config,
            openai_api_key=provider.api_key,
            openai_base_url=provider.base_url,
            model_name=provider.model or DEFAULT_MODEL_NAME,
            temperature=llm_settings.temperature,
            max_iterations=llm_settings.max_iterations,
            system_prompt=llm_settings.system_prompt,
        )

    if config.openai_api_key:
        return config

    raise ValueError("No enabled LLM provider configured")


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
    provider_id: str | None = None,
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
    resolved_config = _resolve_runtime_config(config, provider_id)

    llm_kwargs: dict[str, Any] = {
        "model": resolved_config.model_name,
        "temperature": resolved_config.temperature,
    }
    if resolved_config.openai_api_key:
        llm_kwargs["api_key"] = resolved_config.openai_api_key
    if resolved_config.openai_base_url:
        llm_kwargs["base_url"] = resolved_config.openai_base_url

    llm = ChatOpenAI(**llm_kwargs)
    registry = _create_tool_registry()

    # Use skill-specific system prompt if provided (with language support)
    system_prompt = (
        get_system_prompt_for_skill(skill_id, language) or resolved_config.system_prompt
    )

    return ReactAgent(
        llm=llm,
        tool_registry=registry,
        system_prompt=system_prompt,
    )


def _create_shared_llm(config: AgentConfig) -> ChatOpenAI:
    """Create the shared direct-call LLM instance on demand."""
    resolved_config = _resolve_runtime_config(config)
    llm_kwargs: dict[str, Any] = {
        "model": resolved_config.model_name,
        "temperature": 0.3,
    }
    if resolved_config.openai_api_key:
        llm_kwargs["api_key"] = resolved_config.openai_api_key
    if resolved_config.openai_base_url:
        llm_kwargs["base_url"] = resolved_config.openai_base_url
    return ChatOpenAI(**llm_kwargs)


async def init_dependencies(config: AgentConfig | None = None) -> None:
    """Initialize all singletons (called during lifespan startup).

    Args:
        config: Optional configuration.
    """
    global _llm
    global _agent, _store, _conversation_tree_store, _conversation_tree_service
    global _profile_store, _profile_service
    global _email_store, _email_service, _alarm_store, _alarm_service
    global _alarm_scheduler, _config, _course_store, _course_material_store
    _config = config or AgentConfig.from_env()
    set_index_dir(PolicySearchConfig.from_env().index_dir)

    # Configure encryption key if provided
    if _config.encryption_key:
        reset_fernet(_config.encryption_key)

    _store = SessionStore(database_file(_config.db_path, "sessions.db"))
    await _store.initialize()
    _conversation_tree_store = ConversationTreeStore(
        database_file(_config.db_path, "sessions.db"),
        engine=_store.db,
    )
    await _conversation_tree_store.initialize()
    _conversation_tree_service = ConversationTreeService(
        _store,
        _conversation_tree_store,
    )

    # Course subsystem
    course_db = database_file(_config.db_path, "courses.db")
    _course_store = CourseStore(course_db)
    await _course_store.initialize()

    material_db = database_file(_config.db_path, "course_materials.db")
    _course_material_store = CourseMaterialStore(
        material_db,
        max_size_bytes=_config.course_material_max_size_mb * 1024 * 1024,
        allowed_extensions=frozenset(
            ext.strip().lower()
            for ext in _config.course_material_allowed_extensions.split(",")
            if ext.strip()
        ),
    )
    await _course_material_store.initialize()

    # Register course store singletons
    from agent_core.persistence.course_material_provider import (
        set_course_material_store,
    )
    from agent_core.persistence.course_provider import set_course_store

    await set_course_store(_course_store)
    await set_course_material_store(_course_material_store)

    _profile_store = ProfileStore(database_file(_config.db_path, "sessions.db"))
    await _profile_store.initialize()
    _profile_service = ProfileService(_profile_store)

    # Email subsystem
    import tempfile

    if _config.db_path == ":memory:":
        email_db = ":memory:"
        data_root = tempfile.mkdtemp()
    else:
        email_db = database_file(_config.db_path, "email.db")
        data_root = _config.db_path
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
    _alarm_store = AlarmStore(database_file(_config.db_path, "sessions.db"))
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

    # Delay LLM-dependent construction until a chat/evaluate request needs it.
    _agent = None
    _llm = None


async def shutdown_dependencies() -> None:
    """Release all singletons (called during lifespan shutdown)."""
    global _llm
    global _agent, _store, _conversation_tree_store, _conversation_tree_service
    global _profile_store, _profile_service
    global _email_store, _email_service, _alarm_store, _alarm_service
    global _alarm_scheduler, _config, _course_store, _course_material_store
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
    if _conversation_tree_store:
        await _conversation_tree_store.close()
        _conversation_tree_store = None
    _conversation_tree_service = None
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
    from agent_core.persistence.agent_memory_provider import (
        set_agent_memory_service,
        set_agent_memory_store,
    )

    await set_agent_memory_store(None)
    await set_agent_memory_service(None)
    from agent_core.persistence.course_material_provider import (
        set_course_material_store,
    )
    from agent_core.persistence.course_provider import set_course_store

    await set_course_store(None)
    await set_course_material_store(None)
    if _course_material_store:
        await _course_material_store.close()
        _course_material_store = None
    if _course_store:
        await _course_store.close()
        _course_store = None


def get_agent() -> ReactAgent:
    """FastAPI dependency that provides the current ReactAgent.

    Returns:
        The initialized ReactAgent.

    Raises:
        RuntimeError: If the agent has not been initialized.
    """
    global _agent
    if _agent is None:
        if _config is None or _store is None:
            raise RuntimeError("Agent dependencies not initialized")
        try:
            _agent = create_agent(_config)
        except ValueError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        _agent.session_store = _store
        _agent.approval_handler = make_api_approval_handler
    return _agent


def get_agent_for_skill(
    skill_id: str | None,
    language: str = "en",
    provider_id: str | None = None,
) -> ReactAgent:
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
    if not skill_id and not provider_id:
        return base

    agent = create_agent(
        _config,
        skill_id=skill_id,
        language=language,
        provider_id=provider_id,
    )
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


def get_conversation_tree_service() -> ConversationTreeService:
    """FastAPI dependency that provides the ConversationTreeService."""
    if _conversation_tree_service is None:
        raise RuntimeError("ConversationTreeService not initialized")
    return _conversation_tree_service


def get_conversation_tree_store() -> ConversationTreeStore:
    """FastAPI dependency that provides the ConversationTreeStore."""
    if _conversation_tree_store is None:
        raise RuntimeError("ConversationTreeStore not initialized")
    return _conversation_tree_store


def get_llm() -> ChatOpenAI:
    """FastAPI dependency that provides a shared ChatOpenAI instance.

    Used for direct LLM calls outside the agent (e.g., quiz evaluation).

    Returns:
        A configured ChatOpenAI instance.

    Raises:
        RuntimeError: If dependencies have not been initialized.
    """
    global _llm
    if _llm is None:
        if _config is None:
            raise RuntimeError("LLM dependencies not initialized")
        try:
            _llm = _create_shared_llm(_config)
        except ValueError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _llm


def get_config() -> AgentConfig:
    """FastAPI dependency that provides the current AgentConfig."""
    if _config is None:
        raise RuntimeError("Config not initialized")
    return _config


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
    from agent_core.persistence.deadline_provider import set_deadline_store

    deadline_db = database_file(db_path, "deadlines.db")
    store = DeadlineStore(deadline_db)
    await store.initialize()
    await set_deadline_store(store)
    return store
