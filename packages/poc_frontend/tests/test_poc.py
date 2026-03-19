"""Tests for POC frontend (Chainlit app module)."""

from agent_core.tools.calculator import register_calculator_tools
from agent_core.tools.registry import ToolRegistry


class TestPocFrontendImports:
    """Test that POC frontend modules can be imported."""

    def test_import_app_module(self) -> None:
        """Test that the app module can be imported."""
        # This verifies the module structure is correct
        import poc_frontend

        assert poc_frontend is not None

    def test_agent_creation_tools(self) -> None:
        """Test that calculator tools register correctly for the frontend."""
        registry = ToolRegistry()
        register_calculator_tools(registry)
        tools = registry.list_tools()
        assert len(tools) == 4
        names = {t.name for t in tools}
        assert "add" in names
