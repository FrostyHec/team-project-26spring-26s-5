"""Settings REST routes — CRUD for user profile credentials.

Provides endpoints for the frontend settings panel to read and update
the user's CAS and email account credentials.  Passwords are encrypted
at rest; they are **never** returned via the API — only a boolean flag
indicates whether a password has been configured.

Architecture: This controller delegates all business logic to
:class:`~agent_core.services.profile_service.ProfileService`.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from agent_core.api.dependencies import get_config, get_profile_service, get_store
from agent_core.config import (
    AgentConfig,
    load_llm_settings,
    reset_llm_settings,
    save_llm_settings,
)
from agent_core.logging_utils import get_logger
from agent_core.models.llm_settings import LlmSettingsFile
from agent_core.models.settings import UpdateProfileRequest, UserProfileResponse
from agent_core.persistence.session_store import SessionStore
from agent_core.services.profile_service import ProfileService

logger = get_logger("api.settings")

router = APIRouter(prefix="/settings", tags=["settings"])

# ---------- Error messages ----------

_ERR_UPDATE_FAILED = "Failed to update settings"
_ERR_RESET_FAILED = "Failed to reset settings"
_ERR_LLM_UPDATE_FAILED = "Failed to update LLM settings"
_ERR_LLM_RESET_FAILED = "Failed to reset LLM settings"


@router.get("", response_model=UserProfileResponse)
async def get_settings(
    service: ProfileService = Depends(get_profile_service),
) -> UserProfileResponse:
    """Return the current user profile settings.

    Passwords are **not** returned — only a boolean flag indicates
    whether a password has been configured.

    Args:
        service: Injected ProfileService.

    Returns:
        Sanitised :class:`~agent_core.models.settings.UserProfileResponse`.
    """
    return await service.get_profile()


@router.put("", response_model=UserProfileResponse)
async def update_settings(
    request: UpdateProfileRequest,
    service: ProfileService = Depends(get_profile_service),
) -> UserProfileResponse:
    """Update user profile settings.

    Only non-``None`` fields in the request body are modified.  Supplied
    passwords are encrypted before storage and never echoed back.

    Args:
        request: Partial update request with plaintext credentials.
        service: Injected ProfileService.

    Returns:
        Sanitised :class:`~agent_core.models.settings.UserProfileResponse`
        reflecting the post-update state.

    Raises:
        HTTPException: 500 if the update fails unexpectedly.
    """
    try:
        return await service.update_profile(request)
    except Exception as exc:
        logger.exception("Failed to update settings: %s", exc)
        raise HTTPException(status_code=500, detail=_ERR_UPDATE_FAILED) from exc


@router.delete("", response_model=UserProfileResponse)
async def reset_settings(
    service: ProfileService = Depends(get_profile_service),
) -> UserProfileResponse:
    """Reset the user profile to an empty state.

    Clears all stored credentials (CAS and email) so the user can
    start fresh.

    Args:
        service: Injected ProfileService.

    Returns:
        Sanitised :class:`~agent_core.models.settings.UserProfileResponse`
        reflecting the cleared state.

    Raises:
        HTTPException: 500 if the reset fails unexpectedly.
    """
    try:
        return await service.reset_profile()
    except Exception as exc:
        logger.exception("Failed to reset settings: %s", exc)
        raise HTTPException(status_code=500, detail=_ERR_RESET_FAILED) from exc


@router.get("/llm", response_model=LlmSettingsFile)
async def get_llm_runtime_settings(
    config: AgentConfig = Depends(get_config),
) -> LlmSettingsFile:
    """Return the YAML-backed LLM runtime settings."""
    return load_llm_settings(config.llm_settings_path)


@router.put("/llm", response_model=LlmSettingsFile)
async def update_llm_runtime_settings(
    request: LlmSettingsFile,
    config: AgentConfig = Depends(get_config),
    store: SessionStore = Depends(get_store),
) -> LlmSettingsFile:
    """Persist the YAML-backed LLM runtime settings."""
    try:
        saved_settings = save_llm_settings(request, config.llm_settings_path)
        await store.clear_invalid_selected_providers(
            {provider.id for provider in saved_settings.providers}
        )
        return saved_settings
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=[
                {
                    "loc": list(error["loc"]),
                    "msg": error["msg"],
                    "type": error["type"],
                }
                for error in exc.errors()
            ],
        ) from exc
    except Exception as exc:
        logger.exception("Failed to update LLM settings: %s", exc)
        raise HTTPException(status_code=500, detail=_ERR_LLM_UPDATE_FAILED) from exc


@router.delete("/llm", response_model=LlmSettingsFile)
async def reset_llm_runtime_settings(
    config: AgentConfig = Depends(get_config),
    store: SessionStore = Depends(get_store),
) -> LlmSettingsFile:
    """Reset the YAML-backed LLM runtime settings to defaults."""
    try:
        reset_settings = reset_llm_settings(config.llm_settings_path)
        await store.clear_invalid_selected_providers(set())
        return reset_settings
    except Exception as exc:
        logger.exception("Failed to reset LLM settings: %s", exc)
        raise HTTPException(status_code=500, detail=_ERR_LLM_RESET_FAILED) from exc
