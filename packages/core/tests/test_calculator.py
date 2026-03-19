"""Tests for calculator tools."""

import pytest

from agent_core.tools.calculator import register_calculator_tools
from agent_core.tools.registry import ToolRegistry


class TestCalculatorTools:
    """Test suite for calculator tools."""

    def setup_method(self) -> None:
        """Register calculator tools for each test."""
        self.registry = ToolRegistry()
        register_calculator_tools(self.registry)

    def test_all_tools_registered(self) -> None:
        """Test that all 4 calculator tools are registered."""
        tools = self.registry.list_tools()
        names = {t.name for t in tools}
        assert names == {"add", "subtract", "multiply", "divide"}

    @pytest.mark.asyncio
    async def test_add(self) -> None:
        """Test addition tool."""
        result = await self.registry.execute("add", {"a": 2.0, "b": 3.0})
        assert result == 5.0

    @pytest.mark.asyncio
    async def test_add_negative(self) -> None:
        """Test addition with negative numbers."""
        result = await self.registry.execute("add", {"a": -5.0, "b": 3.0})
        assert result == -2.0

    @pytest.mark.asyncio
    async def test_subtract(self) -> None:
        """Test subtraction tool."""
        result = await self.registry.execute("subtract", {"a": 10.0, "b": 3.0})
        assert result == 7.0

    @pytest.mark.asyncio
    async def test_multiply(self) -> None:
        """Test multiplication tool."""
        result = await self.registry.execute("multiply", {"a": 4.0, "b": 5.0})
        assert result == 20.0

    @pytest.mark.asyncio
    async def test_multiply_by_zero(self) -> None:
        """Test multiplication by zero."""
        result = await self.registry.execute("multiply", {"a": 100.0, "b": 0.0})
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_divide(self) -> None:
        """Test division tool."""
        result = await self.registry.execute("divide", {"a": 10.0, "b": 2.0})
        assert result == 5.0

    @pytest.mark.asyncio
    async def test_divide_by_zero(self) -> None:
        """Test division by zero returns error string."""
        result = await self.registry.execute("divide", {"a": 10.0, "b": 0.0})
        assert isinstance(result, str)
        assert "zero" in result.lower()

    @pytest.mark.asyncio
    async def test_divide_fractional(self) -> None:
        """Test division with fractional result."""
        result = await self.registry.execute("divide", {"a": 7.0, "b": 2.0})
        assert result == 3.5
