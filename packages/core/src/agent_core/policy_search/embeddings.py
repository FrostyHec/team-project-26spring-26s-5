"""Embedding wrapper — calls DashScope text-embedding-v4 via OpenAI-compatible API.

Handles the DashScope batch size constraint (max 10 texts per request)
by automatically splitting large batches into sub-batches.
"""

import os

from openai import OpenAI

from agent_core.logging_utils import get_logger

logger = get_logger("policy_search.embeddings")

# DashScope embedding API limits each batch to 10 items
_MAX_BATCH_SIZE = 10


def _get_embedding_config() -> tuple[str, str, str]:
    """Load embedding configuration from environment variables.

    Returns:
        Tuple of (api_key, base_url, model_name).
    """
    api_key = os.getenv("EMBEDDING_API_KEY", "")
    base_url = os.getenv(
        "EMBEDDING_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    model = os.getenv("EMBEDDING_MODEL", "text-embedding-v4")
    return api_key, base_url, model


def get_embeddings(
    texts: list[str],
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> list[list[float]]:
    """Generate embeddings for a list of texts.

    Automatically splits into sub-batches of 10 to comply with
    DashScope API limits.

    Args:
        texts: List of text strings to embed.
        api_key: Override for EMBEDDING_API_KEY env var.
        base_url: Override for EMBEDDING_BASE_URL env var.
        model: Override for EMBEDDING_MODEL env var.

    Returns:
        List of embedding vectors (each a list of floats).

    Raises:
        ValueError: If no API key is configured.
    """
    env_key, env_url, env_model = _get_embedding_config()
    api_key = api_key or env_key
    base_url = base_url or env_url
    model = model or env_model

    if not api_key:
        raise ValueError(
            "EMBEDDING_API_KEY is not set. "
            "Please configure it in .env or pass it explicitly."
        )

    client = OpenAI(api_key=api_key, base_url=base_url)
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), _MAX_BATCH_SIZE):
        batch = texts[i : i + _MAX_BATCH_SIZE]
        logger.debug(
            "Embedding batch %d-%d of %d texts",
            i,
            i + len(batch),
            len(texts),
        )
        response = client.embeddings.create(input=batch, model=model)
        batch_embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(batch_embeddings)

    logger.info("Generated %d embeddings (model=%s)", len(all_embeddings), model)
    return all_embeddings


def get_query_embedding(
    query: str,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> list[float]:
    """Generate an embedding for a single query string.

    Args:
        query: The search query text.
        api_key: Override for EMBEDDING_API_KEY env var.
        base_url: Override for EMBEDDING_BASE_URL env var.
        model: Override for EMBEDDING_MODEL env var.

    Returns:
        Embedding vector as a list of floats.
    """
    results = get_embeddings([query], api_key=api_key, base_url=base_url, model=model)
    return results[0]
