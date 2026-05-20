"""File serving route — serves PDF files with path-traversal protection."""

from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from agent_core.policy_search.config import PolicySearchConfig

router = APIRouter()


def _validate_filename(filename: str) -> Path:
    """Validate and resolve a PDF filename safely.

    Raises HTTPException on path traversal or invalid characters.
    """
    from urllib.parse import unquote

    # Decode any URL-encoded characters
    filename = unquote(filename)
    # Strip whitespace
    filename = filename.strip()
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .pdf files are supported.",
        )
    # Reject path separators and null bytes
    if "/" in filename or "\\" in filename or "\0" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename.",
        )
    pdfs_dir = PolicySearchConfig.from_env().pdf_dir.resolve()
    path = (pdfs_dir / filename).resolve()
    if not path.is_relative_to(pdfs_dir):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found.",
        )
    return path


@router.get("/pdfs/{filename}")
async def serve_pdf(filename: str) -> FileResponse:
    """Serve a PDF file from the pdfs directory.

    Args:
        filename: Name of the PDF file (no path components allowed).

    Returns:
        FileResponse with PDF content type and inline Content-Disposition.
    """
    path = _validate_filename(filename)
    # Use RFC 5987 encoding for Content-Disposition to support Chinese filenames
    encoded_filename = quote(filename, safe="")
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}"},
    )
