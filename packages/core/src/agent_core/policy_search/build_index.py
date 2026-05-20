"""Build the policy search FAISS index from PDF files.

Usage:
    python -m agent_core.policy_search.build_index [--pdf-dir PATH] [--output-dir PATH]

Reads all PDFs from the specified directory, chunks them, generates
embeddings via DashScope, and writes a FAISS index to disk.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from agent_core.policy_search.config import PolicySearchConfig
from agent_core.policy_search.index import build_index, save_index
from agent_core.policy_search.ingest import ingest_directory


@dataclass(frozen=True)
class PolicyIndexBuildResult:
    """Summary of a completed policy index build."""

    pdf_dir: Path
    output_dir: Path
    chunk_count: int
    vector_count: int


def rebuild_policy_index(
    config: PolicySearchConfig | None = None,
    pdf_dir: Path | None = None,
    output_dir: Path | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> PolicyIndexBuildResult:
    """Build and save the policy search index.

    This function is the shared implementation used by both the standalone
    module entry point and the main ``agent-cli`` command.

    Args:
        config: Base policy search config. Defaults to environment config.
        pdf_dir: Optional source PDF directory override.
        output_dir: Optional index output directory override.
        chunk_size: Optional maximum characters per text chunk override.
        chunk_overlap: Optional character overlap between chunks override.

    Returns:
        A build summary with chunk and vector counts.

    Raises:
        FileNotFoundError: If *pdf_dir* does not exist.
        ValueError: If no chunks can be produced from the PDFs.
    """
    build_config = (config or PolicySearchConfig.from_env()).with_overrides(
        pdf_dir=pdf_dir,
        index_dir=output_dir,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    if not build_config.pdf_dir.exists():
        raise FileNotFoundError(f"PDF directory not found: {build_config.pdf_dir}")

    chunks = ingest_directory(
        build_config.pdf_dir,
        build_config.chunk_size,
        build_config.chunk_overlap,
    )
    if not chunks:
        raise ValueError("No chunks produced. Check PDF directory.")

    index, ordered_chunks = build_index(chunks)
    save_index(index, ordered_chunks, build_config.index_dir)

    return PolicyIndexBuildResult(
        pdf_dir=build_config.pdf_dir,
        output_dir=build_config.index_dir,
        chunk_count=len(ordered_chunks),
        vector_count=int(index.ntotal),
    )


def main() -> None:
    """Entry point for index building."""
    load_dotenv()
    config = PolicySearchConfig.from_env()

    parser = argparse.ArgumentParser(description="Build policy search index")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Path to a .env file for runtime configuration",
    )
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=None,
        help=f"Directory containing PDF files (default: {config.pdf_dir})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=f"Output directory for index files (default: {config.index_dir})",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help=f"Maximum characters per chunk (default: {config.chunk_size})",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=None,
        help=f"Character overlap between chunks (default: {config.chunk_overlap})",
    )
    args = parser.parse_args()

    if args.env_file is not None:
        from agent_core.runtime_paths import set_runtime_env_file

        set_runtime_env_file(args.env_file)
        load_dotenv(args.env_file, override=True)
        config = PolicySearchConfig.from_env()

    build_config = config.with_overrides(
        pdf_dir=args.pdf_dir,
        index_dir=args.output_dir,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

    print(f"Ingesting PDFs from: {build_config.pdf_dir}")
    print("Building FAISS index (this calls the embedding API)...")
    try:
        result = rebuild_policy_index(config=build_config)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Produced {result.chunk_count} chunks from PDFs")
    print(f"Index built: {result.vector_count} vectors")
    print(f"Index saved to: {result.output_dir}")
    print("Done! Index saved successfully.")


if __name__ == "__main__":
    main()
