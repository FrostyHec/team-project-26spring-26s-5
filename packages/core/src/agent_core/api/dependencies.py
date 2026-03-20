"""Dependency injection for FastAPI routes.

Provides the shared ReactAgent instance via FastAPI's Depends system,
analogous to Spring Boot's @Autowired / service injection.
"""

from typing import Any

from langchain_openai import ChatOpenAI

from agent_core.config import AgentConfig
from agent_core.engine.agent import ReactAgent
from agent_core.tools.calculator import register_calculator_tools
from agent_core.tools.registry import ToolRegistry

# Module-level agent instance (initialized during app lifespan)
_agent: ReactAgent | None = None


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

    return ReactAgent(
        llm=llm,
        tool_registry=registry,
        system_prompt=config.system_prompt,
    )


def init_agent(config: AgentConfig | None = None) -> None:
    """Initialize the global agent instance (called during lifespan).

    Args:
        config: Optional configuration.
    """
    global _agent
    _agent = create_agent(config)


def shutdown_agent() -> None:
    """Release the global agent instance (called during lifespan)."""
    global _agent
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
