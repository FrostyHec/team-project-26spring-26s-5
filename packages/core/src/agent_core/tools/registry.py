"""Tool Registry - Central registration and execution of agent tools.

Provides a decorator-based tool registration system with:
- Type-safe tool definitions via Pydantic
- Sensitivity levels for HITL control
- Async execution support
"""

import asyncio
import inspect
from collections.abc import Callable
from enum import StrEnum
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel


class ToolSensitivity(StrEnum):
    """Sensitivity level for tool operations.

    Determines whether human approval is needed before execution.
    """

    SAFE = "safe"
    SENSITIVE = "sensitive"


class ToolDefinition(BaseModel):
    """Metadata for a registered tool.

    Attributes:
        name: Unique tool identifier.
        description: Human-readable description for the LLM.
        func: The callable implementing the tool.
        sensitivity: Whether this tool requires HITL approval.
    """

    name: str
    description: str
    func: Callable[..., Any]
    sensitivity: ToolSensitivity

    model_config = {"arbitrary_types_allowed": True}


class ToolRegistry:
    """Central registry for agent tools.

    Manages tool registration, lookup, and execution. Supports
    both decorator-based and programmatic registration.

    Example:
        registry = ToolRegistry()

        @registry.register(description="Add two numbers")
        def add(a: float, b: float) -> float:
            return a + b

        result = await registry.execute("add", {"a": 1, "b": 2})
    """

    def __init__(self) -> None:
        """Initialize an empty tool registry."""
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        description: str,
        sensitivity: ToolSensitivity = ToolSensitivity.SAFE,
        name: str | None = None,
    ) -> Callable:
        """Decorator to register a function as an agent tool.

        Args:
            description: Description for the LLM to understand the tool.
            sensitivity: HITL sensitivity level.
            name: Optional custom name (defaults to function name).

        Returns:
            The original function, unchanged.
        """

        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__
            tool_def = ToolDefinition(
                name=tool_name,
                description=description,
                func=func,
                sensitivity=sensitivity,
            )
            self._tools[tool_name] = tool_def
            return func

        return decorator

    def add_tool(
        self,
        func: Callable,
        description: str,
        sensitivity: ToolSensitivity = ToolSensitivity.SAFE,
        name: str | None = None,
    ) -> None:
        """Programmatically register a tool.

        Args:
            func: The tool function.
            description: Description for the LLM.
            sensitivity: HITL sensitivity level.
            name: Optional custom name.
        """
        tool_name = name or func.__name__
        tool_def = ToolDefinition(
            name=tool_name,
            description=description,
            func=func,
            sensitivity=sensitivity,
        )
        self._tools[tool_name] = tool_def

    def get(self, name: str) -> ToolDefinition | None:
        """Look up a tool by name.

        Args:
            name: The tool name.

        Returns:
            ToolDefinition if found, None otherwise.
        """
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        """List all registered tools.

        Returns:
            List of all tool definitions.
        """
        return list(self._tools.values())

    async def execute(self, name: str, args: dict[str, Any]) -> Any:
        """Execute a registered tool by name.

        Args:
            name: The tool name.
            args: Keyword arguments for the tool function.

        Returns:
            The tool's return value.

        Raises:
            KeyError: If tool is not registered.
        """
        tool_def = self._tools.get(name)
        if tool_def is None:
            raise KeyError(f"Tool '{name}' is not registered")

        func = tool_def.func
        if inspect.iscoroutinefunction(func):
            return await func(**args)
        else:
            # Run sync functions in executor to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: func(**args))

    def is_sensitive(self, name: str) -> bool:
        """Check if a tool requires human approval.

        Args:
            name: The tool name.

        Returns:
            True if the tool is sensitive.
        """
        tool_def = self._tools.get(name)
        if tool_def is None:
            return False
        return tool_def.sensitivity == ToolSensitivity.SENSITIVE

    def get_langchain_tools(self) -> list[StructuredTool]:
        """Convert registered tools to LangChain StructuredTool format.

        Returns:
            List of LangChain-compatible tool objects.
        """
        lc_tools = []
        for tool_def in self._tools.values():
            lc_tool = StructuredTool.from_function(
                func=tool_def.func,
                name=tool_def.name,
                description=tool_def.description,
            )
            lc_tools.append(lc_tool)
        return lc_tools


def tool(
    description: str,
    sensitivity: ToolSensitivity = ToolSensitivity.SAFE,
    name: str | None = None,
) -> Callable:
    """Standalone decorator to mark a function as a tool.

    The decorated function gets a `_tool_meta` attribute for later
    collection by a ToolRegistry.

    Args:
        description: Tool description for the LLM.
        sensitivity: HITL sensitivity level.
        name: Optional custom name.

    Returns:
        Decorator function.
    """

    def decorator(func: Callable) -> Callable:
        func._tool_meta = {  # type: ignore[attr-defined]
            "description": description,
            "sensitivity": sensitivity,
            "name": name or func.__name__,
        }
        return func

    return decorator
