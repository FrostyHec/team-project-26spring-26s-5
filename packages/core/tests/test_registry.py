"""Tests for the ToolRegistry and tool registration system."""

import pytest

from agent_core.tools.registry import (
    ToolDefinition,
    ToolRegistry,
    ToolSensitivity,
    tool,
)


class TestToolRegistry:
    """Test suite for ToolRegistry."""

    def setup_method(self) -> None:
        """Create a fresh registry for each test."""
        self.registry = ToolRegistry()

    def test_register_decorator(self) -> None:
        """Test registering a tool via decorator."""

        @self.registry.register(description="Add two numbers")
        def add(a: float, b: float) -> float:
            return a + b

        assert self.registry.get("add") is not None
        assert self.registry.get("add").description == "Add two numbers"  # type: ignore[union-attr]

    def test_register_with_custom_name(self) -> None:
        """Test registering with a custom tool name."""

        @self.registry.register(description="Sum", name="custom_add")
        def add(a: float, b: float) -> float:
            return a + b

        assert self.registry.get("custom_add") is not None
        assert self.registry.get("add") is None

    def test_register_with_sensitivity(self) -> None:
        """Test registering a sensitive tool."""

        @self.registry.register(
            description="Delete file",
            sensitivity=ToolSensitivity.SENSITIVE,
        )
        def delete_file(path: str) -> str:
            return f"deleted {path}"

        assert self.registry.is_sensitive("delete_file")

    def test_add_tool_programmatic(self) -> None:
        """Test programmatic tool registration."""

        def multiply(a: float, b: float) -> float:
            return a * b

        self.registry.add_tool(multiply, description="Multiply two numbers")
        assert self.registry.get("multiply") is not None

    def test_list_tools(self) -> None:
        """Test listing all registered tools."""

        @self.registry.register(description="Tool A")
        def tool_a() -> str:
            return "a"

        @self.registry.register(description="Tool B")
        def tool_b() -> str:
            return "b"

        tools = self.registry.list_tools()
        assert len(tools) == 2
        names = {t.name for t in tools}
        assert names == {"tool_a", "tool_b"}

    @pytest.mark.asyncio
    async def test_execute_sync_tool(self) -> None:
        """Test executing a synchronous tool."""

        @self.registry.register(description="Add")
        def add(a: float, b: float) -> float:
            return a + b

        result = await self.registry.execute("add", {"a": 3.0, "b": 4.0})
        assert result == 7.0

    @pytest.mark.asyncio
    async def test_execute_async_tool(self) -> None:
        """Test executing an async tool."""

        @self.registry.register(description="Async add")
        async def async_add(a: float, b: float) -> float:
            return a + b

        result = await self.registry.execute("async_add", {"a": 1.0, "b": 2.0})
        assert result == 3.0

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self) -> None:
        """Test executing a tool that doesn't exist raises KeyError."""
        with pytest.raises(KeyError, match="not_real"):
            await self.registry.execute("not_real", {})

    def test_is_sensitive_safe_tool(self) -> None:
        """Test that safe tools are not sensitive."""

        @self.registry.register(description="Safe tool")
        def safe() -> str:
            return "safe"

        assert not self.registry.is_sensitive("safe")

    def test_is_sensitive_nonexistent(self) -> None:
        """Test is_sensitive for non-existent tool returns False."""
        assert not self.registry.is_sensitive("nonexistent")

    def test_get_langchain_tools(self) -> None:
        """Test converting tools to LangChain format."""

        @self.registry.register(description="Add two numbers")
        def add(a: float, b: float) -> float:
            return a + b

        lc_tools = self.registry.get_langchain_tools()
        assert len(lc_tools) == 1
        assert lc_tools[0].name == "add"


class TestToolDecorator:
    """Test the standalone @tool decorator."""

    def test_tool_decorator_adds_metadata(self) -> None:
        """Test that @tool adds _tool_meta attribute."""

        @tool(description="Test tool")
        def my_tool() -> str:
            return "result"

        assert hasattr(my_tool, "_tool_meta")
        assert my_tool._tool_meta["description"] == "Test tool"
        assert my_tool._tool_meta["name"] == "my_tool"
        assert my_tool._tool_meta["sensitivity"] == ToolSensitivity.SAFE

    def test_tool_decorator_preserves_function(self) -> None:
        """Test that decorated function still works normally."""

        @tool(description="Add")
        def add(a: int, b: int) -> int:
            return a + b

        assert add(1, 2) == 3


class TestToolDefinition:
    """Test ToolDefinition model."""

    def test_create_tool_definition(self) -> None:
        """Test creating a ToolDefinition."""

        def dummy() -> str:
            return "dummy"

        td = ToolDefinition(
            name="test",
            description="A test tool",
            func=dummy,
            sensitivity=ToolSensitivity.SAFE,
        )
        assert td.name == "test"
        assert td.sensitivity == ToolSensitivity.SAFE
