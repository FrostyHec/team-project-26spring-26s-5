"""Tests for the course-materials REST API endpoints (CRUD + upload/download)."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from agent_core.api.server import create_app
from agent_core.config import AgentConfig
from agent_core.persistence.course_material_provider import set_course_material_store
from agent_core.persistence.course_material_store import CourseMaterialStore
from agent_core.persistence.course_provider import set_course_store
from agent_core.persistence.course_store import CourseStore
from agent_core.services.course_material_service import CourseMaterialService
from agent_core.services.course_service import CourseService


@pytest_asyncio.fixture
async def course_stores():
    """Create fresh in-memory course and material stores for each test."""
    course_store = CourseStore(":memory:")
    await course_store.initialize()
    await set_course_store(course_store)

    material_store = CourseMaterialStore(":memory:")
    await material_store.initialize()
    await set_course_material_store(material_store)

    yield course_store, material_store

    await set_course_store(None)
    await set_course_material_store(None)
    await material_store.close()
    await course_store.close()


@pytest_asyncio.fixture
async def client(course_stores):
    """Create an async HTTP client with the in-memory stores already configured."""
    config = AgentConfig(
        openai_api_key="test-key",
        model_name="gpt-4o-mini",
    )
    app = create_app(config)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def material_service(course_stores, tmp_path: Path) -> CourseMaterialService:
    """Build a CourseMaterialService backed by a temp directory."""
    course_store, material_store = course_stores
    course_service = CourseService(course_store)
    svc = CourseMaterialService(
        store=material_store,
        course_service=course_service,
        storage_root=str(tmp_path),
    )
    return svc


def mock_material_service(material_service: CourseMaterialService):
    """Patch course_materials._get_service to return the given service (async)."""
    return patch(
        "agent_core.api.routes.course_materials._get_service",
        new=AsyncMock(return_value=material_service),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestListMaterials:
    @pytest.mark.asyncio
    async def test_list_empty(
        self, client: AsyncClient, material_service: CourseMaterialService
    ) -> None:
        with mock_material_service(material_service):
            response = await client.get("/course-materials")
        assert response.status_code == 200
        assert response.json()["materials"] == []

    @pytest.mark.asyncio
    async def test_list_returns_all_materials(
        self, client: AsyncClient, material_service: CourseMaterialService
    ) -> None:
        course_resp = await client.post("/courses", json={"name": "Test Course"})
        course_id = course_resp.json()["id"]

        for fname in ("notes.pdf", "syllabus.txt"):
            with mock_material_service(material_service):
                await client.post(
                    "/course-materials",
                    data={"course_id": course_id, "description": fname},
                    files={"file": (fname, b"content", "application/octet-stream")},
                )

        with mock_material_service(material_service):
            response = await client.get("/course-materials")
        assert response.status_code == 200
        materials = response.json()["materials"]
        assert len(materials) == 2
        filenames = {m["filename"] for m in materials}
        assert "notes.pdf" in filenames
        assert "syllabus.txt" in filenames

    @pytest.mark.asyncio
    async def test_list_filter_by_course_id(
        self, client: AsyncClient, material_service: CourseMaterialService
    ) -> None:
        course_a = (await client.post("/courses", json={"name": "Course A"})).json()[
            "id"
        ]
        course_b = (await client.post("/courses", json={"name": "Course B"})).json()[
            "id"
        ]

        with mock_material_service(material_service):
            await client.post(
                "/course-materials",
                data={"course_id": course_a},
                files={"file": ("a.pdf", b"a", "application/octet-stream")},
            )
            await client.post(
                "/course-materials",
                data={"course_id": course_b},
                files={"file": ("b.pdf", b"b", "application/octet-stream")},
            )

            response = await client.get(f"/course-materials?course_id={course_a}")
        assert response.status_code == 200
        materials = response.json()["materials"]
        assert len(materials) == 1
        assert materials[0]["course_id"] == course_a


class TestUploadMaterial:
    @pytest.mark.asyncio
    async def test_upload_requires_course_id(self, client: AsyncClient) -> None:
        response = await client.post(
            "/course-materials",
            data={"course_id": "no-such-course"},
            files={"file": ("test.pdf", b"content", "application/pdf")},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_upload_unsupported_file_type(
        self, client: AsyncClient, material_service: CourseMaterialService
    ) -> None:
        course_resp = await client.post("/courses", json={"name": "Test Course"})
        course_id = course_resp.json()["id"]

        with mock_material_service(material_service):
            response = await client.post(
                "/course-materials",
                data={"course_id": course_id},
                files={"file": ("script.exe", b"malware", "application/x-executable")},
            )
        assert response.status_code == 422
        assert "Unsupported file type" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_valid_pdf(
        self, client: AsyncClient, material_service: CourseMaterialService
    ) -> None:
        course_resp = await client.post("/courses", json={"name": "Test Course"})
        course_id = course_resp.json()["id"]

        with mock_material_service(material_service):
            response = await client.post(
                "/course-materials",
                data={"course_id": course_id, "description": "Week 1 slides"},
                files={
                    "file": ("lecture1.pdf", b"PDF content here", "application/pdf")
                },
            )
        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "lecture1.pdf"
        assert data["file_type"] == ".pdf"
        assert data["description"] == "Week 1 slides"
        assert "id" in data
        assert data["course_id"] == course_id

    @pytest.mark.asyncio
    async def test_upload_txt_file(
        self, client: AsyncClient, material_service: CourseMaterialService
    ) -> None:
        course_resp = await client.post("/courses", json={"name": "Test Course"})
        course_id = course_resp.json()["id"]

        with mock_material_service(material_service):
            response = await client.post(
                "/course-materials",
                data={"course_id": course_id, "description": "Readme", "tags": "intro"},
                files={"file": ("README.txt", b"Hello world", "text/plain")},
            )
        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "README.txt"
        assert data["file_type"] == ".txt"
        assert data["tags"] == "intro"


class TestGetMaterial:
    @pytest.mark.asyncio
    async def test_get_existing(
        self, client: AsyncClient, material_service: CourseMaterialService
    ) -> None:
        course_resp = await client.post("/courses", json={"name": "Test Course"})
        course_id = course_resp.json()["id"]

        with mock_material_service(material_service):
            upload_resp = await client.post(
                "/course-materials",
                data={"course_id": course_id},
                files={"file": ("notes.pdf", b"content", "application/pdf")},
            )
        material_id = upload_resp.json()["id"]

        with mock_material_service(material_service):
            response = await client.get(f"/course-materials/{material_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == material_id
        assert data["filename"] == "notes.pdf"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_404(
        self, client: AsyncClient, material_service: CourseMaterialService
    ) -> None:
        with mock_material_service(material_service):
            response = await client.get("/course-materials/no-such-id")
        assert response.status_code == 404
        assert response.json()["detail"] == "Material not found"


class TestUpdateMaterial:
    async def _create_material(
        self, client: AsyncClient, material_service: CourseMaterialService
    ) -> str:
        """Create a course + material via the mocked service."""
        course_resp = await client.post("/courses", json={"name": "Test Course"})
        course_id = course_resp.json()["id"]

        upload_resp = await client.post(
            "/course-materials",
            data={"course_id": course_id, "description": "Original"},
            files={"file": ("notes.pdf", b"content", "application/pdf")},
        )
        return upload_resp.json()["id"]

    @pytest.mark.asyncio
    async def test_update_description(
        self, client: AsyncClient, material_service: CourseMaterialService
    ) -> None:
        material_id = await self._create_material(client, material_service)

        with mock_material_service(material_service):
            response = await client.patch(
                f"/course-materials/{material_id}",
                data={"description": "Updated description"},
            )
        assert response.status_code == 200
        assert response.json()["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_update_tags(
        self, client: AsyncClient, material_service: CourseMaterialService
    ) -> None:
        material_id = await self._create_material(client, material_service)

        with mock_material_service(material_service):
            response = await client.patch(
                f"/course-materials/{material_id}",
                data={"tags": "new,tag,list"},
            )
        assert response.status_code == 200
        assert response.json()["tags"] == "new,tag,list"

    @pytest.mark.asyncio
    async def test_update_both_fields(
        self, client: AsyncClient, material_service: CourseMaterialService
    ) -> None:
        material_id = await self._create_material(client, material_service)

        with mock_material_service(material_service):
            response = await client.patch(
                f"/course-materials/{material_id}",
                data={"description": "New desc", "tags": "tag1"},
            )
        data = response.json()
        assert data["description"] == "New desc"
        assert data["tags"] == "tag1"

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_404(
        self, client: AsyncClient, material_service: CourseMaterialService
    ) -> None:
        with mock_material_service(material_service):
            response = await client.patch(
                "/course-materials/no-such-id",
                data={"description": "x"},
            )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_empty_body_returns_existing(
        self, client: AsyncClient, material_service: CourseMaterialService
    ) -> None:
        material_id = await self._create_material(client, material_service)

        with mock_material_service(material_service):
            response = await client.patch(
                f"/course-materials/{material_id}",
                data={},
            )
        assert response.status_code == 200
        assert response.json()["description"] == "Original"


class TestDeleteMaterial:
    async def _create_material(
        self, client: AsyncClient, material_service: CourseMaterialService
    ) -> str:
        course_resp = await client.post("/courses", json={"name": "Test Course"})
        course_id = course_resp.json()["id"]

        upload_resp = await client.post(
            "/course-materials",
            data={"course_id": course_id},
            files={"file": ("notes.pdf", b"content", "application/pdf")},
        )
        return upload_resp.json()["id"]

    @pytest.mark.asyncio
    async def test_delete_existing(
        self, client: AsyncClient, material_service: CourseMaterialService
    ) -> None:
        material_id = await self._create_material(client, material_service)

        with mock_material_service(material_service):
            delete_resp = await client.delete(f"/course-materials/{material_id}")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["status"] == "deleted"
        assert delete_resp.json()["id"] == material_id

        with mock_material_service(material_service):
            get_resp = await client.get(f"/course-materials/{material_id}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(
        self, client: AsyncClient, material_service: CourseMaterialService
    ) -> None:
        with mock_material_service(material_service):
            response = await client.delete("/course-materials/no-such-id")
        assert response.status_code == 404
        assert response.json()["detail"] == "Material not found"


class TestDownloadMaterial:
    async def _create_material(
        self, client: AsyncClient, material_service: CourseMaterialService
    ) -> tuple[str, bytes]:
        course_resp = await client.post("/courses", json={"name": "Test Course"})
        course_id = course_resp.json()["id"]

        upload_resp = await client.post(
            "/course-materials",
            data={"course_id": course_id},
            files={"file": ("notes.pdf", b"PDF_CONTENTS", "application/pdf")},
        )
        return upload_resp.json()["id"], b"PDF_CONTENTS"

    @pytest.mark.asyncio
    async def test_download_existing_file(
        self, client: AsyncClient, material_service: CourseMaterialService
    ) -> None:
        material_id, expected_content = await self._create_material(
            client, material_service
        )

        with mock_material_service(material_service):
            response = await client.get(f"/course-materials/{material_id}/download")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/octet-stream"
        assert "notes.pdf" in response.headers.get("content-disposition", "")
        assert response.content == expected_content

    @pytest.mark.asyncio
    async def test_download_nonexistent_returns_404(
        self, client: AsyncClient, material_service: CourseMaterialService
    ) -> None:
        with mock_material_service(material_service):
            response = await client.get("/course-materials/no-such-id/download")
        assert response.status_code == 404
