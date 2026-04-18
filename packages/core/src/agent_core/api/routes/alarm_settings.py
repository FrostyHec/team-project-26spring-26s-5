"""Alarm settings REST routes.

Provides endpoints for reading and updating the global deadline alarm
configuration (:class:`~agent_core.models.alarm.AlarmSettings`).

Architecture: Delegates all logic to
:class:`~agent_core.services.alarm_service.AlarmService`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from agent_core.api.dependencies import get_alarm_service
from agent_core.logging_utils import get_logger
from agent_core.models.alarm import AlarmSettings
from agent_core.services.alarm_service import AlarmService

logger = get_logger("api.alarm_settings")

router = APIRouter(prefix="/alarm-settings", tags=["alarm"])

_ERR_SAVE_FAILED = "Failed to save alarm settings"


@router.get("", response_model=AlarmSettings)
async def get_alarm_settings(
    service: AlarmService = Depends(get_alarm_service),
) -> AlarmSettings:
    """Return the current global alarm settings.

    Returns:
        :class:`~agent_core.models.alarm.AlarmSettings` (defaults when unset).
    """
    return await service.get_settings()


@router.put("", response_model=AlarmSettings)
async def update_alarm_settings(
    settings: AlarmSettings,
    service: AlarmService = Depends(get_alarm_service),
) -> AlarmSettings:
    """Update global alarm settings.

    Special behaviour: if the previous settings had ``enabled=False`` and the
    new settings have ``enabled=True``, an immediate alarm check is triggered
    so that any pending reminders are dispatched without waiting for the next
    polling cycle.

    Args:
        settings: New alarm settings (validated by Pydantic).
        service: Injected AlarmService.

    Returns:
        Saved :class:`~agent_core.models.alarm.AlarmSettings`.

    Raises:
        HTTPException: 422 if the settings are invalid (forwarded from Pydantic).
        HTTPException: 500 on unexpected persistence errors.
    """
    try:
        previous = await service.get_settings()
        saved = await service.save_settings(settings)
        # Immediate check when re-enabling: catch up on any missed reminders
        if not previous.enabled and saved.enabled:
            logger.info("Alarm re-enabled — running immediate check_and_dispatch")
            await service.check_and_dispatch(datetime.now(UTC))
        return saved
    except ValueError as exc:
        # Pydantic validation errors become 422 automatically via FastAPI,
        # but model_validator errors raised inside the endpoint become ValueError.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to save alarm settings: %s", exc)
        raise HTTPException(status_code=500, detail=_ERR_SAVE_FAILED) from exc
