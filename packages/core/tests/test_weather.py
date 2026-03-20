"""Tests for weather tools."""

import pytest

from agent_core.tools.registry import ToolRegistry, ToolSensitivity
from agent_core.tools.weather import register_weather_tools


class TestWeatherTools:
    """Test suite for weather tools."""

    def setup_method(self) -> None:
        """Register weather tools for each test."""
        self.registry = ToolRegistry()
        register_weather_tools(self.registry)

    def test_tool_registered(self) -> None:
        """Test that the weather tool is registered."""
        tools = self.registry.list_tools()
        names = {t.name for t in tools}
        assert "get_weather" in names

    def test_tool_is_sensitive(self) -> None:
        """Test that the weather tool is marked SENSITIVE."""
        assert self.registry.is_sensitive("get_weather")
        tool_def = next(
            t for t in self.registry.list_tools() if t.name == "get_weather"
        )
        assert tool_def.sensitivity == ToolSensitivity.SENSITIVE

    @pytest.mark.asyncio
    async def test_get_weather_known_city(self) -> None:
        """Test weather for a known city returns expected data."""
        result = await self.registry.execute("get_weather", {"city": "Beijing"})
        assert "beijing" in result.lower() or "Beijing" in result
        assert "temperature" in result.lower()

    @pytest.mark.asyncio
    async def test_get_weather_case_insensitive(self) -> None:
        """Test weather lookup is case-insensitive."""
        result_lower = await self.registry.execute("get_weather", {"city": "london"})
        result_upper = await self.registry.execute("get_weather", {"city": "LONDON"})
        assert result_lower == result_upper

    @pytest.mark.asyncio
    async def test_get_weather_unknown_city(self) -> None:
        """Test weather for an unknown city returns error message."""
        result = await self.registry.execute("get_weather", {"city": "Atlantis"})
        assert "not available" in result.lower()

    @pytest.mark.asyncio
    async def test_get_weather_all_known_cities(self) -> None:
        """Test all five known cities return valid weather."""
        cities = ["Beijing", "Shanghai", "New York", "London", "Tokyo"]
        for city in cities:
            result = await self.registry.execute("get_weather", {"city": city})
            # Should contain weather info, not an error
            assert "not available" not in result.lower()
            assert len(result) > 10  # Some non-trivial output

    def test_tool_has_description(self) -> None:
        """Test the weather tool has a meaningful description."""
        tool_def = next(
            t for t in self.registry.list_tools() if t.name == "get_weather"
        )
        assert len(tool_def.description) > 10
        assert "weather" in tool_def.description.lower()
