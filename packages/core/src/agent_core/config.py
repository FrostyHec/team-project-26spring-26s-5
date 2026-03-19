"""Configuration management for the agent."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class AgentConfig:
    """Configuration for the ReAct agent.

    Loads settings from environment variables with sensible defaults.

    Attributes:
        openai_api_key: OpenAI API key for LLM access.
        openai_base_url: Custom API base URL (for proxies/alternatives).
        model_name: LLM model identifier.
        temperature: LLM sampling temperature.
        max_iterations: Maximum ReAct loop iterations.
        system_prompt: Default system prompt.
    """

    openai_api_key: str = ""
    openai_base_url: str = ""
    model_name: str = "gpt-4o-mini"
    temperature: float = 0.0
    max_iterations: int = 10
    system_prompt: str = field(
        default=(
            "You are a helpful AI assistant. You can use tools to help "
            "answer questions. When you need to perform calculations, "
            "use the available calculator tools."
        )
    )

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> "AgentConfig":
        """Load configuration from environment variables.

        Args:
            env_file: Optional path to .env file.

        Returns:
            Configured AgentConfig instance.
        """
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_base_url=os.getenv("OPENAI_BASE_URL", ""),
            model_name=os.getenv("MODEL_NAME", "gpt-4o-mini"),
            temperature=float(os.getenv("TEMPERATURE", "0.0")),
            max_iterations=int(os.getenv("MAX_ITERATIONS", "10")),
            system_prompt=os.getenv(
                "SYSTEM_PROMPT",
                cls.system_prompt,
            ),
        )
