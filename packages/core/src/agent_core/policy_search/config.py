"""Configuration for policy search indexing and retrieval."""

import os
from dataclasses import dataclass, replace
from pathlib import Path

from agent_core.runtime_paths import resolve_data_path, resolve_runtime_path

DEFAULT_PDF_DIR = Path("./output/pdfs")
DEFAULT_INDEX_DIR = Path("./output/policy_index")
DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 100


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
        data_path = resolve_data_path()

        return cls(
            pdf_dir=(
                resolve_runtime_path(pdf_dir)
                if pdf_dir and pdf_dir.strip()
                else data_path / "pdfs"
            ),
            index_dir=(
                resolve_runtime_path(index_dir)
                if index_dir and index_dir.strip()
                else data_path / "policy_index"
            ),
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
            updates["pdf_dir"] = resolve_runtime_path(pdf_dir, base_dir=Path.cwd())
        if index_dir is not None:
            updates["index_dir"] = resolve_runtime_path(index_dir, base_dir=Path.cwd())
        if chunk_size is not None:
            updates["chunk_size"] = chunk_size
        if chunk_overlap is not None:
            updates["chunk_overlap"] = chunk_overlap
        return replace(self, **updates)
