"""Email REST routes — CRUD for emails, sync, flags, send, and settings.

Provides endpoints consumed by the Vue frontend email panel.  All
business logic is delegated to
:class:`~agent_core.services.email_service.EmailService`.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response

from agent_core.api.dependencies import get_email_service
from agent_core.logging_utils import get_logger
from agent_core.models.email import (
    AttachmentRecord,
    ClearCacheResult,
    EmailConnectionTestResult,
    EmailDetail,
    EmailSettingsInfo,
    EmailSummary,
    EmailSyncResult,
    SendEmailRequest,
    UpdateFlagRequest,
)
from agent_core.services.email_service import AttachmentNotFoundError, EmailService

logger = get_logger("api.email")

router = APIRouter(prefix="/email", tags=["email"])

# ---------- Error messages ----------

_ERR_EMAIL_NOT_FOUND = "Email not found"
_ERR_SYNC_FAILED = "Email sync failed"
_ERR_SEND_FAILED = "Failed to send email"
_ERR_FLAG_FAILED = "Failed to update flag"
_ERR_CONNECTION_FAILED = "Connection test failed"
_ERR_FILE_NOT_FOUND = "File not found"
_ERR_CREDENTIALS_CODE = "EMAIL_CREDENTIALS_MISSING"


def _raise_credentials_http_error(exc: ValueError) -> None:
    raise HTTPException(
        status_code=428,
        detail={
            "code": _ERR_CREDENTIALS_CODE,
            "message": str(exc),
        },
    ) from exc


# ------------------------------------------------------------------
# Sync
# ------------------------------------------------------------------


@router.post("/sync", response_model=EmailSyncResult)
async def sync_emails(
    days: int | None = Query(default=None, ge=1, le=365),
    folder: str = Query(default="INBOX"),
    service: EmailService = Depends(get_email_service),
) -> EmailSyncResult:
    """Pull new emails from IMAP and update the local store.

    Args:
        days: Optional override for how far back to fetch.
        service: Injected EmailService.

    Returns:
        Sync result with counts of new / updated / total emails.
    """
    try:
        return await service.sync_emails(days=days, folder=folder)
    except ValueError as exc:
        _raise_credentials_http_error(exc)
    except Exception as exc:
        logger.exception("Sync failed: %s", exc)
        raise HTTPException(status_code=500, detail=_ERR_SYNC_FAILED) from exc


# ------------------------------------------------------------------
# List / detail
# ------------------------------------------------------------------


@router.get("", response_model=list[EmailSummary])
async def list_emails(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    flagged_only: bool = Query(default=False),
    unseen_only: bool = Query(default=False),
    folder: str | None = Query(default=None),
    service: EmailService = Depends(get_email_service),
) -> list[EmailSummary]:
    """Return a paginated list of email summaries from the local store."""
    return await service.list_emails(
        limit=limit,
        offset=offset,
        flagged_only=flagged_only,
        unseen_only=unseen_only,
        folder=folder,
    )


@router.get("/count")
async def count_emails(
    service: EmailService = Depends(get_email_service),
) -> dict[str, int]:
    """Return the total number of locally stored emails."""
    total = await service.count_emails()
    return {"total": total}


@router.get("/{uid}", response_model=EmailDetail)
async def get_email_detail(
    uid: int,
    folder: str = Query(default="INBOX"),
    service: EmailService = Depends(get_email_service),
) -> EmailDetail:
    """Return full email detail including attachments.

    Implements the lazy-fetch pattern: if the email content has not been
    downloaded yet (or was cleared via cache-clear), this endpoint triggers
    an on-demand IMAP fetch before returning.  If credentials are not
    configured, a 428 is returned with EMAIL_CREDENTIALS_MISSING so the
    frontend can surface the settings guidance.  If the IMAP fetch fails
    for other reasons, a 503 is returned.
    """
    try:
        detail = await service.ensure_email_content_fetched(uid, folder=folder)
    except ValueError as exc:
        _raise_credentials_http_error(exc)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if detail is None:
        raise HTTPException(status_code=404, detail=_ERR_EMAIL_NOT_FOUND)
    return detail


# ------------------------------------------------------------------
# HTML body serving
# ------------------------------------------------------------------


@router.get("/{uid}/html")
async def get_email_html(
    uid: int,
    folder: str = Query(default="INBOX"),
    service: EmailService = Depends(get_email_service),
) -> Response:
    """Serve the cached HTML body with CID references rewritten."""
    html_content = await service.get_html_with_cid_replacement(uid, folder=folder)
    if html_content is None:
        raise HTTPException(status_code=404, detail="No HTML body available")

    return Response(content=html_content, media_type="text/html")


# ------------------------------------------------------------------
# Attachment download
# ------------------------------------------------------------------


@router.get("/{uid}/attachments/{attachment_id}")
async def download_attachment(
    uid: int,
    attachment_id: int,
    folder: str = Query(default="INBOX"),
    service: EmailService = Depends(get_email_service),
) -> FileResponse:
    """Download a cached attachment file."""
    detail = await service.get_email_detail(uid, folder=folder)
    if detail is None:
        raise HTTPException(status_code=404, detail=_ERR_EMAIL_NOT_FOUND)
    att = next((a for a in detail.attachments if a.id == attachment_id), None)
    if att is None:
        raise HTTPException(status_code=404, detail="Attachment not found")

    from pathlib import Path

    cache_root = Path(service._data_root).resolve()
    full_path = (Path(service._data_root) / att.local_path).resolve()
    try:
        full_path.relative_to(cache_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid attachment path") from exc
    if not full_path.is_file():
        raise HTTPException(status_code=404, detail=_ERR_FILE_NOT_FOUND)
    return FileResponse(
        full_path,
        media_type=att.content_type,
        filename=att.filename,
    )


@router.post("/{uid}/attachments/{att_id}/download", response_model=AttachmentRecord)
async def trigger_attachment_download(
    uid: int,
    att_id: int,
    folder: str = Query(default="INBOX"),
    service: EmailService = Depends(get_email_service),
) -> AttachmentRecord:
    """Fetch a regular attachment from IMAP on demand and cache it locally.

    Returns the updated ``AttachmentRecord`` with ``is_downloaded=True``
    and the resolved ``local_path``.
    """
    try:
        return await service.download_attachment(uid, att_id, folder=folder)
    except AttachmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        _raise_credentials_http_error(exc)
    except Exception as exc:
        logger.exception("Attachment download failed: %s", exc)
        raise HTTPException(
            status_code=500, detail="Attachment download failed"
        ) from exc


# ------------------------------------------------------------------
# Flags
# ------------------------------------------------------------------


@router.patch("/{uid}/flags")
async def update_flag(
    uid: int,
    request: UpdateFlagRequest,
    folder: str = Query(default="INBOX"),
    service: EmailService = Depends(get_email_service),
) -> dict[str, bool]:
    """Set or clear an email flag (seen/flagged/answered)."""
    try:
        ok = await service.update_flag(uid, request.flag, request.value, folder=folder)
        return {"success": ok}
    except ValueError as exc:
        _raise_credentials_http_error(exc)
    except Exception as exc:
        logger.exception("Flag update failed: %s", exc)
        raise HTTPException(status_code=500, detail=_ERR_FLAG_FAILED) from exc


# ------------------------------------------------------------------
# Send / reply
# ------------------------------------------------------------------


@router.post("/send")
async def send_email(
    request: SendEmailRequest,
    service: EmailService = Depends(get_email_service),
) -> dict[str, str]:
    """Send an email via SMTP."""
    try:
        await service.send_email(request)
        return {"status": "sent"}
    except ValueError as exc:
        _raise_credentials_http_error(exc)
    except Exception as exc:
        logger.exception("Send failed: %s", exc)
        raise HTTPException(status_code=500, detail=_ERR_SEND_FAILED) from exc


# ------------------------------------------------------------------
# Connection test
# ------------------------------------------------------------------


@router.post("/test-connection", response_model=EmailConnectionTestResult)
async def test_connection(
    service: EmailService = Depends(get_email_service),
) -> EmailConnectionTestResult:
    """Test IMAP and SMTP connectivity with stored credentials."""
    try:
        return await service.test_connection()
    except ValueError as exc:
        _raise_credentials_http_error(exc)
    except Exception as exc:
        logger.exception("Connection test failed: %s", exc)
        raise HTTPException(status_code=500, detail=_ERR_CONNECTION_FAILED) from exc


# ------------------------------------------------------------------
# Settings
# ------------------------------------------------------------------


@router.get("/settings/email", response_model=EmailSettingsInfo)
async def get_email_settings(
    service: EmailService = Depends(get_email_service),
) -> EmailSettingsInfo:
    """Return email-specific settings (fetch_days, auto_sync)."""
    return await service.get_email_settings()


@router.put("/settings/email", response_model=EmailSettingsInfo)
async def update_email_settings(
    settings: EmailSettingsInfo,
    service: EmailService = Depends(get_email_service),
) -> EmailSettingsInfo:
    """Update email-specific settings."""
    return await service.update_email_settings(
        fetch_days=settings.email_fetch_days,
        auto_sync=settings.auto_sync,
    )


# ------------------------------------------------------------------
# Cache management
# ------------------------------------------------------------------


@router.delete("/cache", response_model=ClearCacheResult)
async def clear_cache(
    service: EmailService = Depends(get_email_service),
) -> ClearCacheResult:
    """Delete all cached HTML and attachment files."""
    return await service.clear_cache()
