"""Mock weather tool — demonstrates HITL (sensitive tool) flow.

Provides a hardcoded weather query tool registered as SENSITIVE.
When the agent calls this tool, the HITL approval flow is triggered,
requiring explicit user confirmation before execution.
"""

from agent_core.tools.registry import ToolRegistry, ToolSensitivity

# Hardcoded weather data for demo
_WEATHER_DATA: dict[str, dict[str, str | int]] = {
    "beijing": {
        "city": "Beijing",
        "temperature": 28,
        "condition": "Sunny",
        "humidity": 45,
    },
    "shanghai": {
        "city": "Shanghai",
        "temperature": 32,
        "condition": "Cloudy",
        "humidity": 72,
    },
    "new york": {
        "city": "New York",
        "temperature": 22,
        "condition": "Partly Cloudy",
        "humidity": 58,
    },
    "london": {
        "city": "London",
        "temperature": 16,
        "condition": "Rainy",
        "humidity": 85,
    },
    "tokyo": {
        "city": "Tokyo",
        "temperature": 26,
        "condition": "Clear",
        "humidity": 60,
    },
}


def get_weather(city: str) -> str:
    """Query weather information for a city.

    This is a mock implementation with hardcoded data.
    In production, this would call a real weather API.

    Args:
        city: The city name to query weather for.

    Returns:
        Formatted weather information string.
    """
    key = city.strip().lower()
    data = _WEATHER_DATA.get(key)
    if data is None:
        return (
            f"Weather data not available for '{city}'. "
            f"Available cities: {', '.join(d['city'] for d in _WEATHER_DATA.values())}"
        )
    return (
        f"Weather for {data['city']}: "
        f"{data['condition']}, "
        f"Temperature: {data['temperature']}C, "
        f"Humidity: {data['humidity']}%"
    )


def register_weather_tools(registry: ToolRegistry) -> None:
    """Register weather tools into the given registry.

    The weather query tool is marked as SENSITIVE to demonstrate
    the HITL (Human-in-the-Loop) approval flow.

    Args:
        registry: The tool registry to register into.
    """
    registry.add_tool(
        func=get_weather,
        description=(
            "Query weather information for a specified city. "
            "Args: city (str) - the city name. "
            "This is a SENSITIVE tool that requires user approval."
        ),
        sensitivity=ToolSensitivity.SENSITIVE,
        name="get_weather",
    )
