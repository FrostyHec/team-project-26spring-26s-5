"""Tests for SessionStore — SQLite-backed session and message CRUD."""


import pytest

from agent_core.models.session import MessageRecord, MessageRole
from agent_core.persistence.session_store import SessionStore


@pytest.fixture
async def store() -> SessionStore:
    """Create an in-memory SessionStore for testing."""
    s = SessionStore(":memory:")
    await s.initialize()
    yield s
    await s.close()


# ---- Session CRUD ----


class TestSessionCRUD:
    """Test session create / read / list / delete."""

    async def test_create_and_get(self, store: SessionStore) -> None:
        """Creating a session should make it retrievable."""
        session = await store.create_session("Test Session")
        assert session.title == "Test Session"
        assert session.is_active is True

        fetched = await store.get_session(session.id)
        assert fetched is not None
        assert fetched.id == session.id
        assert fetched.title == "Test Session"

    async def test_create_with_id(self, store: SessionStore) -> None:
        """create_session_with_id should use the provided ID."""
        session = await store.create_session_with_id("custom-id", "Custom")
        assert session.id == "custom-id"
        assert session.title == "Custom"

        fetched = await store.get_session("custom-id")
        assert fetched is not None

    async def test_list_sessions_empty(self, store: SessionStore) -> None:
        """Listing with no sessions returns empty list."""
        sessions = await store.list_sessions()
        assert sessions == []

    async def test_list_sessions_returns_summaries(self, store: SessionStore) -> None:
        """Listing sessions returns summaries with message count."""
        s1 = await store.create_session("First")
        await store.create_session("Second")

        # Add a message to s1
        await store.add_message(
            MessageRecord(
                session_id=s1.id,
                role=MessageRole.HUMAN,
                content="hello",
                ordinal=0,
            )
        )

        summaries = await store.list_sessions()
        assert len(summaries) == 2

        first_summary = next(s for s in summaries if s.id == s1.id)
        assert first_summary.message_count == 1
        assert first_summary.title == "First"

    async def test_delete_session_soft(self, store: SessionStore) -> None:
        """Deleting a session soft-deletes it (not retrievable)."""
        session = await store.create_session("To Delete")
        deleted = await store.delete_session(session.id)
        assert deleted is True

        fetched = await store.get_session(session.id)
        assert fetched is None

    async def test_delete_nonexistent_returns_false(self, store: SessionStore) -> None:
        """Deleting a non-existent session returns False."""
        deleted = await store.delete_session("no-such-id")
        assert deleted is False

    async def test_get_nonexistent_returns_none(self, store: SessionStore) -> None:
        """Getting a non-existent session returns None."""
        result = await store.get_session("nonexistent")
        assert result is None


# ---- Message persistence ----


