"""PDF ingestion — parse PDFs and produce text chunks with metadata.

Uses PyMuPDF (fitz) for PDF text extraction. Chunks are created using
fixed-length splitting with overlap to preserve context at boundaries.
"""

import hashlib
import json
import re
from pathlib import Path

import fitz  # PyMuPDF

from agent_core.logging_utils import get_logger
from agent_core.policy_search.models import ChunkMetadata, TextChunk

logger = get_logger("policy_search.ingest")

# Chunking defaults
DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 100

# Cached compiled patterns from patterns.json
_PATTERNS: list[re.Pattern] | None = None


def _load_patterns() -> list[re.Pattern]:
    """Load section heading patterns from patterns.json."""
    pattern_file = Path(__file__).parent / "patterns.json"
    with open(pattern_file, encoding="utf-8") as f:
        data = json.load(f)
    return [re.compile(p) for p in data["section_heading_patterns"]]


def _get_patterns() -> list[re.Pattern]:
    """Get cached compiled patterns."""
    global _PATTERNS
    if _PATTERNS is None:
        _PATTERNS = _load_patterns()
    return _PATTERNS


def _generate_doc_id(path: Path) -> str:
    """Generate a stable document ID from the file path."""
    return hashlib.md5(str(path.name).encode()).hexdigest()[:12]


def _extract_title_from_filename(path: Path) -> str:
    """Derive a human-readable title from the PDF filename.

    Strips leading numbers and hyphens (e.g. '00-CourseGuide.pdf' -> 'CourseGuide').
    """
    stem = path.stem
    cleaned = re.sub(r"^\d+[-_\s]*", "", stem)
    return cleaned or stem


def _detect_section_heading(text: str) -> str:
    """Detect a section heading from the beginning of a text block.

    Matches patterns defined in patterns.json (Chinese heading conventions
    like chapter numbers, section markers, etc.).
    """
    lines = text.strip().split("\n")
    if not lines:
        return ""

    first_line = lines[0].strip()
    for pattern in _get_patterns():
        if pattern.match(first_line):
            return first_line[:50]
    return ""


def parse_pdf(path: Path) -> list[dict[str, str | int]]:
    """Extract text from a PDF file, returning page-level text blocks.

    Args:
        path: Path to the PDF file.

    Returns:
        List of dicts with keys 'text' and 'page' (1-based).
    """
    pages: list[dict[str, str | int]] = []
    with fitz.open(str(path)) as doc:
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            if text.strip():
                pages.append({"text": text, "page": page_num + 1})
    logger.info("Parsed %d non-empty pages from %s", len(pages), path.name)
    return pages


def chunk_text(
    pages: list[dict[str, str | int]],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict[str, str | int]]:
    """Split page-level text into fixed-length chunks with overlap.

    Each chunk retains its originating page number. When a chunk spans
    a page boundary, the page of the chunk's starting character is used.

    Args:
        pages: Output from :func:`parse_pdf`.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Character overlap between consecutive chunks.

    Returns:
        List of dicts with keys 'text', 'page', 'section'.
    """
    chunks: list[dict[str, str | int]] = []
    buffer = ""
    buffer_spans: list[dict[str, int]] = []

    for page_data in pages:
        text = str(page_data["text"])
        page = int(page_data["page"])

        if not buffer:
            current_page = page

        start = len(buffer)
        buffer += text
        buffer_spans.append({"start": start, "end": len(buffer), "page": page})

        while len(buffer) >= chunk_size:
            chunk_text_content = buffer[:chunk_size]
            section = _detect_section_heading(chunk_text_content)
            # Use the page of the chunk's starting character
            chunk_page = buffer_spans[0]["page"] if buffer_spans else current_page
            chunks.append(
                {
                    "text": chunk_text_content,
                    "page": chunk_page,
                    "section": section,
                }
            )

            consumed = chunk_size - chunk_overlap
            buffer = buffer[consumed:]

            # Remove spans that are fully consumed
            updated_spans: list[dict[str, int]] = []
            for span in buffer_spans:
                if span["end"] <= consumed:
                    continue
                updated_spans.append(
                    {
                        "start": max(0, span["start"] - consumed),
                        "end": span["end"] - consumed,
                        "page": span["page"],
                    }
                )
            buffer_spans = updated_spans

    # Flush remaining buffer
    if buffer.strip():
        section = _detect_section_heading(buffer)
        chunk_page = buffer_spans[0]["page"] if buffer_spans else current_page
        chunks.append(
            {
                "text": buffer,
                "page": chunk_page,
                "section": section,
            }
        )

    logger.info(
        "Produced %d chunks (size=%d, overlap=%d)",
        len(chunks),
        chunk_size,
        chunk_overlap,
    )
    return chunks


def ingest_pdf(
    path: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[TextChunk]:
    """Full ingestion pipeline for a single PDF.

    Args:
        path: Path to the PDF file.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Overlap between consecutive chunks.

    Returns:
        List of :class:`TextChunk` instances ready for embedding.
    """
    doc_id = _generate_doc_id(path)
    title = _extract_title_from_filename(path)
    pages = parse_pdf(path)
    raw_chunks = chunk_text(pages, chunk_size, chunk_overlap)

    text_chunks: list[TextChunk] = []
    for i, raw in enumerate(raw_chunks):
        chunk_id = f"{doc_id}_{i:04d}"
        metadata = ChunkMetadata(
            doc_id=doc_id,
            title=title,
            page=int(raw["page"]),
            section=str(raw.get("section", "")),
            source_path=str(path),
        )
        text_chunks.append(
            TextChunk(
                chunk_id=chunk_id,
                text=str(raw["text"]),
                metadata=metadata,
            )
        )

    logger.info(
        "Ingested %s: %d chunks (doc_id=%s)", path.name, len(text_chunks), doc_id
    )
    return text_chunks


def ingest_directory(
    directory: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[TextChunk]:
    """Ingest all PDF files in a directory.

    Args:
        directory: Path to directory containing PDF files.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Overlap between consecutive chunks.

    Returns:
        Combined list of :class:`TextChunk` from all PDFs.
    """
    all_chunks: list[TextChunk] = []
    pdf_files = sorted(directory.glob("*.pdf"))
    if not pdf_files:
        logger.warning("No PDF files found in %s", directory)
        return all_chunks

    for pdf_path in pdf_files:
        chunks = ingest_pdf(pdf_path, chunk_size, chunk_overlap)
        all_chunks.extend(chunks)

    logger.info(
        "Ingested %d PDFs, total %d chunks from %s",
        len(pdf_files),
        len(all_chunks),
        directory,
    )
    return all_chunks
