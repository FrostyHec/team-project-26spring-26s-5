"""Configuration for policy search indexing and retrieval."""

import os
from dataclasses import dataclass, replace
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[5]
_CORE_DIR = Path(__file__).resolve().parents[3]

DEFAULT_PDF_DIR = _PROJECT_ROOT / "pdfs"
DEFAULT_INDEX_DIR = _CORE_DIR / "output" / "policy_index"
DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 100


def _resolve_path(value: str | Path, base_dir: Path = _PROJECT_ROOT) -> Path:
    """Resolve a user-provided path relative to the project root."""
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return base_dir / path


@dataclass(frozen=True)
class PolicySearchConfig:
    """Policy search index configuration."""

    pdf_dir: Path = DEFAULT_PDF_DIR
    index_dir: Path = DEFAULT_INDEX_DIR
    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP

    @classmethod
    def from_env(cls) -> "PolicySearchConfig":
        """Load policy search configuration from environment variables."""
        pdf_dir = os.getenv("POLICY_PDF_DIR")
        index_dir = os.getenv("POLICY_INDEX_DIR")
        chunk_size = os.getenv("POLICY_CHUNK_SIZE")
        chunk_overlap = os.getenv("POLICY_CHUNK_OVERLAP")

        return cls(
            pdf_dir=_resolve_path(pdf_dir) if pdf_dir else DEFAULT_PDF_DIR,
            index_dir=_resolve_path(index_dir) if index_dir else DEFAULT_INDEX_DIR,
            chunk_size=int(chunk_size) if chunk_size else DEFAULT_CHUNK_SIZE,
            chunk_overlap=(
                int(chunk_overlap) if chunk_overlap else DEFAULT_CHUNK_OVERLAP
            ),
        )

    def with_overrides(
        self,
        pdf_dir: Path | None = None,
        index_dir: Path | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> "PolicySearchConfig":
        """Return a config with explicit command-line overrides applied.

        Relative override paths are resolved from the current working directory,
        matching normal CLI path behavior.
        """
        updates = {}
        if pdf_dir is not None:
            updates["pdf_dir"] = _resolve_path(pdf_dir, base_dir=Path.cwd())
        if index_dir is not None:
            updates["index_dir"] = _resolve_path(index_dir, base_dir=Path.cwd())
        if chunk_size is not None:
            updates["chunk_size"] = chunk_size
        if chunk_overlap is not None:
            updates["chunk_overlap"] = chunk_overlap
        return replace(self, **updates)
