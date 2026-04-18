"""Pending notifications REST routes.

Provides endpoints for the frontend to poll in-app alarm notifications
and acknowledge (dismiss) them.

Architecture: Delegates to
:class:`~agent_core.services.alarm_service.AlarmService`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from agent_core.api.dependencies import get_alarm_service
from agent_core.logging_utils import get_logger
from agent_core.models.alarm import PendingNotification
from agent_core.services.alarm_service import AlarmService

logger = get_logger("api.notifications")

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/pending", response_model=list[PendingNotification])
async def get_pending_notifications(
    service: AlarmService = Depends(get_alarm_service),
) -> list[PendingNotification]:
    """Return all unacknowledged in-app alarm notifications, oldest first.

    Returns:
        List of :class:`~agent_core.models.alarm.PendingNotification`.
    """
    notifications = await service.get_pending_notifications()
    logger.debug("Fetched %d pending notification(s)", len(notifications))
    return notifications


@router.post("/{notification_id}/ack")
async def ack_notification(
    notification_id: str,
    service: AlarmService = Depends(get_alarm_service),
) -> dict[str, str]:
    """Acknowledge (dismiss) a pending notification by its id.

    Args:
        notification_id: UUID of the notification to dismiss.
        service: Injected AlarmService.

    Returns:
        ``{"status": "ok"}``

    Raises:
        HTTPException: 404 if the notification id is not found.
    """
    deleted = await service.ack_notification(notification_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Notification '{notification_id}' not found.",
        )
    logger.info("Acknowledged notification %s", notification_id)
    return {"status": "ok"}
