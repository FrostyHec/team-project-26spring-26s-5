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
from agent_core.tools.calculator import register_calculator_tools
from agent_core.tools.registry import ToolRegistry
from agent_core.tools.weather import register_weather_tools

# Module-level singletons (initialized during app lifespan)
_agent: ReactAgent | None = None
_store: SessionStore | None = None


def create_agent(config: AgentConfig | None = None) -> ReactAgent:
    """Create and configure a ReactAgent instance.

    Args:
        config: Optional configuration. Uses env if not provided.

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

    registry = ToolRegistry()
    register_calculator_tools(registry)
    register_weather_tools(registry)

    return ReactAgent(
        llm=llm,
        tool_registry=registry,
        system_prompt=config.system_prompt,
    )


async def init_dependencies(config: AgentConfig | None = None) -> None:
    """Initialize all singletons (called during lifespan startup).

    Args:
        config: Optional configuration.
    """
    global _agent, _store
    resolved = config or AgentConfig.from_env()

    _store = SessionStore(resolved.db_path)
    await _store.initialize()

    _agent = create_agent(config)
    _agent.session_store = _store
    _agent.approval_handler = make_api_approval_handler


async def shutdown_dependencies() -> None:
    """Release all singletons (called during lifespan shutdown)."""
    global _agent, _store
    if _store:
        await _store.close()
        _store = None
    _agent = None


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
