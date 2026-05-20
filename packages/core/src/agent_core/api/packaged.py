"""Packaged FastAPI application with same-origin Vue static serving."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agent_core.api.server import (
    _configure_middleware,
    _create_base_app,
    _include_api_routers,
    _resolve_config,
)
from agent_core.config import AgentConfig


def _is_reserved_packaged_path(path: str) -> bool:
    """Return whether the path belongs to packaged API/file routes."""
    return path in {"/api", "/files"} or path.startswith(("/api/", "/files/"))


def create_packaged_app(
    static_dir: Path,
    config: AgentConfig | None = None,
) -> FastAPI:
    """Create the packaged same-origin app.

    The packaged app keeps the normal API assembly shared with ``create_app`` but
    exposes business routes under ``/api`` and serves the Vue build at ``/``.

    Args:
        static_dir: Vite ``dist`` directory containing ``index.html``.
        config: Optional runtime configuration. Defaults to env.

    Returns:
        FastAPI app serving API, files, and Vue static assets.
    """
    resolved_static_dir = static_dir.resolve()
    index_file = resolved_static_dir / "index.html"
    if not resolved_static_dir.is_dir() or not index_file.is_file():
        raise RuntimeError(
            f"Packaged static directory must contain index.html: {resolved_static_dir}"
        )

    init_config = _resolve_config(config)
    app = _create_base_app(init_config)
    _configure_middleware(app)
    _include_api_routers(app, prefix="/api")

    assets_dir = resolved_static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa_fallback(path: str, request: Request) -> FileResponse:
        """Serve static files or Vue index for non-API frontend routes."""
        request_path = request.url.path
        if _is_reserved_packaged_path(request_path):
            raise HTTPException(status_code=404)

        candidate = (resolved_static_dir / path).resolve()
        if candidate.is_file() and candidate.is_relative_to(resolved_static_dir):
            return FileResponse(candidate)
        return FileResponse(index_file)

    return app
