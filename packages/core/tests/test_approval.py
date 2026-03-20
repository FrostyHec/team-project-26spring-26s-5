"""Tests for the pending-approval manager."""

import asyncio

import pytest

from agent_core.api.approval import (
    _pending,
    create_pending,
    get_result,
    make_api_approval_handler,
    resolve_pending,
)


class TestPendingApproval:
    """Unit tests for the synchronous approval helpers."""

    def setup_method(self) -> None:
        """Clear pending state before each test."""
        _pending.clear()

    def test_create_pending(self) -> None:
        """Test creating a pending approval entry."""
        event = create_pending("tc_1")
        assert "tc_1" in _pending
        assert not event.is_set()

    def test_resolve_pending_approve(self) -> None:
        """Test resolving a pending approval with approval."""
        create_pending("tc_2")
        ok = resolve_pending("tc_2", approved=True)
        assert ok is True

    def test_resolve_pending_reject(self) -> None:
        """Test resolving a pending approval with rejection."""
        create_pending("tc_3")
        ok = resolve_pending("tc_3", approved=False)
        assert ok is True

    def test_resolve_missing_returns_false(self) -> None:
        """Test resolving a non-existent pending returns False."""
        ok = resolve_pending("unknown_id", approved=True)
        assert ok is False

    def test_get_result_approved(self) -> None:
        """Test retrieving result after approval."""
        create_pending("tc_4")
        resolve_pending("tc_4", approved=True)
        result = get_result("tc_4")
        assert result is True
        # Entry should be removed
        assert "tc_4" not in _pending

    def test_get_result_rejected(self) -> None:
        """Test retrieving result after rejection."""
        create_pending("tc_5")
        resolve_pending("tc_5", approved=False)
        result = get_result("tc_5")
        assert result is False
        assert "tc_5" not in _pending

    def test_get_result_missing_returns_false(self) -> None:
        """Test retrieving result for unknown ID returns False."""
        result = get_result("missing_id")
        assert result is False


class TestMakeApiApprovalHandler:
    """Async tests for the API approval handler."""

    def setup_method(self) -> None:
        """Clear pending state before each test."""
        _pending.clear()

    @pytest.mark.asyncio
    async def test_handler_approved(self) -> None:
        """Test handler returns True when user approves."""

        async def approve_after_delay() -> None:
            await asyncio.sleep(0.05)
            resolve_pending("tc_a", approved=True)

        task = asyncio.create_task(approve_after_delay())
        result = await make_api_approval_handler(
            "get_weather", {"city": "Beijing"}, "tc_a"
        )
        await task
        assert result is True

    @pytest.mark.asyncio
    async def test_handler_rejected(self) -> None:
        """Test handler returns False when user rejects."""

        async def reject_after_delay() -> None:
            await asyncio.sleep(0.05)
            resolve_pending("tc_b", approved=False)

        task = asyncio.create_task(reject_after_delay())
        result = await make_api_approval_handler(
            "get_weather", {"city": "London"}, "tc_b"
        )
        await task
        assert result is False

    @pytest.mark.asyncio
    async def test_handler_timeout(self) -> None:
        """Test handler returns False on timeout."""

        async def fast_timeout_handler(
            tool_name: str,
            tool_args: dict,
            tool_call_id: str,
        ) -> bool:
            event = create_pending(tool_call_id)
            try:
                await asyncio.wait_for(event.wait(), timeout=0.05)
            except TimeoutError:
                _pending.pop(tool_call_id, None)
                return False
            return get_result(tool_call_id)

        result = await fast_timeout_handler(
            "get_weather", {"city": "Tokyo"}, "tc_timeout"
        )
        assert result is False
        assert "tc_timeout" not in _pending