class TestMessagePersistence:
    """Test message add / get / ordering."""

    async def test_add_and_get_messages(self, store: SessionStore) -> None:
        """Messages should round-trip through add/get."""
        session = await store.create_session()
        msg = MessageRecord(
            session_id=session.id,
            role=MessageRole.HUMAN,
            content="Hello, agent!",
            ordinal=0,
        )
        saved = await store.add_message(msg)
        assert saved.id is not None

        messages = await store.get_messages(session.id)
        assert len(messages) == 1
        assert messages[0].content == "Hello, agent!"
        assert messages[0].role == MessageRole.HUMAN

    async def test_messages_ordered_by_ordinal(self, store: SessionStore) -> None:
        """Messages should be returned in ordinal order."""
        session = await store.create_session()
        for i, content in enumerate(["first", "second", "third"]):
            await store.add_message(
                MessageRecord(
                    session_id=session.id,
                    role=MessageRole.HUMAN,
                    content=content,
                    ordinal=i,
                )
            )

        messages = await store.get_messages(session.id)
        assert [m.content for m in messages] == ["first", "second", "third"]

    async def test_tool_call_metadata_persisted(self, store: SessionStore) -> None:
        """AI messages with tool_calls should preserve metadata."""
        session = await store.create_session()
        tool_calls = [{"name": "add", "args": {"a": 1, "b": 2}, "id": "call_1"}]
        await store.add_message(
            MessageRecord(
                session_id=session.id,
                role=MessageRole.AI,
                content="",
                tool_calls=tool_calls,
                ordinal=0,
            )
        )

        messages = await store.get_messages(session.id)
        assert messages[0].tool_calls == tool_calls

    async def test_tool_message_persisted(self, store: SessionStore) -> None:
        """Tool messages should preserve tool_call_id."""
        session = await store.create_session()
        await store.add_message(
            MessageRecord(
                session_id=session.id,
                role=MessageRole.TOOL,
                content="42",
                tool_call_id="call_1",
                ordinal=0,
            )
        )

        messages = await store.get_messages(session.id)
        assert messages[0].tool_call_id == "call_1"
        assert messages[0].content == "42"

    async def test_auto_title_from_first_human_message(
        self, store: SessionStore
    ) -> None:
        """Session title should auto-update from first human message."""
        session = await store.create_session()
        assert session.title == ""

        await store.add_message(
            MessageRecord(
                session_id=session.id,
                role=MessageRole.HUMAN,
                content="What is 2+2?",
                ordinal=0,
            )
        )

        updated = await store.get_session(session.id)
        assert updated is not None
        assert updated.title == "What is 2+2?"

    async def test_auto_title_not_overwritten(self, store: SessionStore) -> None:
        """Once a title is set, it should not be overwritten."""
        session = await store.create_session("My Custom Title")
        await store.add_message(
            MessageRecord(
                session_id=session.id,
                role=MessageRole.HUMAN,
                content="New content",
                ordinal=0,
            )
        )

        updated = await store.get_session(session.id)
        assert updated is not None
        assert updated.title == "My Custom Title"

    async def test_get_next_ordinal(self, store: SessionStore) -> None:
        """get_next_ordinal should return the next available ordinal."""
        session = await store.create_session()
        assert await store.get_next_ordinal(session.id) == 0

        await store.add_message(
            MessageRecord(
                session_id=session.id,
                role=MessageRole.HUMAN,
                content="hello",
                ordinal=0,
            )
        )
        assert await store.get_next_ordinal(session.id) == 1


# ---- Pending state ----


class TestPendingState:
    """Test save/clear/read of pending tool call state."""

    async def test_save_and_read_pending_state(self, store: SessionStore) -> None:
        """Saving pending state should make it readable."""
        session = await store.create_session()
        pending = {"tool": "calculator", "args": {"a": 1}}
        await store.save_pending_state(session.id, pending)

        fetched = await store.get_session(session.id)
        assert fetched is not None
        assert fetched.pending_state == pending

    async def test_clear_pending_state(self, store: SessionStore) -> None:
        """Clearing pending state should set it to None."""
        session = await store.create_session()
        await store.save_pending_state(session.id, {"tool": "test"})
        await store.clear_pending_state(session.id)

        fetched = await store.get_session(session.id)
        assert fetched is not None
        assert fetched.pending_state is None

    async def test_can_resume_reflects_pending_state(self, store: SessionStore) -> None:
        """SessionSummary.can_resume should be True when pending state exists."""
        session = await store.create_session()
        await store.save_pending_state(session.id, {"tool": "test"})

        summaries = await store.list_sessions()
        summary = next(s for s in summaries if s.id == session.id)
        assert summary.can_resume is True


# ---- Session detail ----


class TestSessionDetail:
    """Test get_session_detail returns full session with messages."""

    async def test_get_session_detail(self, store: SessionStore) -> None:
        """get_session_detail should return session + messages."""
        session = await store.create_session("Detail Test")
        await store.add_message(
            MessageRecord(
                session_id=session.id,
                role=MessageRole.HUMAN,
                content="ping",
                ordinal=0,
            )
        )

        detail = await store.get_session_detail(session.id)
        assert detail is not None
        assert detail.session.title == "Detail Test"
        assert len(detail.messages) == 1
        assert detail.messages[0].content == "ping"

    async def test_get_session_detail_nonexistent(self, store: SessionStore) -> None:
        """get_session_detail on non-existent ID returns None."""
        detail = await store.get_session_detail("nonexistent")
        assert detail is None


# ---- Error handling ----


class TestStoreErrors:
    """Test error handling in SessionStore."""

    async def test_db_property_before_init(self) -> None:
        """Accessing db before initialize should raise RuntimeError."""
        store = SessionStore(":memory:")
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = store.db
