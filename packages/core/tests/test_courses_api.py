"""Tests for the courses REST API endpoints (GET/POST/PATCH/DELETE /courses)."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from agent_core.api.server import create_app
from agent_core.config import AgentConfig
from agent_core.persistence.course_material_provider import set_course_material_store
from agent_core.persistence.course_material_store import CourseMaterialStore
from agent_core.persistence.course_provider import set_course_store
from agent_core.persistence.course_store import CourseStore


@pytest_asyncio.fixture
async def course_stores():
    """Create fresh in-memory course and material stores for each test.

    Runs BEFORE app lifespan so that the module-level singleton is set
    before init_dependencies lazily creates the store.
    """
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
    """Create an async HTTP client with the in-memory stores already configured.

    The httpx ASGITransport handles the ASGI lifespan automatically, running
    startup before the first request and shutdown when the client closes.
    """
    config = AgentConfig(
        openai_api_key="test-key",
        model_name="gpt-4o-mini",
    )
    app = create_app(config)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestListCourses:
    @pytest.mark.asyncio
    async def test_list_empty(self, client: AsyncClient) -> None:
        response = await client.get("/courses")
        assert response.status_code == 200
        assert response.json()["courses"] == []

    @pytest.mark.asyncio
    async def test_list_returns_all_courses(self, client: AsyncClient) -> None:
        await client.post(
            "/courses", json={"name": "Course A", "semester": "2026Spring"}
        )
        await client.post(
            "/courses", json={"name": "Course B", "semester": "2026Spring"}
        )

        response = await client.get("/courses")
        assert response.status_code == 200
        courses = response.json()["courses"]
        assert len(courses) == 2
        names = {c["name"] for c in courses}
        assert "Course A" in names
        assert "Course B" in names

    @pytest.mark.asyncio
    async def test_list_filter_by_semester(self, client: AsyncClient) -> None:
        await client.post("/courses", json={"name": "CS101", "semester": "2026Spring"})
        await client.post("/courses", json={"name": "CS201", "semester": "2026Fall"})

        response = await client.get("/courses?semester=2026Spring")
        assert response.status_code == 200
        courses = response.json()["courses"]
        assert len(courses) == 1
        assert courses[0]["name"] == "CS101"
        assert courses[0]["semester"] == "2026Spring"

    @pytest.mark.asyncio
    async def test_list_filter_nonexistent_semester_returns_empty(
        self, client: AsyncClient
    ) -> None:
        await client.post("/courses", json={"name": "CS101", "semester": "2026Spring"})
        response = await client.get("/courses?semester=2020Fall")
        assert response.status_code == 200
        assert response.json()["courses"] == []


class TestCreateCourse:
    @pytest.mark.asyncio
    async def test_create_minimal(self, client: AsyncClient) -> None:
        response = await client.post("/courses", json={"name": "Intro to CS"})
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Intro to CS"
        assert data["code"] == ""
        assert data["semester"] == ""
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_with_all_fields(self, client: AsyncClient) -> None:
        response = await client.post(
            "/courses",
            json={
                "name": "Advanced Algorithms",
                "code": "CS401",
                "credits": 4.0,
                "instructor": "Dr. Smith",
                "description": "Advanced algorithm design",
                "tags": "algorithms,cs",
                "semester": "2026Spring",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Advanced Algorithms"
        assert data["code"] == "CS401"
        assert data["credits"] == 4.0
        assert data["instructor"] == "Dr. Smith"
        assert data["description"] == "Advanced algorithm design"
        assert data["tags"] == "algorithms,cs"
        assert data["semester"] == "2026Spring"

    @pytest.mark.asyncio
    async def test_create_missing_name_returns_422(self, client: AsyncClient) -> None:
        response = await client.post("/courses", json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_id_is_generated(self, client: AsyncClient) -> None:
        response = await client.post("/courses", json={"name": "Test Course"})
        assert response.status_code == 201
        data = response.json()
        assert data["id"] != ""
        get_resp = await client.get(f"/courses/{data['id']}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Test Course"


class TestGetCourse:
    @pytest.mark.asyncio
    async def test_get_existing(self, client: AsyncClient) -> None:
        create_resp = await client.post("/courses", json={"name": "Fetch Test"})
        course_id = create_resp.json()["id"]

        response = await client.get(f"/courses/{course_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == course_id
        assert data["name"] == "Fetch Test"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_404(self, client: AsyncClient) -> None:
        response = await client.get("/courses/no-such-id-12345")
        assert response.status_code == 404
        assert response.json()["detail"] == "Course not found"


class TestUpdateCourse:
    @pytest.mark.asyncio
    async def test_update_single_field(self, client: AsyncClient) -> None:
        create_resp = await client.post("/courses", json={"name": "Old Name"})
        course_id = create_resp.json()["id"]

        response = await client.patch(
            f"/courses/{course_id}", json={"name": "New Name"}
        )
        assert response.status_code == 200
        assert response.json()["name"] == "New Name"

    @pytest.mark.asyncio
    async def test_update_multiple_fields(self, client: AsyncClient) -> None:
        create_resp = await client.post(
            "/courses", json={"name": "Course", "code": "C1", "semester": "2026Spring"}
        )
        course_id = create_resp.json()["id"]

        response = await client.patch(
            f"/courses/{course_id}",
            json={"code": "CS101", "instructor": "Dr. Lee", "semester": "2026Fall"},
        )
        data = response.json()
        assert data["name"] == "Course"
        assert data["code"] == "CS101"
        assert data["instructor"] == "Dr. Lee"
        assert data["semester"] == "2026Fall"

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_404(self, client: AsyncClient) -> None:
        response = await client.patch("/courses/no-such-id-12345", json={"name": "X"})
        assert response.status_code == 404
        assert response.json()["detail"] == "Course not found"

    @pytest.mark.asyncio
    async def test_update_empty_body_returns_existing(
        self, client: AsyncClient
    ) -> None:
        create_resp = await client.post("/courses", json={"name": "Unchanged"})
        course_id = create_resp.json()["id"]

        response = await client.patch(f"/courses/{course_id}", json={})
        assert response.status_code == 200
        assert response.json()["name"] == "Unchanged"


class TestDeleteCourse:
    @pytest.mark.asyncio
    async def test_delete_existing(self, client: AsyncClient) -> None:
        create_resp = await client.post("/courses", json={"name": "ToDelete"})
        course_id = create_resp.json()["id"]

        response = await client.delete(f"/courses/{course_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"
        assert response.json()["id"] == course_id

        get_resp = await client.get(f"/courses/{course_id}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, client: AsyncClient) -> None:
        response = await client.delete("/courses/no-such-id-12345")
        assert response.status_code == 404
        assert response.json()["detail"] == "Course not found"
