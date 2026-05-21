"""Tests for AgentConfig configuration management."""

import os
from pathlib import Path
from unittest.mock import patch

from agent_core.config import AgentConfig, database_file


class TestAgentConfig:
    """Test suite for AgentConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = AgentConfig()
        assert config.openai_api_key == ""
        assert config.model_name == "gpt-4o-mini"
        assert config.temperature == 0.0
        assert config.max_iterations == 10

    def test_custom_values(self) -> None:
        """Test creating config with custom values."""
        config = AgentConfig(
            openai_api_key="test-key",
            model_name="gpt-4o",
            temperature=0.7,
        )
        assert config.openai_api_key == "test-key"
        assert config.model_name == "gpt-4o"
        assert config.temperature == 0.7

    def test_from_env_reads_llm_yaml(self, tmp_path: Path) -> None:
        """LLM runtime settings should come from YAML, not legacy env keys."""
        llm_settings_path = tmp_path / "llm_settings.yaml"
        llm_settings_path.write_text(
            """
temperature: 0.5
max_iterations: 5
system_prompt: YAML prompt
providers:
  - id: primary
    name: Primary
    priority: 0
    base_url: https://example.test/v1
    api_key: yaml-key
    model: yaml-model
    enabled: true
""".strip(),
            encoding="utf-8",
        )
        env_vars = {
            "OPENAI_API_KEY": "env-key-should-be-ignored",
            "MODEL_NAME": "env-model-should-be-ignored",
            "TEMPERATURE": "0.9",
            "MAX_ITERATIONS": "99",
            "LLM_SETTINGS_PATH": str(llm_settings_path),
        }
        with patch.dict(os.environ, env_vars, clear=False):
            with patch("agent_core.config.load_dotenv"):
                config = AgentConfig.from_env()
        assert config.openai_api_key == "yaml-key"
        assert config.openai_base_url == "https://example.test/v1"
        assert config.model_name == "yaml-model"
        assert config.temperature == 0.5
        assert config.max_iterations == 5
        assert config.system_prompt == "YAML prompt"

    def test_from_env_defaults_without_llm_yaml(self, tmp_path: Path) -> None:
        """Missing YAML should use safe default LLM settings."""
        env_vars = {"LLM_SETTINGS_PATH": str(tmp_path / "missing_llm_settings.yaml")}
        with patch.dict(os.environ, env_vars, clear=False):
            for key in [
                "OPENAI_API_KEY",
                "MODEL_NAME",
                "TEMPERATURE",
                "MAX_ITERATIONS",
                "LLM_SETTINGS_PATH",
                "DATA_PATH",
                "DB_PATH",
                "LOG_FILE",
                "APP_HOST",
                "APP_PORT",
            ]:
                os.environ.pop(key, None)
            with patch("agent_core.config.load_dotenv"):
                config = AgentConfig.from_env()
        assert config.openai_api_key == ""
        assert config.model_name == "gpt-4o-mini"
        assert config.temperature == 0.0
        assert config.max_iterations == 10
        assert config.data_path == "output"
        assert config.db_path == "output"
        assert config.log_file == str(Path("output") / "logs" / "agent.log")
        assert config.llm_settings_path == str(Path("output") / "llm_settings.yaml")
        assert config.app_host == "127.0.0.1"
        assert config.app_port == 8000

    def test_from_env_derives_paths_from_data_path(self, tmp_path: Path) -> None:
        """Path defaults should derive from DATA_PATH when unset."""
        data_path = tmp_path / "runtime-data"
        env_vars = {
            "DATA_PATH": str(data_path),
            "DB_PATH": "",
            "LOG_FILE": "",
            "LLM_SETTINGS_PATH": "",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            with patch("agent_core.config.load_dotenv"):
                config = AgentConfig.from_env()

        assert config.data_path == str(data_path)
        assert config.db_path == str(data_path)
        assert config.log_file == str(data_path / "logs" / "agent.log")
        assert config.llm_settings_path == str(data_path / "llm_settings.yaml")

    def test_from_env_resolves_relative_paths_from_env_file(
        self, tmp_path: Path
    ) -> None:
        """Relative paths in an explicit env file should use that file's parent."""
        env_file = tmp_path / "config" / ".env"
        env_file.parent.mkdir()
        env_file.write_text(
            "\n".join(
                [
                    "DATA_PATH=runtime",
                    "DB_PATH=",
                    "LOG_FILE=",
                    "LLM_SETTINGS_PATH=",
                    "APP_HOST=127.0.0.2",
                    "APP_PORT=9010",
                ]
            ),
            encoding="utf-8",
        )

        with patch.dict(os.environ, {}, clear=False):
            config = AgentConfig.from_env(env_file)
        data_path = env_file.parent / "runtime"

        assert config.data_path == str(data_path)
        assert config.db_path == str(data_path)
        assert config.log_file == str(data_path / "logs" / "agent.log")
        assert config.llm_settings_path == str(data_path / "llm_settings.yaml")
        assert config.app_host == "127.0.0.2"
        assert config.app_port == 9010

    def test_explicit_env_file_overrides_ambient_path_variables(
        self, tmp_path: Path
    ) -> None:
        """Packaged env files should win over inherited shell path variables."""
        env_file = tmp_path / "config" / ".env"
        env_file.parent.mkdir()
        env_file.write_text(
            "\n".join(
                [
                    "DATA_PATH=../output",
                    "DB_PATH=",
                    "LOG_FILE=",
                    "LLM_SETTINGS_PATH=",
                    "APP_PORT=8123",
                ]
            ),
            encoding="utf-8",
        )
        ambient_data = tmp_path / "ambient-data"
        ambient_db = tmp_path / "ambient-db"

        with patch.dict(
            os.environ,
            {
                "DATA_PATH": str(ambient_data),
                "DB_PATH": str(ambient_db),
                "LOG_FILE": str(tmp_path / "ambient.log"),
                "LLM_SETTINGS_PATH": str(tmp_path / "ambient.yaml"),
                "APP_PORT": "9000",
            },
            clear=False,
        ):
            config = AgentConfig.from_env(env_file)

        data_path = env_file.parent / ".." / "output"
        assert config.data_path == str(data_path)
        assert config.db_path == str(data_path)
        assert config.log_file == str(data_path / "logs" / "agent.log")
        assert config.llm_settings_path == str(data_path / "llm_settings.yaml")
        assert config.app_port == 8123

    def test_database_file_uses_db_directory(self, tmp_path: Path) -> None:
        """Database filenames should be fixed under the configured DB directory."""
        db_dir = tmp_path / "db"

        assert database_file(db_dir, "sessions.db") == str(db_dir / "sessions.db")
        assert database_file(":memory:", "sessions.db") == ":memory:"
