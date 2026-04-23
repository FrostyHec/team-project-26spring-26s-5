"""Data models for policy search — chunk metadata and retrieval results."""

from pydantic import BaseModel


class ChunkMetadata(BaseModel):
    """Metadata attached to each text chunk extracted from a PDF.

    Attributes:
        doc_id: Unique identifier for the source document.
        title: Document title (derived from filename or content).
        page: 1-based page number where the chunk originates.
        section: Detected section/chapter heading, if available.
        source_path: Relative path to the original PDF file.
        official_url: Optional URL to the official online version.
    """

    doc_id: str
    title: str
    page: int
    section: str = ""
    source_path: str = ""
    official_url: str = ""


class TextChunk(BaseModel):
    """A single text chunk with its metadata.

    Attributes:
        chunk_id: Globally unique identifier for this chunk.
        text: The actual text content of the chunk.
        metadata: Source and location metadata.
    """

    chunk_id: str
    text: str
    metadata: ChunkMetadata


class RetrievalResult(BaseModel):
    """A single retrieval result returned by the policy search retriever.

    Attributes:
        snippet: The matched text snippet.
        score: Similarity score (lower = more similar for L2 distance).
        title: Document title.
        page: Page number in the source document.
        section: Section heading, if available.
        source_path: Path to the original PDF.
        official_url: Optional URL to the official source.
        chunk_id: The chunk identifier for traceability.
    """

    snippet: str
    score: float
    title: str = ""
    page: int = 0
    section: str = ""
    source_path: str = ""
    official_url: str = ""
    chunk_id: str = ""
