"""Dependency injection for FastAPI routes.

Provides the shared ReactAgent instance and SessionStore via
FastAPI's Depends system, analogous to Spring Boot's @Autowired.
"""

from typing import Any

from langchain_openai import ChatOpenAI

from agent_core.api.approval import make_api_approval_handler
from agent_core.config import AgentConfig
from agent_core.engine.agent import ReactAgent
from agent_core.persistence.session_store import SessionStore
from agent_core.skills import get_system_prompt_for_skill
from agent_core.tools import auto_discover_and_register
from agent_core.tools.registry import ToolRegistry

# Module-level singletons (initialized during app lifespan)
_agent: ReactAgent | None = None
_store: SessionStore | None = None
_config: AgentConfig | None = None


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
) -> ReactAgent:
    """Create and configure a ReactAgent instance.

    Args:
        config: Optional configuration. Uses env if not provided.
        skill_id: Optional skill ID for system prompt override.

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

    # Use skill-specific system prompt if provided
    system_prompt = get_system_prompt_for_skill(skill_id) or config.system_prompt

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
    global _agent, _store, _config
    _config = config or AgentConfig.from_env()

    _store = SessionStore(_config.db_path)
    await _store.initialize()

    _agent = create_agent(_config)
    _agent.session_store = _store
    _agent.approval_handler = make_api_approval_handler


async def shutdown_dependencies() -> None:
    """Release all singletons (called during lifespan shutdown)."""
    global _agent, _store, _config
    if _store:
        await _store.close()
        _store = None
    _agent = None
    _config = None


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


def get_agent_for_skill(skill_id: str | None) -> ReactAgent:
    """Get an agent configured for a specific skill.

    If no skill_id is given (or it matches the default), returns the
    shared singleton. Otherwise creates a new agent with the skill's
    system prompt, sharing the session store and approval handler.

    Args:
        skill_id: Optional skill identifier.

    Returns:
        A ReactAgent with the appropriate system prompt.
    """
    base = get_agent()
    if not skill_id:
        return base

    agent = create_agent(_config, skill_id=skill_id)
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
