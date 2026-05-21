"""Course material service — business logic for material CRUD and file ops."""

import uuid
from datetime import UTC, datetime
from pathlib import Path

from agent_core.logging_utils import get_logger
from agent_core.models.course_material import CourseMaterial
from agent_core.persistence.course_material_store import (
    CourseMaterialStore,
    validate_file_extension,
    validate_file_size,
)
from agent_core.services.course_service import CourseService

logger = get_logger("services.course_material")


def resolve_course_material_storage_root() -> Path:
    """Return the runtime directory used for physical course material files."""
    from agent_core.config import AgentConfig

    return Path(AgentConfig.from_env().data_path) / "course_materials"


class MaterialValidationError(Exception):
    """Raised when file validation fails."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class MaterialNotFoundError(Exception):
    """Raised when a material ID does not exist in the store."""

    def __init__(self, material_id: str) -> None:
        self.material_id = material_id
        super().__init__(f"Material '{material_id}' not found.")


class CourseMaterialService:
    """Service encapsulating course material business logic."""

    def __init__(
        self,
        store: CourseMaterialStore,
        course_service: CourseService,
        storage_root: str | None = None,
    ) -> None:
        self._store = store
        self._course_service = course_service
        if storage_root:
            self._storage_root = Path(storage_root)
        else:
            self._storage_root = resolve_course_material_storage_root()
        self._storage_root.mkdir(parents=True, exist_ok=True)

    def _material_dir(self, course_id: str) -> Path:
        return self._storage_root / course_id

    def _stored_path(self, course_id: str, material_id: str, filename: str) -> Path:
        # Prevent path traversal: strip separators and ".." components
        clean = filename.replace("/", "_").replace("\\", "_").replace("..", "_")
        # Keep only safe chars; replace rest with underscore
        clean = "".join(c if c.isalnum() or c in "_.-" else "_" for c in clean)
        clean = clean.rstrip(". ")
        # Guard against empty or hidden filenames (e.g. ".htaccess")
        if not clean or clean.startswith("."):
            clean = "file"
        if len(clean) > 200:
            clean = clean[:200]
        base_path = self._material_dir(course_id) / f"{material_id}_{clean}"
        return self._get_unique_path(base_path)

    def _get_unique_path(self, base_path: Path) -> Path:
        """Generate a unique file path by appending a number if file exists."""
        if not base_path.exists():
            return base_path

        stem = base_path.stem
        suffix = base_path.suffix
        parent = base_path.parent
        counter = 1

        while True:
            new_path = parent / f"{stem} ({counter}){suffix}"
            if not new_path.exists():
                return new_path
            counter += 1

    async def create_from_upload(
        self,
        course_id: str,
        filename: str,
        file_bytes: bytes,
        description: str = "",
        tags: str = "",
    ) -> CourseMaterial:
        """Save an uploaded file and create a material record.

        Args:
            course_id: ID of the owning course.
            filename: Original filename.
            file_bytes: Raw file content.
            description: Optional description.
            tags: Optional tags.

        Returns:
            The created CourseMaterial record.

        Raises:
            MaterialValidationError: If file type or size is invalid.
            CourseNotFoundError: If the owning course does not exist.
        """
        # Validate course exists
        await self._course_service.get(course_id)

        # Validate extension
        ext = validate_file_extension(filename, self._store.allowed_extensions)
        if ext is None:
            raise MaterialValidationError(
                f"Unsupported file type '{Path(filename).suffix}'. "
                f"Allowed: {', '.join(sorted(self._store.allowed_extensions))}."
            )

        # Validate size
        if not validate_file_size(len(file_bytes), self._store.max_size_bytes):
            size_mb = self._store.max_size_bytes // (1024 * 1024)
            raise MaterialValidationError(
                f"File size {len(file_bytes):,} bytes exceeds the "
                f"{self._store.max_size_bytes:,} byte ({size_mb} MB) limit."
            )

        material_id = str(uuid.uuid4())
        rel_path = self._stored_path(course_id, material_id, filename)
        self._material_dir(course_id).mkdir(parents=True, exist_ok=True)

        with open(rel_path, "wb") as f:
            f.write(file_bytes)

        record = CourseMaterial(
            id=material_id,
            course_id=course_id,
            filename=filename,
            stored_path=str(rel_path),
            file_type=ext,
            file_size=len(file_bytes),
            description=description,
            tags=tags,
            created_at=datetime.now(UTC),
        )
        return await self._store.add(record)

    async def list(self, course_id: str | None = None) -> list[CourseMaterial]:
        return await self._store.list_all(course_id=course_id)

    async def get(self, material_id: str) -> CourseMaterial:
        record = await self._store.get(material_id)
        if record is None:
            raise MaterialNotFoundError(material_id)
        return record

    async def get_file_bytes(self, material_id: str) -> tuple[CourseMaterial, bytes]:
        """Fetch a material record and its raw file content."""
        record = await self.get(material_id)
        path = Path(record.stored_path)
        if not path.exists():
            logger.warning(
                "Physical file missing for material %s: %s", material_id, path
            )
            return record, b""
        with open(path, "rb") as f:
            return record, f.read()

    async def update(
        self, material_id: str, fields: dict[str, object]
    ) -> CourseMaterial:
        existing = await self._store.get(material_id)
        if existing is None:
            raise MaterialNotFoundError(material_id)
        updated = await self._store.update(material_id, fields)
        if updated is None:
            raise MaterialNotFoundError(material_id)
        return updated

    async def delete(self, material_id: str) -> bool:
        existing = await self._store.get(material_id)
        if existing is None:
            raise MaterialNotFoundError(material_id)
        return await self._store.delete(material_id)


__all__ = [
    "CourseMaterialService",
    "MaterialNotFoundError",
    "MaterialValidationError",
    "resolve_course_material_storage_root",
]
