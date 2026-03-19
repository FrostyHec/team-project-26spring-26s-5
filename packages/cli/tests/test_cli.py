"""Tests for the CLI module."""

from unittest.mock import patch

import pytest

from agent_cli.main import main


class TestCliMain:
    """Test CLI entry point."""

    def test_no_args_prints_help(self, capsys: pytest.CaptureFixture) -> None:
        """Test that running with no args prints help and exits."""
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["agent-cli"]):
                main()
        assert exc_info.value.code == 1

    def test_serve_command_parsed(self) -> None:
        """Test that serve command is recognized."""
        with patch("sys.argv", ["agent-cli", "serve"]):
            with patch("agent_cli.main.run_server") as mock_serve:
                main()
                mock_serve.assert_called_once_with(host="0.0.0.0", port=8000)

    def test_serve_with_custom_port(self) -> None:
        """Test serve with custom port."""
        with patch("sys.argv", ["agent-cli", "serve", "--port", "9000"]):
            with patch("agent_cli.main.run_server") as mock_serve:
                main()
                mock_serve.assert_called_once_with(host="0.0.0.0", port=9000)

    def test_chat_command_parsed(self) -> None:
        """Test that chat command triggers async loop."""
        with patch("sys.argv", ["agent-cli", "chat"]):
            with patch("asyncio.run") as mock_run:
                main()
                mock_run.assert_called_once()
