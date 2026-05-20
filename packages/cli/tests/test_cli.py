"""Tests for the CLI module."""

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest
from agent_core.runtime_paths import ENV_FILE_ENV_KEY

from agent_cli.main import main


@pytest.fixture(autouse=True)
def clear_runtime_env_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep CLI tests isolated from explicit env-file state."""
    monkeypatch.delenv(ENV_FILE_ENV_KEY, raising=False)
    monkeypatch.delenv("APP_HOST", raising=False)
    monkeypatch.delenv("APP_PORT", raising=False)


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
                mock_serve.assert_called_once_with(
                    host="127.0.0.1",
                    port=8000,
                    env_file=None,
                    static_dir=None,
                )

    def test_serve_with_custom_port(self) -> None:
        """Test serve with custom port."""
        with patch("sys.argv", ["agent-cli", "serve", "--port", "9000"]):
            with patch("agent_cli.main.run_server") as mock_serve:
                main()
                mock_serve.assert_called_once_with(
                    host="127.0.0.1",
                    port=9000,
                    env_file=None,
                    static_dir=None,
                )

    def test_serve_uses_env_file_defaults(self, tmp_path: Path) -> None:
        """Test serve can read host and port from an explicit env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("APP_HOST=127.0.0.2\nAPP_PORT=9010\n", encoding="utf-8")
        with patch("sys.argv", ["agent-cli", "serve", "--env-file", str(env_file)]):
            with patch("agent_cli.main.run_server") as mock_serve:
                main()
                mock_serve.assert_called_once_with(
                    host="127.0.0.2",
                    port=9010,
                    env_file=str(env_file),
                    static_dir=None,
                )

    def test_serve_accepts_static_dir(self, tmp_path: Path) -> None:
        """Test serve accepts a static directory for packaged mode."""
        static_dir = tmp_path / "dist"
        with patch(
            "sys.argv",
            ["agent-cli", "serve", "--static-dir", str(static_dir)],
        ):
            with patch("agent_cli.main.run_server") as mock_serve:
                main()
                mock_serve.assert_called_once_with(
                    host="127.0.0.1",
                    port=8000,
                    env_file=None,
                    static_dir=str(static_dir),
                )

    def test_chat_command_parsed(self) -> None:
        """Test that chat command triggers async loop."""
        with patch("sys.argv", ["agent-cli", "chat"]):
            with patch("asyncio.run") as mock_run:
                main()
                mock_run.assert_called_once()
                chat_loop_coro = mock_run.call_args.args[0]
                assert asyncio.iscoroutine(chat_loop_coro)
                chat_loop_coro.close()

    def test_build_policy_index_command_parsed(self) -> None:
        """Test build-policy-index command."""
        with patch("sys.argv", ["agent-cli", "build-policy-index"]):
            with patch("agent_cli.main.build_policy_index") as mock_build:
                main()
                mock_build.assert_called_once_with(env_file=None)

    def test_build_policy_index_accepts_env_file(self, tmp_path: Path) -> None:
        """Test build-policy-index accepts an explicit env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("DATA_PATH=runtime\n", encoding="utf-8")
        with patch(
            "sys.argv",
            ["agent-cli", "build-policy-index", "--env-file", str(env_file)],
        ):
            with patch("agent_cli.main.build_policy_index") as mock_build:
                main()
                mock_build.assert_called_once_with(env_file=str(env_file))
