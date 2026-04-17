"""Policy retriever — top-K vector search over the FAISS index.

Provides the main search interface used by the policy search tool.
Manages a singleton index instance loaded lazily on first query.
"""

import threading
from pathlib import Path

import faiss
import numpy as np

from agent_core.logging_utils import get_logger
from agent_core.policy_search.embeddings import get_query_embedding
from agent_core.policy_search.index import load_index
from agent_core.policy_search.models import (
    FormattedSource,
    RetrievalResult,
    TextChunk,
)

logger = get_logger("policy_search.retriever")

# Default index location
DEFAULT_INDEX_DIR = Path(__file__).resolve().parents[3] / "output" / "policy_index"

# Module-level singleton
_index: faiss.Index | None = None
_chunks: list[TextChunk] = []
_index_dir: Path = DEFAULT_INDEX_DIR
_lock = threading.Lock()


def set_index_dir(index_dir: Path) -> None:
    """Override the default index directory (useful for tests).

    Also resets any loaded index so the next search triggers a reload.
    """
    global _index, _chunks, _index_dir
    with _lock:
        _index = None
        _chunks = []
        _index_dir = index_dir


def _ensure_loaded() -> tuple[faiss.Index, list[TextChunk]]:
    """Lazily load the FAISS index on first use."""
    global _index, _chunks
    with _lock:
        if _index is None:
            logger.info("Loading policy index from %s", _index_dir)
            _index, _chunks = load_index(_index_dir)
        return _index, _chunks


def search(
    query: str,
    top_k: int = 5,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> list[RetrievalResult]:
    """Search the policy index for chunks relevant to a query.

    Args:
        query: Natural language search query.
        top_k: Number of results to return.
        api_key: Embedding API key override.
        base_url: Embedding base URL override.
        model: Embedding model name override.

    Returns:
        List of :class:`RetrievalResult` ordered by relevance (best first).
    """
    index, chunks = _ensure_loaded()

    query_vec = get_query_embedding(
        query, api_key=api_key, base_url=base_url, model=model
    )
    query_array = np.array([query_vec], dtype=np.float32)

    actual_k = min(top_k, index.ntotal)
    distances, indices = index.search(query_array, actual_k)

    results: list[RetrievalResult] = []
    for dist, idx in zip(distances[0], indices[0], strict=False):
        if idx < 0 or idx >= len(chunks):
            continue
        chunk = chunks[idx]
        results.append(
            RetrievalResult(
                snippet=chunk.text,
                score=float(dist),
                title=chunk.metadata.title,
                page=chunk.metadata.page,
                section=chunk.metadata.section,
                source_path=chunk.metadata.source_path,
                official_url=chunk.metadata.official_url,
                chunk_id=chunk.chunk_id,
            )
        )

    logger.info(
        "Search for '%s': returned %d results (top_k=%d)",
        query[:50],
        len(results),
        top_k,
    )
    return results


def format_results_for_llm(results: list[RetrievalResult]) -> str:
    """Format retrieval results into a string suitable for LLM consumption.

    Produces a structured text block with numbered sources and snippets,
    Produces a structured text block with numbered sources and snippets,
    plus a citation index the LLM can reference as ``[source n]``.

    Args:
        results: Retrieval results from :func:`search`.

    Returns:
        Formatted string with snippets and citation references.
    """
    if not results:
        return "No relevant policy documents found."  # nosemgrep

    sections: list[str] = []
    sources: list[FormattedSource] = []

    for i, result in enumerate(results, 1):
        source = FormattedSource(
            index=i,
            title=result.title,
            page=result.page,
            section=result.section,
        )
        sources.append(source)

        snippet_preview = result.snippet.strip().replace("\n", " ")
        if len(snippet_preview) > 300:
            snippet_preview = snippet_preview[:300] + "..."

        sections.append(
            f"--- Search Result {i} ---\n"  # nosemgrep
            f"Source: {source.to_citation()}\n"
            f"Content: {snippet_preview}\n"
        )

    output_parts = [
        "Retrieved relevant content from campus policy documents:\n\n"
    ]  # nosemgrep
    output_parts.extend(sections)
    output_parts.append("--- Citation Index ---")
    for src in sources:
        output_parts.append(src.to_citation())

    return "\n".join(output_parts)
