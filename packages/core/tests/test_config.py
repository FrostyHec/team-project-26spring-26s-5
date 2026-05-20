"""Tests for AgentConfig configuration management."""

import os
from pathlib import Path
from unittest.mock import patch

from agent_core.config import AgentConfig


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
            ]:
                os.environ.pop(key, None)
            with patch("agent_core.config.load_dotenv"):
                config = AgentConfig.from_env()
        assert config.openai_api_key == ""
        assert config.model_name == "gpt-4o-mini"
        assert config.temperature == 0.0
        assert config.max_iterations == 10
