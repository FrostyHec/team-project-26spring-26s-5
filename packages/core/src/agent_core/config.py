"""Configuration management for the agent."""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

from agent_core.models.llm_settings import (
    DEFAULT_MODEL_NAME,
    DEFAULT_SYSTEM_PROMPT,
    LlmSettingsFile,
)
from agent_core.runtime_paths import (
    resolve_data_path,
    resolve_path_env,
    set_runtime_env_file,
)
from agent_core.security.encryption import ENV_KEY as _ENCRYPTION_ENV_KEY


def _resolve_llm_settings_path(settings_path: str | Path | None = None) -> Path:
    """Resolve the YAML settings path from an explicit path, env, or default."""
    if settings_path is not None:
        return Path(settings_path)
    data_path = resolve_data_path()
    return resolve_path_env(
        "LLM_SETTINGS_PATH",
        data_path / "llm_settings.yaml",
    )


def load_llm_settings(settings_path: str | Path | None = None) -> LlmSettingsFile:
    """Load YAML-backed LLM settings from disk."""
    resolved_path = _resolve_llm_settings_path(settings_path)
    if not resolved_path.exists():
        return LlmSettingsFile()
    with resolved_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return LlmSettingsFile.model_validate(raw)


def save_llm_settings(
    settings: LlmSettingsFile, settings_path: str | Path | None = None
) -> LlmSettingsFile:
    """Persist YAML-backed LLM settings and return the normalized result."""
    resolved_path = _resolve_llm_settings_path(settings_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = LlmSettingsFile.model_validate(settings.model_dump())
    with resolved_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(
            normalized.model_dump(),
            handle,
            allow_unicode=True,
            sort_keys=False,
        )
    return normalized


def reset_llm_settings(settings_path: str | Path | None = None) -> LlmSettingsFile:
    """Reset YAML-backed LLM settings to the default structure."""
    return save_llm_settings(LlmSettingsFile(), settings_path=settings_path)


def database_file(db_path: str | Path, filename: str) -> str:
    """Return a concrete database file path inside the configured DB directory."""
    if str(db_path) == ":memory:":
        return ":memory:"
    return str(Path(db_path) / filename)


@dataclass
class AgentConfig:
    """Configuration for the ReAct agent.

    Loads non-LLM settings from environment variables and LLM settings from YAML.

    Attributes:
        openai_api_key: Selected provider API key from YAML.
        openai_base_url: Selected provider base URL from YAML.
        model_name: Selected provider model name from YAML.
        temperature: LLM sampling temperature from YAML.
        max_iterations: Maximum ReAct loop iterations from YAML.
        system_prompt: Default system prompt from YAML.
    """

    openai_api_key: str = ""
    openai_base_url: str = ""
    model_name: str = "gpt-4o-mini"
    temperature: float = 0.0
    max_iterations: int = 10
    log_level: str = "INFO"
    log_file: str = "./output/logs/agent.log"
    db_path: str = "./output"
    data_path: str = "./output"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    course_material_max_size_mb: int = 10
    course_material_allowed_extensions: str = ".pdf,.docx,.pptx,.xlsx,.txt,.md"
    encryption_key: str = ""
    llm_settings_path: str = "./output/llm_settings.yaml"
    system_prompt: str = field(default=DEFAULT_SYSTEM_PROMPT)

    @staticmethod
    def _load_llm_settings(settings_path: Path) -> LlmSettingsFile:
        """Load YAML-backed LLM settings, falling back to safe defaults."""
        return load_llm_settings(settings_path)

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> "AgentConfig":
        """Load configuration from environment variables and YAML.

        Args:
            env_file: Optional path to .env file.

        Returns:
            Configured AgentConfig instance.
        """
        if env_file:
            set_runtime_env_file(env_file)
            load_dotenv(env_file, override=True)
            base_dir = Path(env_file).expanduser().resolve().parent
        else:
            load_dotenv()
            base_dir = None

        data_path = resolve_data_path(base_dir=base_dir)
        db_path = resolve_path_env(
            "DB_PATH",
            data_path,
            base_dir=base_dir,
        )
        log_file = resolve_path_env(
            "LOG_FILE",
            data_path / "logs" / "agent.log",
            base_dir=base_dir,
        )
        llm_settings_path = resolve_path_env(
            "LLM_SETTINGS_PATH",
            data_path / "llm_settings.yaml",
            base_dir=base_dir,
        )
        llm_settings = cls._load_llm_settings(llm_settings_path)
        provider = llm_settings.default_provider()

        return cls(
            openai_api_key=provider.api_key,
            openai_base_url=provider.base_url,
            model_name=provider.model or DEFAULT_MODEL_NAME,
            temperature=llm_settings.temperature,
            max_iterations=llm_settings.max_iterations,
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_file=str(log_file),
            db_path=":memory:" if os.getenv("DB_PATH") == ":memory:" else str(db_path),
            data_path=str(data_path),
            app_host=os.getenv("APP_HOST", "127.0.0.1"),
            app_port=int(os.getenv("APP_PORT", "8000")),
            encryption_key=os.getenv(_ENCRYPTION_ENV_KEY, ""),
            course_material_max_size_mb=int(
                os.getenv("COURSE_MATERIAL_MAX_SIZE_MB", "10")
            ),
            course_material_allowed_extensions=os.getenv(
                "COURSE_MATERIAL_ALLOWED_EXTENSIONS",
                ".pdf,.docx,.pptx,.xlsx,.txt,.md",
            ),
            llm_settings_path=str(llm_settings_path),
            system_prompt=llm_settings.system_prompt or DEFAULT_SYSTEM_PROMPT,
        )
