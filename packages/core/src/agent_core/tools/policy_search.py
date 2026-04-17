"""Policy search tool — exposes campus policy retrieval to the ReAct agent.

Registers ``search_campus_policy`` as a SAFE tool via the standard
``register_*_tools(registry)`` convention for auto-discovery.
"""

from typing import Any

from agent_core.logging_utils import get_logger
from agent_core.policy_search.retriever import format_results_for_llm, search
from agent_core.tools.registry import ToolRegistry, ToolSensitivity

logger = get_logger("tools.policy_search")


def search_campus_policy(query: str) -> str:
    """Search campus policy documents for information relevant to the query.

    Uses vector similarity search over pre-indexed PDF documents to find
    the most relevant policy content. Returns formatted results with
    source citations that can be referenced as ``[source n]``.

    Args:
        query: Natural language question about campus policies,
            regulations, curriculum requirements, or academic procedures.

    Returns:
        Formatted search results with snippets and citation references,
        or a message indicating no relevant content was found.
    """
    try:
        results = search(query, top_k=5)
        formatted = format_results_for_llm(results)
        logger.info("Policy search for '%s': %d results", query[:50], len(results))
        return formatted
    except FileNotFoundError:
        logger.warning("Policy index not found — has it been built?")
        return "Policy index not built. Run the build script first."  # nosemgrep
    except ValueError as exc:
        logger.error("Policy search configuration error: %s", exc)
        return f"Policy search config error: {exc}"  # nosemgrep
    except Exception as exc:
        logger.error("Policy search failed: %s", exc, exc_info=True)
        return f"Policy search error: {exc}"  # nosemgrep


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_TOOL_DESCRIPTIONS: list[tuple[Any, str, ToolSensitivity]] = [
    (
        search_campus_policy,
        "Search campus policy documents for information about university "
        "regulations, curriculum requirements, academic procedures, course "
        "plans, graduation requirements, and other campus policies. "
        "Pass a natural language query in Chinese. Returns relevant excerpts "
        "with source citations in ``[source n]`` format. "
        "ALWAYS call this tool when the user asks about campus policies, "
        "academic regulations, or curriculum requirements.",
        ToolSensitivity.SAFE,
    ),
]


def register_policy_search_tools(registry: ToolRegistry) -> None:
    """Register all policy search tools with the given registry."""
    for func, description, sensitivity in _TOOL_DESCRIPTIONS:
        registry.add_tool(func=func, description=description, sensitivity=sensitivity)
