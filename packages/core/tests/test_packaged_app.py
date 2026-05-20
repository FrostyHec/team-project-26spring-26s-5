"""Tests for the packaged same-origin FastAPI app."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_core.api.packaged import create_packaged_app
from agent_core.config import AgentConfig


def _write_static_dir(tmp_path: Path) -> Path:
    static_dir = tmp_path / "dist"
    assets_dir = static_dir / "assets"
    assets_dir.mkdir(parents=True)
    (static_dir / "index.html").write_text('<div id="app"></div>', encoding="utf-8")
    (assets_dir / "app.js").write_text("console.log('ok')", encoding="utf-8")
    return static_dir


@pytest.fixture
def packaged_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Create a packaged app test client with isolated runtime paths."""
    static_dir = _write_static_dir(tmp_path)
    data_path = tmp_path / "data"
    pdf_dir = data_path / "pdfs"
    pdf_dir.mkdir(parents=True)
    (pdf_dir / "guide.pdf").write_bytes(b"%PDF-1.4\n")
    monkeypatch.setenv("DATA_PATH", str(data_path))
    monkeypatch.setenv("POLICY_PDF_DIR", str(pdf_dir))

    config = AgentConfig(
        openai_api_key="test-key",
        db_path=":memory:",
        data_path=str(data_path),
        log_file=str(data_path / "logs" / "agent.log"),
        llm_settings_path=str(data_path / "llm_settings.yaml"),
    )
    app = create_packaged_app(static_dir, config)
    with TestClient(app) as client:
        yield client


def test_packaged_health_uses_api_prefix(packaged_client: TestClient) -> None:
    """Packaged app should expose business routes under /api."""
    response = packaged_client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_packaged_files_remain_top_level(packaged_client: TestClient) -> None:
    """The files route should stay at /files for existing file URLs."""
    response = packaged_client.get("/files/pdfs/guide.pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"


def test_packaged_root_serves_index(packaged_client: TestClient) -> None:
    """Root should serve the Vue index."""
    response = packaged_client.get("/")

    assert response.status_code == 200
    assert '<div id="app"></div>' in response.text


def test_packaged_frontend_route_uses_spa_fallback(
    packaged_client: TestClient,
) -> None:
    """Frontend history routes should fall back to index.html."""
    response = packaged_client.get("/settings")

    assert response.status_code == 200
    assert '<div id="app"></div>' in response.text


def test_packaged_static_asset_is_served(packaged_client: TestClient) -> None:
    """Static assets should be served from the Vite assets directory."""
    response = packaged_client.get("/assets/app.js")

    assert response.status_code == 200
    assert "console.log('ok')" in response.text


def test_packaged_api_404_is_not_spa_fallback(packaged_client: TestClient) -> None:
    """Unknown API routes should remain API 404s, not return index.html."""
    response = packaged_client.get("/api/not-found")

    assert response.status_code == 404
    assert '<div id="app"></div>' not in response.text


@pytest.mark.parametrize("path", ["/apiary", "/files-help"])
def test_packaged_reserved_prefix_boundaries_fall_back_to_spa(
    packaged_client: TestClient,
    path: str,
) -> None:
    """Only /api and /files path segments should be reserved."""
    response = packaged_client.get(path)

    assert response.status_code == 200
    assert '<div id="app"></div>' in response.text


def test_packaged_static_dir_must_contain_index(tmp_path: Path) -> None:
    """Missing index.html should fail fast with a clear error."""
    static_dir = tmp_path / "dist"
    static_dir.mkdir()

    with pytest.raises(RuntimeError, match="index.html"):
        create_packaged_app(static_dir, AgentConfig(db_path=":memory:"))
