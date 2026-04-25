"""Tests for conversation tree persistence."""

from datetime import UTC, datetime

import pytest

from agent_core.models.session import (
    ChatNodeRecord,
    MessageRole,
    MessageStatus,
    NodeLeafBookmarkRecord,
    NodeSourceKind,
    VersionGroupSelectionRecord,
)
from agent_core.persistence.conversation_tree_store import ConversationTreeStore
from agent_core.persistence.session_store import SessionStore


def _now() -> datetime:
    return datetime.now(UTC)


@pytest.fixture
async def store() -> ConversationTreeStore:
    session_store = SessionStore(":memory:")
    await session_store.initialize()
    await session_store.create_session_with_id("session-1", "Tree")
    tree_store = ConversationTreeStore(":memory:", engine=session_store.db)
    await tree_store.initialize()
    yield tree_store
    await tree_store.close()
    await session_store.close()


class TestConversationTreeStore:
    async def test_add_and_list_nodes(self, store: ConversationTreeStore) -> None:
        node = ChatNodeRecord(
            id="node-1",
            session_id="session-1",
            role=MessageRole.HUMAN,
            content="hello",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-user-1",
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            created_at=_now(),
            updated_at=_now(),
        )
        await store.add_node(node)

        nodes = await store.list_nodes("session-1")
        assert len(nodes) == 1
        assert nodes[0].id == "node-1"
        assert nodes[0].content == "hello"

    async def test_upsert_version_selection(self, store: ConversationTreeStore) -> None:
        await store.upsert_version_selection(
            VersionGroupSelectionRecord(
                session_id="session-1",
                version_group_id="vg-1",
                selected_node_id="node-1",
            )
        )
        await store.upsert_version_selection(
            VersionGroupSelectionRecord(
                session_id="session-1",
                version_group_id="vg-1",
                selected_node_id="node-2",
            )
        )

        selection = await store.get_version_selection("session-1", "vg-1")
        assert selection is not None
        assert selection.selected_node_id == "node-2"

    async def test_upsert_node_bookmark(self, store: ConversationTreeStore) -> None:
        await store.add_node(
            ChatNodeRecord(
                id="node-1",
                session_id="session-1",
                role=MessageRole.HUMAN,
                content="hello",
                status=MessageStatus.COMPLETED,
                version_group_id="vg-user-1",
                version_index=0,
                source_kind=NodeSourceKind.INITIAL,
                created_at=_now(),
                updated_at=_now(),
            )
        )
        await store.upsert_node_bookmark(
            NodeLeafBookmarkRecord(
                session_id="session-1",
                node_id="node-1",
                selected_leaf_id="leaf-1",
            )
        )
        await store.upsert_node_bookmark(
            NodeLeafBookmarkRecord(
                session_id="session-1",
                node_id="node-1",
                selected_leaf_id="leaf-2",
            )
        )

        bookmark = await store.get_node_bookmark("session-1", "node-1")
        assert bookmark is not None
        assert bookmark.selected_leaf_id == "leaf-2"

    async def test_add_versioned_node_retries_on_conflict(
        self,
        store: ConversationTreeStore,
    ) -> None:
        first = ChatNodeRecord(
            id="node-1",
            session_id="session-1",
            role=MessageRole.AI,
            content="first",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-a-1",
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            created_at=_now(),
            updated_at=_now(),
        )
        await store.add_node(first)

        conflicting = ChatNodeRecord(
            id="node-2",
            session_id="session-1",
            role=MessageRole.AI,
            content="second",
            status=MessageStatus.COMPLETED,
            version_group_id="vg-a-1",
            version_index=0,
            source_kind=NodeSourceKind.RETRY,
            created_at=_now(),
            updated_at=_now(),
        )
        saved = await store.add_versioned_node(conflicting)
        assert saved.version_index == 1
