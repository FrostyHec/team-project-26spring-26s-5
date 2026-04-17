"""Build the policy search FAISS index from PDF files.

Usage:
    python -m agent_core.policy_search.build_index [--pdf-dir PATH] [--output-dir PATH]

Reads all PDFs from the specified directory, chunks them, generates
embeddings via DashScope, and writes a FAISS index to disk.
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from agent_core.policy_search.index import build_index, save_index
from agent_core.policy_search.ingest import ingest_directory

# Project root — two levels up from this file's package
_PROJECT_ROOT = Path(__file__).resolve().parents[5]
_DEFAULT_PDF_DIR = _PROJECT_ROOT / "pdfs"
_DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[3] / "output" / "policy_index"


def main() -> None:
    """Entry point for index building."""
    load_dotenv()

    parser = argparse.ArgumentParser(description="Build policy search index")
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=_DEFAULT_PDF_DIR,
        help=f"Directory containing PDF files (default: {_DEFAULT_PDF_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
        help=f"Output directory for index files (default: {_DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Maximum characters per chunk (default: 500)",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=100,
        help="Character overlap between chunks (default: 100)",
    )
    args = parser.parse_args()

    pdf_dir: Path = args.pdf_dir
    output_dir: Path = args.output_dir

    if not pdf_dir.exists():
        print(f"Error: PDF directory not found: {pdf_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Ingesting PDFs from: {pdf_dir}")
    chunks = ingest_directory(pdf_dir, args.chunk_size, args.chunk_overlap)
    if not chunks:
        print("Error: No chunks produced. Check PDF directory.", file=sys.stderr)
        sys.exit(1)
    print(f"Produced {len(chunks)} chunks from PDFs")

    print("Building FAISS index (this calls the embedding API)...")
    index, ordered_chunks = build_index(chunks)
    print(f"Index built: {index.ntotal} vectors")

    print(f"Saving index to: {output_dir}")
    save_index(index, ordered_chunks, output_dir)
    print("Done! Index saved successfully.")


if __name__ == "__main__":
    main()
