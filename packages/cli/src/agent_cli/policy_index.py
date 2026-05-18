"""Policy search index CLI actions."""

import sys


def build_policy_index() -> None:
    """Build the policy search index using configured policy search settings."""
    from agent_core.policy_search.build_index import rebuild_policy_index
    from agent_core.policy_search.config import PolicySearchConfig
    from dotenv import load_dotenv

    load_dotenv()
    config = PolicySearchConfig.from_env()

    try:
        result = rebuild_policy_index(config=config)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Policy index built successfully: {result.vector_count} vectors")
    print(f"Chunks: {result.chunk_count}")
    print(f"PDF directory: {result.pdf_dir}")
    print(f"Output directory: {result.output_dir}")
