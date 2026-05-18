"""FAISS index management — build, save, load, and search the vector index.

Stores both the FAISS index and chunk metadata as separate files
so the index can be rebuilt without re-parsing PDFs.
"""

import json
from pathlib import Path

import faiss
import numpy as np

from agent_core.logging_utils import get_logger
from agent_core.policy_search.embeddings import get_embeddings
from agent_core.policy_search.models import TextChunk

logger = get_logger("policy_search.index")

# File names within the index directory
_INDEX_FILE = "faiss.index"
_CHUNKS_FILE = "chunks.jsonl"


def get_missing_index_files(index_dir: Path) -> list[Path]:
    """Return required policy index files that are missing.

    Args:
        index_dir: Directory expected to contain the policy search index.

    Returns:
        Required file paths that do not currently exist.
    """
    required_files = [index_dir / _INDEX_FILE, index_dir / _CHUNKS_FILE]
    return [path for path in required_files if not path.exists()]


def log_index_startup_check(index_dir: Path) -> None:
    """Log a startup warning when the policy index has not been built.

    This check is intentionally non-blocking: the API server can still start,
    while policy search requests will continue to return the existing
    not-built error from the retriever/tool layer.
    """
    missing = get_missing_index_files(index_dir)
    if not missing:
        logger.info("Policy search index found at %s", index_dir)
        return

    missing_names = ", ".join(path.name for path in missing)
    logger.warning(
        "Policy search index is missing required file(s): %s. "
        "Run `uv run agent-cli build-policy-index` from packages/cli "
        "before using policy search.",
        missing_names,
    )


def build_index(
    chunks: list[TextChunk],
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> tuple[faiss.Index, list[TextChunk]]:
    """Build a FAISS index from text chunks.

    Args:
        chunks: List of text chunks to index.
        api_key: Embedding API key override.
        base_url: Embedding base URL override.
        model: Embedding model name override.

    Returns:
        Tuple of (FAISS index, ordered chunk list matching index positions).
    """
    if not chunks:
        raise ValueError("Cannot build index from empty chunk list")

    texts = [c.text for c in chunks]
    logger.info("Generating embeddings for %d chunks...", len(texts))
    embeddings = get_embeddings(texts, api_key=api_key, base_url=base_url, model=model)

    vectors = np.array(embeddings, dtype=np.float32)
    dimension = vectors.shape[1]
    logger.info(
        "Building FAISS index: %d vectors, dimension=%d", len(vectors), dimension
    )

    index = faiss.IndexFlatL2(dimension)
    index.add(vectors)

    logger.info("FAISS index built successfully with %d vectors", index.ntotal)
    return index, chunks


def save_index(
    index: faiss.Index,
    chunks: list[TextChunk],
    output_dir: Path,
) -> None:
    """Save a FAISS index and chunk metadata to disk.

    Args:
        index: The FAISS index to save.
        chunks: Ordered chunk list matching index positions.
        output_dir: Directory to write index files into.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    index_path = output_dir / _INDEX_FILE
    faiss.write_index(index, str(index_path))
    logger.info("Saved FAISS index to %s (%d vectors)", index_path, index.ntotal)

    chunks_path = output_dir / _CHUNKS_FILE
    with open(chunks_path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(chunk.model_dump_json() + "\n")
    logger.info("Saved %d chunk records to %s", len(chunks), chunks_path)


def load_index(index_dir: Path) -> tuple[faiss.Index, list[TextChunk]]:
    """Load a FAISS index and chunk metadata from disk.

    Args:
        index_dir: Directory containing saved index files.

    Returns:
        Tuple of (FAISS index, ordered chunk list).

    Raises:
        FileNotFoundError: If index files are missing.
    """
    index_path = index_dir / _INDEX_FILE
    chunks_path = index_dir / _CHUNKS_FILE

    if not index_path.exists():
        raise FileNotFoundError(f"FAISS index not found: {index_path}")
    if not chunks_path.exists():
        raise FileNotFoundError(f"Chunk metadata not found: {chunks_path}")

    index = faiss.read_index(str(index_path))
    logger.info("Loaded FAISS index from %s (%d vectors)", index_path, index.ntotal)

    chunks: list[TextChunk] = []
    with open(chunks_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                chunks.append(TextChunk(**data))
    logger.info("Loaded %d chunk records from %s", len(chunks), chunks_path)

    if index.ntotal != len(chunks):
        logger.warning(
            "Index/chunk count mismatch: %d vectors vs %d chunks",
            index.ntotal,
            len(chunks),
        )

    return index, chunks
