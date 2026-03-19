"""Tests for AgentConfig configuration management."""

import os
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

    def test_from_env(self) -> None:
        """Test loading config from environment variables."""
        env_vars = {
            "OPENAI_API_KEY": "env-key",
            "MODEL_NAME": "gpt-3.5-turbo",
            "TEMPERATURE": "0.5",
            "MAX_ITERATIONS": "5",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            config = AgentConfig.from_env()
            assert config.openai_api_key == "env-key"
            assert config.model_name == "gpt-3.5-turbo"
            assert config.temperature == 0.5
            assert config.max_iterations == 5

    def test_from_env_defaults(self) -> None:
        """Test from_env with no env vars uses defaults."""
        env_clear = {
            "OPENAI_API_KEY": "",
            "MODEL_NAME": "",
            "TEMPERATURE": "",
        }
        with patch.dict(os.environ, {}, clear=False):
            # Remove keys if they exist
            for key in env_clear:
                os.environ.pop(key, None)
            # Patch load_dotenv to prevent .env file from overriding
            with patch("agent_core.config.load_dotenv"):
                config = AgentConfig.from_env()
                assert config.model_name == "gpt-4o-mini"
                assert config.temperature == 0.0
