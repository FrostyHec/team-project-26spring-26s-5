"""Typed models for YAML-backed LLM runtime settings."""

from pathlib import Path

from pydantic import BaseModel, Field, model_validator

DEFAULT_LLM_SETTINGS_PATH = Path("./output/llm_settings.yaml")
DEFAULT_MODEL_NAME = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_ITERATIONS = 10
DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful AI assistant. You can use tools to help answer questions. "
    "When you need to perform calculations, use the available calculator tools."
)


def _next_generated_provider_id(seed: int, used_provider_ids: set[str]) -> str:
    """Generate the next stable provider ID that does not collide."""
    candidate_number = max(1, seed)
    candidate_id = f"provider_{candidate_number}"

    while candidate_id in used_provider_ids:
        candidate_number += 1
        candidate_id = f"provider_{candidate_number}"

    return candidate_id


class ProviderSettings(BaseModel):
    """A single LLM provider entry from the YAML settings file."""

    id: str
    name: str
    priority: int = 0
    base_url: str = ""
    api_key: str = ""
    model: str = DEFAULT_MODEL_NAME
    enabled: bool = True


class LlmSettingsFile(BaseModel):
    """Complete YAML-backed LLM settings."""

    temperature: float = DEFAULT_TEMPERATURE
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    debug_mode: bool = False
    providers: list[ProviderSettings] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_provider_ids(cls, data: object) -> object:
        """Normalize missing or duplicate provider IDs before strict validation."""
        if not isinstance(data, dict):
            return data

        raw_providers = data.get("providers")
        if not isinstance(raw_providers, list):
            return data

        normalized_providers: list[object] = []
        used_provider_ids: set[str] = set()

        for index, provider in enumerate(raw_providers):
            if isinstance(provider, ProviderSettings):
                provider_data = provider.model_dump()
            elif isinstance(provider, dict):
                provider_data = dict(provider)
            else:
                normalized_providers.append(provider)
                continue

            raw_provider_id = provider_data.get("id", "")
            trimmed_provider_id = str(raw_provider_id or "").strip()
            normalized_provider_id = (
                trimmed_provider_id
                if trimmed_provider_id and trimmed_provider_id not in used_provider_ids
                else _next_generated_provider_id(index + 1, used_provider_ids)
            )

            used_provider_ids.add(normalized_provider_id)
            provider_data["id"] = normalized_provider_id
            normalized_providers.append(provider_data)

        return {
            **data,
            "providers": normalized_providers,
        }

    @model_validator(mode="after")
    def sort_providers(self) -> "LlmSettingsFile":
        """Keep providers sorted by ascending priority for deterministic use."""
        provider_ids = [provider.id for provider in self.providers]
        if len(provider_ids) != len(set(provider_ids)):
            raise ValueError("Provider IDs must be unique")
        for provider in self.providers:
            if provider.enabled and not provider.api_key.strip():
                raise ValueError(
                    f"Provider '{provider.id}' is enabled but has no API key"
                )
        self.providers = sorted(self.providers, key=lambda provider: provider.priority)
        return self

    def default_provider(self) -> ProviderSettings:
        """Return the highest-priority enabled provider, or a safe default."""
        for provider in self.providers:
            if provider.enabled:
                return provider
        return ProviderSettings(
            id="default",
            name="Default Provider",
            model=DEFAULT_MODEL_NAME,
        )

    def provider_by_id(self, provider_id: str) -> ProviderSettings | None:
        """Return a provider by ID when it exists in the settings file."""
        for provider in self.providers:
            if provider.id == provider_id:
                return provider
        return None
