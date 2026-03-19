"""Calculator tools - POC demonstration tools for the ReAct agent.

Provides basic arithmetic operations as agent tools to demonstrate
the tool calling mechanism.
"""

from agent_core.tools.registry import ToolRegistry, ToolSensitivity


def register_calculator_tools(registry: ToolRegistry) -> None:
    """Register all calculator tools with the given registry.

    Args:
        registry: The tool registry to register tools with.
    """

    @registry.register(
        description="Add two numbers together. Args: a (float), b (float)."
    )
    def add(a: float, b: float) -> float:
        """Add two numbers."""
        return a + b

    @registry.register(description="Subtract b from a. Args: a (float), b (float).")
    def subtract(a: float, b: float) -> float:
        """Subtract b from a."""
        return a - b

    @registry.register(description="Multiply two numbers. Args: a (float), b (float).")
    def multiply(a: float, b: float) -> float:
        """Multiply two numbers."""
        return a * b

    @registry.register(
        description="Divide a by b. Args: a (float), b (float). "
        "Returns error if b is zero.",
        sensitivity=ToolSensitivity.SAFE,
    )
    def divide(a: float, b: float) -> float | str:
        """Divide a by b, with zero-division protection."""
        if b == 0:
            return "Error: Division by zero"
        return a / b
