"""Pending approval manager for Human-in-the-Loop tool execution.

Bridges the SSE streaming endpoint and the approval REST endpoint
using :class:`asyncio.Event` synchronisation primitives so that
``_execute_tools`` can pause while waiting for the user to approve
or reject a sensitive tool invocation from the Vue GUI.
"""

from __future__ import annotations

import asyncio
from typing import Any

from agent_core.logging_utils import get_logger

logger = get_logger("api.approval")

# Global registry of pending approvals keyed by tool_call_id.
# Each entry is a tuple of (asyncio.Event, result: bool | None).
_pending: dict[str, tuple[asyncio.Event, list[bool]]] = {}


def create_pending(tool_call_id: str) -> asyncio.Event:
    """Register a pending approval for a tool call.

    Args:
        tool_call_id: Unique identifier for the tool invocation.

    Returns:
        An asyncio Event that will be set when the user responds.
    """
    event = asyncio.Event()
    _pending[tool_call_id] = (event, [])
    logger.debug(f"Created pending approval: {tool_call_id}")
    return event


def resolve_pending(tool_call_id: str, approved: bool) -> bool:
    """Resolve a pending approval with the user's decision.

    Args:
        tool_call_id: Unique identifier for the tool invocation.
        approved: Whether the user approved the tool call.

    Returns:
        True if the pending approval was found and resolved.
    """
    entry = _pending.get(tool_call_id)
    if entry is None:
        logger.warning(f"No pending approval found: {tool_call_id}")
        return False

    event, result_list = entry
    result_list.append(approved)
    event.set()
    logger.debug(f"Resolved pending approval: {tool_call_id} -> {approved}")
    return True


def get_result(tool_call_id: str) -> bool:
    """Retrieve the approval result and clean up.

    Args:
        tool_call_id: Unique identifier for the tool invocation.

    Returns:
        True if approved, False if rejected.
    """
    entry = _pending.pop(tool_call_id, None)
    if entry is None:
        return False
    _, result_list = entry
    return bool(result_list and result_list[0])


async def make_api_approval_handler(
    tool_name: str,
    tool_args: dict[str, Any],
    tool_call_id: str,
) -> bool:
    """Approval handler for the API/Vue frontend.

    Creates a pending approval, waits for the user to respond via
    the ``/chat/approve`` endpoint, then returns the decision.

    Args:
        tool_name: Name of the sensitive tool.
        tool_args: Arguments the LLM wants to pass.
        tool_call_id: Unique ID for this tool invocation.

    Returns:
        True if user approved, False otherwise.
    """
    event = create_pending(tool_call_id)

    # Wait up to 120 seconds for user response
    try:
        await asyncio.wait_for(event.wait(), timeout=120.0)
    except TimeoutError:
        logger.warning(f"Approval timed out: {tool_call_id}")
        _pending.pop(tool_call_id, None)
        return False

    return get_result(tool_call_id)
