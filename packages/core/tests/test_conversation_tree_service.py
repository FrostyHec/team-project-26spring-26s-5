"""Tests for conversation tree service."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage

from agent_core.models.session import (
    ChatNodeRecord,
    MessageRole,
    MessageStatus,
    NodeSourceKind,
)
from agent_core.persistence.conversation_tree_store import ConversationTreeStore
from agent_core.persistence.session_store import SessionStore
from agent_core.services.conversation_tree_service import ConversationTreeService


def _now() -> datetime:
    return datetime.now(UTC)


@pytest.fixture
async def stores() -> AsyncGenerator[
    tuple[SessionStore, ConversationTreeStore, ConversationTreeService], None
]:
    session_store = SessionStore(":memory:")
    await session_store.initialize()
    tree_store = ConversationTreeStore(":memory:", engine=session_store.db)
    await tree_store.initialize()
    service = ConversationTreeService(session_store, tree_store)
    yield session_store, tree_store, service
    await tree_store.close()
    await session_store.close()


async def _add_node(
    tree_store: ConversationTreeStore, **kwargs: object
) -> ChatNodeRecord:
    node = ChatNodeRecord(**kwargs)
    return await tree_store.add_node(node)


class TestConversationTreeService:
    async def test_prepare_stream_turn_keeps_blank_title_until_first_reply_completes(
        self,
        stores: tuple[SessionStore, ConversationTreeStore, ConversationTreeService],
    ) -> None:
        session_store, _tree_store, service = stores
        session = await session_store.create_session()

        _history, saved_user, placeholder = await service.prepare_stream_turn(
            session.id,
            "What is 2+2?",
        )

        updated = await session_store.get_session(session.id)
        assert updated is not None
        assert updated.title == ""
        assert saved_user.content == "What is 2+2?"
        assert placeholder.status == MessageStatus.STREAMING

    async def test_finalize_stream_turn_keeps_blank_title_until_async_generation_runs(
        self,
        stores: tuple[SessionStore, ConversationTreeStore, ConversationTreeService],
    ) -> None:
        session_store, _tree_store, service = stores
        session = await session_store.create_session()

        _history, _saved_user, placeholder = await service.prepare_stream_turn(
            session.id,
            "What is 2+2?",
        )

        await service.finalize_stream_turn(
            session.id,
            placeholder.id,
            "2+2 equals 4.",
            status=MessageStatus.COMPLETED,
        )

        updated = await session_store.get_session(session.id)
        assert updated is not None
        assert updated.title == ""

    async def test_maybe_generate_first_round_title_uses_separate_llm_request(
        self,
        stores: tuple[SessionStore, ConversationTreeStore, ConversationTreeService],
    ) -> None:
        session_store, _tree_store, service = stores
        session = await session_store.create_session()

        _history, _saved_user, placeholder = await service.prepare_stream_turn(
            session.id,
            "What is 2+2?",
        )
        await service.finalize_stream_turn(
            session.id,
            placeholder.id,
            "2+2 equals 4.",
            status=MessageStatus.COMPLETED,
        )

        llm = AsyncMock()
        llm.ainvoke = AsyncMock(return_value=AIMessage(content='"Simple math help"'))

        generated = await service.maybe_generate_first_round_title(
            session.id,
            placeholder.id,
            llm,
        )

        updated = await session_store.get_session(session.id)
        assert generated == "Simple math help"
        assert updated is not None
        assert updated.title == "Simple math help"
        llm.ainvoke.assert_awaited_once()

    async def test_maybe_generate_first_round_title_strips_reasoning_tags(
        self,
        stores: tuple[SessionStore, ConversationTreeStore, ConversationTreeService],
    ) -> None:
        session_store, _tree_store, service = stores
        session = await session_store.create_session()

        _history, _saved_user, placeholder = await service.prepare_stream_turn(
            session.id,
            "Help me summarize this bug",
        )
        await service.finalize_stream_turn(
            session.id,
            placeholder.id,
            "The bug is caused by leaked reasoning content in title generation.",
            status=MessageStatus.COMPLETED,
        )

        llm = AsyncMock()
        llm.ainvoke = AsyncMock(
            return_value=AIMessage(
                content=(
                    "(<think>The user wants me to generate a short title</think>)\n"
                    "Reasoning leak bug"
                )
            )
        )

        generated = await service.maybe_generate_first_round_title(
            session.id,
            placeholder.id,
            llm,
        )

        updated = await session_store.get_session(session.id)
        assert generated == "Reasoning leak bug"
        assert updated is not None
        assert updated.title == "Reasoning leak bug"

    async def test_build_session_detail_projects_visible_path(
        self,
        stores: tuple[SessionStore, ConversationTreeStore, ConversationTreeService],
    ) -> None:
        session_store, tree_store, service = stores
        session = await session_store.create_session("Tree")

        user_node = await _add_node(
            tree_store,
            id="user-1",
            session_id=session.id,
            parent_id=None,
            role=MessageRole.HUMAN,
            content="hello",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-user-1",
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            created_at=_now(),
            updated_at=_now(),
        )
        assistant_a = await _add_node(
            tree_store,
            id="assistant-1",
            session_id=session.id,
            parent_id=user_node.id,
            role=MessageRole.AI,
            content="answer-a",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-assistant-1",
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            response_to_node_id=user_node.id,
            created_at=_now(),
            updated_at=_now(),
        )
        await _add_node(
            tree_store,
            id="assistant-2",
            session_id=session.id,
            parent_id=user_node.id,
            role=MessageRole.AI,
            content="answer-b",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-assistant-1",
            version_index=1,
            source_kind=NodeSourceKind.RETRY,
            source_node_id=assistant_a.id,
            response_to_node_id=user_node.id,
            created_at=_now(),
            updated_at=_now(),
        )
        await session_store.update_current_leaf(session.id, assistant_a.id)

        detail = await service.build_session_detail(session.id)
        assert detail is not None
        assert detail.visible_path == ["user-1", "assistant-1"]
        assert [message.content for message in detail.messages] == ["hello", "answer-a"]
        assert len(detail.version_groups) == 1
        assert detail.version_groups[0].selected_node_id == "assistant-1"

    async def test_select_version_restores_saved_bookmark(
        self,
        stores: tuple[SessionStore, ConversationTreeStore, ConversationTreeService],
    ) -> None:
        session_store, tree_store, service = stores
        session = await session_store.create_session("Bookmarks")

        user = await _add_node(
            tree_store,
            id="user-1",
            session_id=session.id,
            parent_id=None,
            role=MessageRole.HUMAN,
            content="hello",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-user-1",
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            created_at=_now(),
            updated_at=_now(),
        )
        assistant_v1 = await _add_node(
            tree_store,
            id="assistant-1",
            session_id=session.id,
            parent_id=user.id,
            role=MessageRole.AI,
            content="branch-a",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-assistant-1",
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            response_to_node_id=user.id,
            created_at=_now(),
            updated_at=_now(),
        )
        assistant_v2 = await _add_node(
            tree_store,
            id="assistant-2",
            session_id=session.id,
            parent_id=user.id,
            role=MessageRole.AI,
            content="branch-b",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-assistant-1",
            version_index=1,
            source_kind=NodeSourceKind.RETRY,
            source_node_id=assistant_v1.id,
            response_to_node_id=user.id,
            created_at=_now(),
            updated_at=_now(),
        )
        follow_up_user = await _add_node(
            tree_store,
            id="user-2",
            session_id=session.id,
            parent_id=assistant_v1.id,
            role=MessageRole.HUMAN,
            content="follow up",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-user-2",
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            created_at=_now(),
            updated_at=_now(),
        )
        assistant_leaf = await _add_node(
            tree_store,
            id="assistant-3",
            session_id=session.id,
            parent_id=follow_up_user.id,
            role=MessageRole.AI,
            content="leaf",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-assistant-2",
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            response_to_node_id=follow_up_user.id,
            created_at=_now(),
            updated_at=_now(),
        )
        await session_store.update_current_leaf(session.id, assistant_leaf.id)

        switched = await service.select_version(
            session.id,
            "vg-assistant-1",
            assistant_v2.id,
        )
        assert switched is not None
        assert switched.session.current_leaf_node_id == assistant_v2.id
        assert switched.visible_path == ["user-1", "assistant-2"]

        restored = await service.select_version(
            session.id,
            "vg-assistant-1",
            assistant_v1.id,
        )
        assert restored is not None
        assert restored.session.current_leaf_node_id == assistant_leaf.id
        assert restored.visible_path == [
            "user-1",
            "assistant-1",
            "user-2",
            "assistant-3",
        ]

    async def test_retry_assistant_creates_streaming_sibling(
        self,
        stores: tuple[SessionStore, ConversationTreeStore, ConversationTreeService],
    ) -> None:
        session_store, tree_store, service = stores
        session = await session_store.create_session("Retry")
        user = await _add_node(
            tree_store,
            id="user-1",
            session_id=session.id,
            parent_id=None,
            role=MessageRole.HUMAN,
            content="hello",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-user-1",
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            created_at=_now(),
            updated_at=_now(),
        )
        assistant = await _add_node(
            tree_store,
            id="assistant-1",
            session_id=session.id,
            parent_id=user.id,
            role=MessageRole.AI,
            content="answer",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-assistant-1",
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            response_to_node_id=user.id,
            created_at=_now(),
            updated_at=_now(),
        )
        await session_store.update_current_leaf(session.id, assistant.id)

        detail = await service.retry_assistant(session.id, assistant.id)
        assert detail is not None
        assert detail.session.current_leaf_node_id is not None
        assert detail.visible_path[0] == user.id
        assert detail.messages[-1].status == MessageStatus.STREAMING

    async def test_retry_assistant_preserves_original_branch_bookmark(
        self,
        stores: tuple[SessionStore, ConversationTreeStore, ConversationTreeService],
    ) -> None:
        session_store, tree_store, service = stores
        session = await session_store.create_session("Retry bookmark")
        user = await _add_node(
            tree_store,
            id="user-1",
            session_id=session.id,
            parent_id=None,
            role=MessageRole.HUMAN,
            content="hello",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-user-1",
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            created_at=_now(),
            updated_at=_now(),
        )
        assistant = await _add_node(
            tree_store,
            id="assistant-1",
            session_id=session.id,
            parent_id=user.id,
            role=MessageRole.AI,
            content="answer",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-assistant-1",
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            response_to_node_id=user.id,
            created_at=_now(),
            updated_at=_now(),
        )
        follow_up_user = await _add_node(
            tree_store,
            id="user-2",
            session_id=session.id,
            parent_id=assistant.id,
            role=MessageRole.HUMAN,
            content="follow up",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-user-2",
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            created_at=_now(),
            updated_at=_now(),
        )
        follow_up_assistant = await _add_node(
            tree_store,
            id="assistant-2",
            session_id=session.id,
            parent_id=follow_up_user.id,
            role=MessageRole.AI,
            content="leaf",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-assistant-2",
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            response_to_node_id=follow_up_user.id,
            created_at=_now(),
            updated_at=_now(),
        )
        await session_store.update_current_leaf(session.id, follow_up_assistant.id)

        retried = await service.retry_assistant(session.id, assistant.id)
        assert retried is not None
        retry_node_id = retried.session.current_leaf_node_id
        assert retry_node_id is not None
        assert retry_node_id != assistant.id

        restored = await service.select_version(
            session.id,
            assistant.version_group_id,
            assistant.id,
        )
        assert restored is not None
        assert restored.session.current_leaf_node_id == follow_up_assistant.id
        assert restored.visible_path == [
            user.id,
            assistant.id,
            follow_up_user.id,
            follow_up_assistant.id,
        ]

    async def test_edit_user_creates_placeholder_and_failures_can_set_failed(
        self,
        stores: tuple[SessionStore, ConversationTreeStore, ConversationTreeService],
    ) -> None:
        session_store, tree_store, service = stores
        session = await session_store.create_session("Edit user")
        user = await _add_node(
            tree_store,
            id="user-1",
            session_id=session.id,
            parent_id=None,
            role=MessageRole.HUMAN,
            content="hello",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-user-1",
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            created_at=_now(),
            updated_at=_now(),
        )
        await session_store.update_current_leaf(session.id, user.id)

        detail = await service.edit_user(session.id, user.id, "edited")
        assert detail is not None
        assert detail.messages[0].content == "edited"
        placeholder_id = detail.session.current_leaf_node_id
        assert placeholder_id is not None

        failed = await service.fail_stream_placeholder(
            session.id, placeholder_id, "llm failed"
        )
        assert failed is not None
        assert failed.status == MessageStatus.FAILED
        assert failed.content == "llm failed"

    async def test_edit_user_preserves_original_branch_bookmark(
        self,
        stores: tuple[SessionStore, ConversationTreeStore, ConversationTreeService],
    ) -> None:
        session_store, tree_store, service = stores
        session = await session_store.create_session("Edit user bookmark")
        user = await _add_node(
            tree_store,
            id="user-1",
            session_id=session.id,
            parent_id=None,
            role=MessageRole.HUMAN,
            content="hello",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-user-1",
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            created_at=_now(),
            updated_at=_now(),
        )
        assistant = await _add_node(
            tree_store,
            id="assistant-1",
            session_id=session.id,
            parent_id=user.id,
            role=MessageRole.AI,
            content="answer",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-assistant-1",
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            response_to_node_id=user.id,
            created_at=_now(),
            updated_at=_now(),
        )
        follow_up_user = await _add_node(
            tree_store,
            id="user-2",
            session_id=session.id,
            parent_id=assistant.id,
            role=MessageRole.HUMAN,
            content="follow up",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-user-2",
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            created_at=_now(),
            updated_at=_now(),
        )
        follow_up_assistant = await _add_node(
            tree_store,
            id="assistant-2",
            session_id=session.id,
            parent_id=follow_up_user.id,
            role=MessageRole.AI,
            content="leaf",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-assistant-2",
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            response_to_node_id=follow_up_user.id,
            created_at=_now(),
            updated_at=_now(),
        )
        await session_store.update_current_leaf(session.id, follow_up_assistant.id)

        edited = await service.edit_user(session.id, user.id, "edited root")
        assert edited is not None
        assert edited.visible_path[0] != user.id

        restored = await service.select_version(
            session.id,
            user.version_group_id,
            user.id,
        )
        assert restored is not None
        assert restored.session.current_leaf_node_id == follow_up_assistant.id
        assert restored.visible_path == [
            user.id,
            assistant.id,
            follow_up_user.id,
            follow_up_assistant.id,
        ]

    async def test_edit_assistant_preserves_original_branch_bookmark(
        self,
        stores: tuple[SessionStore, ConversationTreeStore, ConversationTreeService],
    ) -> None:
        session_store, tree_store, service = stores
        session = await session_store.create_session("Edit assistant bookmark")
        user = await _add_node(
            tree_store,
            id="user-1",
            session_id=session.id,
            parent_id=None,
            role=MessageRole.HUMAN,
            content="hello",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-user-1",
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            created_at=_now(),
            updated_at=_now(),
        )
        assistant = await _add_node(
            tree_store,
            id="assistant-1",
            session_id=session.id,
            parent_id=user.id,
            role=MessageRole.AI,
            content="answer",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-assistant-1",
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            response_to_node_id=user.id,
            created_at=_now(),
            updated_at=_now(),
        )
        follow_up_user = await _add_node(
            tree_store,
            id="user-2",
            session_id=session.id,
            parent_id=assistant.id,
            role=MessageRole.HUMAN,
            content="follow up",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-user-2",
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            created_at=_now(),
            updated_at=_now(),
        )
        follow_up_assistant = await _add_node(
            tree_store,
            id="assistant-2",
            session_id=session.id,
            parent_id=follow_up_user.id,
            role=MessageRole.AI,
            content="leaf",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-assistant-2",
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            response_to_node_id=follow_up_user.id,
            created_at=_now(),
            updated_at=_now(),
        )
        await session_store.update_current_leaf(session.id, follow_up_assistant.id)

        edited = await service.edit_assistant(session.id, assistant.id, "edited answer")
        assert edited is not None
        assert edited.visible_path[1] != assistant.id

        restored = await service.select_version(
            session.id,
            assistant.version_group_id,
            assistant.id,
        )
        assert restored is not None
        assert restored.session.current_leaf_node_id == follow_up_assistant.id
        assert restored.visible_path == [
            user.id,
            assistant.id,
            follow_up_user.id,
            follow_up_assistant.id,
        ]

    async def test_prepare_and_finalize_stream_turn(
        self,
        stores: tuple[SessionStore, ConversationTreeStore, ConversationTreeService],
    ) -> None:
        session_store, tree_store, service = stores
        session = await session_store.create_session("Stream")
        history, user_node, placeholder = await service.prepare_stream_turn(
            session.id,
            "hello",
        )

        assert history == []
        assert user_node.role == MessageRole.HUMAN
        assert placeholder.parent_id == user_node.id
        assert placeholder.status == MessageStatus.STREAMING

        finalized = await service.finalize_stream_turn(
            session.id,
            placeholder.id,
            "final answer",
            tool_calls=[
                {
                    "name": "calculator",
                    "input": {"expression": "1+2"},
                    "output": "3",
                    "status": "completed",
                }
            ],
            trace_steps=[
                {"type": "loop_start"},
                {
                    "type": "tool_start",
                    "name": "calculator",
                    "input": {"expression": "1+2"},
                },
                {
                    "type": "tool_end",
                    "name": "calculator",
                    "output": "3",
                },
                {"type": "loop_end"},
            ],
        )
        assert finalized is not None
        assert finalized.status == MessageStatus.COMPLETED
        assert finalized.content == "final answer"
        assert finalized.tool_calls is not None
        assert finalized.tool_calls[0]["name"] == "calculator"
        assert finalized.trace_steps is not None
        assert finalized.trace_steps[-1]["type"] == "loop_end"

        detail = await service.build_session_detail(session.id)
        assert detail is not None
        assert [message.content for message in detail.messages] == [
            "hello",
            "final answer",
        ]
        assistant_node = next(
            node for node in detail.nodes if node.id == placeholder.id
        )
        assert assistant_node.tool_calls is not None
        assert assistant_node.tool_calls[0]["output"] == "3"
        assert assistant_node.trace_steps is not None
        assert assistant_node.trace_steps[1]["type"] == "tool_start"

        placeholder_stream = await service.prepare_placeholder_stream(session.id)
        assert placeholder_stream is None

    async def test_prepare_placeholder_stream_uses_existing_streaming_leaf(
        self,
        stores: tuple[SessionStore, ConversationTreeStore, ConversationTreeService],
    ) -> None:
        session_store, _tree_store, service = stores
        session = await session_store.create_session("Pending")
        _history, _user_node, placeholder = await service.prepare_stream_turn(
            session.id,
            "hello",
        )

        prepared = await service.prepare_placeholder_stream(session.id)
        assert prepared is not None
        history_messages, prepared_placeholder = prepared
        assert prepared_placeholder.id == placeholder.id
        assert len(history_messages) == 1
        assert history_messages[0].content == "hello"
