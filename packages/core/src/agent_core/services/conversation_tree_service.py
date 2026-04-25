"""Conversation tree service."""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from agent_core.logging_utils import get_logger
from agent_core.models.session import (
    ChatNodeRecord,
    MessageRecord,
    MessageRole,
    MessageStatus,
    NodeLeafBookmarkRecord,
    NodeSourceKind,
    SessionDetail,
    SessionVersionGroup,
    VersionGroupSelectionRecord,
)
from agent_core.persistence.conversation_tree_store import ConversationTreeStore
from agent_core.persistence.converters import record_to_message
from agent_core.persistence.session_store import SessionStore

logger = get_logger("conversation_tree_service")


def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(UTC)


_TITLE_MAX_LENGTH = 80
_TITLE_REASONING_BLOCK_PATTERNS = (
    re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL),
    re.compile(r"\(\s*<think>.*?</think>\s*\)", re.IGNORECASE | re.DOTALL),
)
_TITLE_PREFIX_PATTERNS = (
    re.compile(r"^(?:title)\s*[:\-\uff1a]\s*", re.IGNORECASE),
    re.compile(
        r"^(?:sure|certainly|of course|here(?:'|’)s|here is)\b[:,-]?\s*", re.IGNORECASE
    ),
    re.compile(
        r"^(?:\u5f53\u7136(?:\u53ef\u4ee5)?|\u597d\u7684|\u4ee5\u4e0b(?:\u662f)?|\u8fd9\u662f)\s*[\uff1a:\uff0c,]?\s*"
    ),
)


def _normalize_title_candidate(text: str) -> str:
    """Extract a short, readable title candidate from assistant text."""
    for pattern in _TITLE_REASONING_BLOCK_PATTERNS:
        text = pattern.sub("\n", text)

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("```"):
            continue
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^[-*+]\s*", "", line)
        line = re.sub(r"^\d+[.)]\s*", "", line)
        line = re.sub(r"`+", "", line)
        for pattern in _TITLE_PREFIX_PATTERNS:
            line = pattern.sub("", line)
        line = re.sub(r"\s+", " ", line).strip(
            " -:()[]{}\uff1a,\uff0c.\u3002;\uff1b\"'"
        )
        if line:
            return line[:_TITLE_MAX_LENGTH]
    return ""


def _extract_llm_text(response: Any) -> str:
    """Coerce common LLM response payloads into plain text."""
    content = response.content if hasattr(response, "content") else response
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
                    continue
            parts.append(str(item))
        return "\n".join(part for part in parts if part).strip()
    return str(content)


_TITLE_GENERATION_SYSTEM_PROMPT = (
    "You generate concise session titles for chat conversations."
)
_TITLE_GENERATION_USER_PROMPT = (
    "Generate a short title for this first-round chat exchange.\n\n"
    "Requirements:\n"
    "- Keep the same language as the conversation.\n"
    "- Use plain text only.\n"
    "- Prefer 4 to 12 words.\n"
    "- Do not include quotes, prefixes, or trailing punctuation.\n\n"
    "User message:\n"
    "{user_message}\n\n"
    "Assistant reply:\n"
    "{assistant_message}\n"
)


class ConversationTreeService:
    """High-level business logic for the conversation version tree."""

    def __init__(
        self,
        session_store: SessionStore,
        tree_store: ConversationTreeStore,
    ) -> None:
        self._sessions = session_store
        self._tree = tree_store

    async def build_session_detail(self, session_id: str) -> SessionDetail | None:
        """Build a session detail snapshot from the conversation tree."""
        session = await self._sessions.get_session(session_id)
        if session is None:
            return None

        nodes = await self._tree.list_nodes(session_id)
        if not nodes:
            messages = await self._sessions.get_messages(session_id)
            return SessionDetail(session=session, messages=messages)

        node_by_id = {node.id: node for node in nodes}
        current_leaf_id = session.current_leaf_node_id or self._latest_leaf(nodes).id
        visible_nodes = self._build_visible_path(current_leaf_id, node_by_id)
        visible_path = [node.id for node in visible_nodes]
        version_groups = self._build_version_groups(nodes, visible_nodes)
        messages = self._project_messages(visible_nodes)

        return SessionDetail(
            session=session,
            messages=messages,
            nodes=nodes,
            visible_path=visible_path,
            version_groups=version_groups,
        )

    async def select_version(
        self,
        session_id: str,
        version_group_id: str,
        node_id: str,
    ) -> SessionDetail | None:
        """Switch the selected node in a version group and rebuild the snapshot."""
        session = await self._sessions.get_session(session_id)
        if session is None:
            return None

        nodes = await self._tree.list_nodes(session_id)
        node_by_id = {node.id: node for node in nodes}
        target = node_by_id.get(node_id)
        if target is None or target.version_group_id != version_group_id:
            raise ValueError("Invalid node selection for version group")

        if session.current_leaf_node_id:
            old_visible_nodes = self._build_visible_path(
                session.current_leaf_node_id,
                node_by_id,
            )
            old_group_node = next(
                (
                    node
                    for node in old_visible_nodes
                    if node.version_group_id == version_group_id
                ),
                None,
            )
            if old_group_node is not None:
                await self._tree.upsert_node_bookmark(
                    NodeLeafBookmarkRecord(
                        session_id=session_id,
                        node_id=old_group_node.id,
                        selected_leaf_id=session.current_leaf_node_id,
                    )
                )

        await self._tree.upsert_version_selection(
            VersionGroupSelectionRecord(
                session_id=session_id,
                version_group_id=version_group_id,
                selected_node_id=node_id,
            )
        )

        bookmark = await self._tree.get_node_bookmark(session_id, node_id)
        resolved_leaf = (
            bookmark.selected_leaf_id
            if bookmark is not None
            else self._latest_leaf(self._collect_subtree_nodes(node_id, node_by_id)).id
        )
        await self._sessions.update_current_leaf(session_id, resolved_leaf)
        return await self.build_session_detail(session_id)

    async def retry_assistant(
        self,
        session_id: str,
        assistant_node_id: str,
    ) -> SessionDetail | None:
        """Create a new assistant retry version and make it current."""
        assistant = await self._tree.get_node(session_id, assistant_node_id)
        if assistant is None:
            return None
        if assistant.role != MessageRole.AI:
            raise ValueError("Retry is only valid for assistant nodes")

        await self._bookmark_current_leaf_if_descendant(session_id, assistant.id)

        next_index = (
            await self._tree.get_max_version_index(
                session_id,
                assistant.version_group_id,
            )
            + 1
        )
        now = _utcnow()
        retry_node = ChatNodeRecord(
            id=str(uuid.uuid4()),
            session_id=session_id,
            parent_id=assistant.parent_id,
            role=MessageRole.AI,
            content="",
            status=MessageStatus.STREAMING,
            version_group_id=assistant.version_group_id,
            version_index=next_index,
            source_kind=NodeSourceKind.RETRY,
            source_node_id=assistant.id,
            response_to_node_id=assistant.response_to_node_id,
            created_at=now,
            updated_at=now,
        )
        saved = await self._tree.add_versioned_node(retry_node)
        await self._tree.upsert_version_selection(
            VersionGroupSelectionRecord(
                session_id=session_id,
                version_group_id=saved.version_group_id,
                selected_node_id=saved.id,
            )
        )
        await self._sessions.update_current_leaf(session_id, saved.id)
        return await self.build_session_detail(session_id)

    async def edit_user(
        self,
        session_id: str,
        user_node_id: str,
        content: str,
    ) -> SessionDetail | None:
        """Create a new user version and assistant placeholder branch."""
        user_node = await self._tree.get_node(session_id, user_node_id)
        if user_node is None:
            return None
        if user_node.role != MessageRole.HUMAN:
            raise ValueError("User edit is only valid for user nodes")

        await self._bookmark_current_leaf_if_descendant(session_id, user_node.id)

        next_index = (
            await self._tree.get_max_version_index(
                session_id, user_node.version_group_id
            )
            + 1
        )
        now = _utcnow()
        new_user = ChatNodeRecord(
            id=str(uuid.uuid4()),
            session_id=session_id,
            parent_id=user_node.parent_id,
            role=MessageRole.HUMAN,
            content=content,
            status=MessageStatus.COMPLETED,
            version_group_id=user_node.version_group_id,
            version_index=next_index,
            source_kind=NodeSourceKind.USER_EDIT,
            source_node_id=user_node.id,
            created_at=now,
            updated_at=now,
        )
        saved_user = await self._tree.add_versioned_node(new_user)
        placeholder = ChatNodeRecord(
            id=str(uuid.uuid4()),
            session_id=session_id,
            parent_id=saved_user.id,
            role=MessageRole.AI,
            content="",
            status=MessageStatus.STREAMING,
            version_group_id=str(uuid.uuid4()),
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            response_to_node_id=saved_user.id,
            created_at=now,
            updated_at=now,
        )
        saved_placeholder = await self._tree.add_node(placeholder)
        await self._tree.upsert_version_selection(
            VersionGroupSelectionRecord(
                session_id=session_id,
                version_group_id=saved_user.version_group_id,
                selected_node_id=saved_user.id,
            )
        )
        await self._tree.upsert_version_selection(
            VersionGroupSelectionRecord(
                session_id=session_id,
                version_group_id=saved_placeholder.version_group_id,
                selected_node_id=saved_placeholder.id,
            )
        )
        await self._sessions.update_current_leaf(session_id, saved_placeholder.id)
        return await self.build_session_detail(session_id)

    async def edit_node(
        self,
        session_id: str,
        node_id: str,
        content: str,
    ) -> SessionDetail | None:
        """Dispatch an edit request to the correct role-specific mutation."""
        node = await self._tree.get_node(session_id, node_id)
        if node is None:
            return None
        if node.role == MessageRole.HUMAN:
            return await self.edit_user(session_id, node_id, content)
        if node.role == MessageRole.AI:
            return await self.edit_assistant(session_id, node_id, content)
        raise ValueError("Edit is only valid for user or assistant nodes")

    async def edit_assistant(
        self,
        session_id: str,
        assistant_node_id: str,
        content: str,
    ) -> SessionDetail | None:
        """Create a new assistant version with edited content."""
        assistant = await self._tree.get_node(session_id, assistant_node_id)
        if assistant is None:
            return None
        if assistant.role != MessageRole.AI:
            raise ValueError("Assistant edit is only valid for assistant nodes")

        await self._bookmark_current_leaf_if_descendant(session_id, assistant.id)

        next_index = (
            await self._tree.get_max_version_index(
                session_id,
                assistant.version_group_id,
            )
            + 1
        )
        now = _utcnow()
        edited = ChatNodeRecord(
            id=str(uuid.uuid4()),
            session_id=session_id,
            parent_id=assistant.parent_id,
            role=MessageRole.AI,
            content=content,
            status=MessageStatus.COMPLETED,
            version_group_id=assistant.version_group_id,
            version_index=next_index,
            source_kind=NodeSourceKind.ASSISTANT_EDIT,
            source_node_id=assistant.id,
            response_to_node_id=assistant.response_to_node_id,
            created_at=now,
            updated_at=now,
        )
        saved = await self._tree.add_versioned_node(edited)
        await self._tree.upsert_version_selection(
            VersionGroupSelectionRecord(
                session_id=session_id,
                version_group_id=saved.version_group_id,
                selected_node_id=saved.id,
            )
        )
        await self._sessions.update_current_leaf(session_id, saved.id)
        return await self.build_session_detail(session_id)

    async def prepare_stream_turn(
        self,
        session_id: str,
        user_content: str,
    ) -> tuple[list[BaseMessage], ChatNodeRecord, ChatNodeRecord]:
        """Create the next user turn and assistant placeholder for streaming."""
        session = await self._sessions.get_session(session_id)
        if session is None:
            await self._sessions.create_session_with_id(session_id)

        detail = await self.build_session_detail(session_id)
        history_messages = (
            [record_to_message(message) for message in detail.messages]
            if detail is not None
            else []
        )

        now = _utcnow()
        parent_id = detail.session.current_leaf_node_id if detail is not None else None
        user_node = ChatNodeRecord(
            id=str(uuid.uuid4()),
            session_id=session_id,
            parent_id=parent_id,
            role=MessageRole.HUMAN,
            content=user_content,
            status=MessageStatus.COMPLETED,
            version_group_id=str(uuid.uuid4()),
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            created_at=now,
            updated_at=now,
        )
        saved_user = await self._tree.add_node(user_node)

        placeholder = ChatNodeRecord(
            id=str(uuid.uuid4()),
            session_id=session_id,
            parent_id=saved_user.id,
            role=MessageRole.AI,
            content="",
            status=MessageStatus.STREAMING,
            version_group_id=str(uuid.uuid4()),
            version_index=0,
            source_kind=NodeSourceKind.INITIAL,
            response_to_node_id=saved_user.id,
            created_at=now,
            updated_at=now,
        )
        saved_placeholder = await self._tree.add_node(placeholder)

        await self._tree.upsert_version_selection(
            VersionGroupSelectionRecord(
                session_id=session_id,
                version_group_id=saved_user.version_group_id,
                selected_node_id=saved_user.id,
            )
        )
        await self._tree.upsert_version_selection(
            VersionGroupSelectionRecord(
                session_id=session_id,
                version_group_id=saved_placeholder.version_group_id,
                selected_node_id=saved_placeholder.id,
            )
        )
        await self._sessions.update_current_leaf(session_id, saved_placeholder.id)
        return history_messages, saved_user, saved_placeholder

    async def prepare_placeholder_stream(
        self,
        session_id: str,
    ) -> tuple[list[BaseMessage], ChatNodeRecord] | None:
        """Prepare to continue generation for the current streaming placeholder."""
        session = await self._sessions.get_session(session_id)
        if session is None or session.current_leaf_node_id is None:
            return None

        placeholder = await self._tree.get_node(
            session_id, session.current_leaf_node_id
        )
        if placeholder is None or placeholder.role != MessageRole.AI:
            return None
        if placeholder.status != MessageStatus.STREAMING:
            return None

        detail = await self.build_session_detail(session_id)
        if detail is None or not detail.messages:
            return None
        # Exclude the placeholder itself.
        # The last history message must be the current user node.
        history_messages = [
            record_to_message(message) for message in detail.messages[:-1]
        ]
        return history_messages, placeholder

    async def finalize_stream_turn(
        self,
        session_id: str,
        placeholder_node_id: str,
        assistant_content: str,
        status: MessageStatus = MessageStatus.COMPLETED,
        *,
        tool_calls: list[dict[str, object]] | None = None,
        trace_steps: list[dict[str, object]] | None = None,
    ) -> ChatNodeRecord | None:
        """Finalize a streaming assistant placeholder with terminal content/status."""
        fields: dict[str, object] = {
            "content": assistant_content,
            "status": status,
        }
        if tool_calls is not None:
            fields["tool_calls"] = tool_calls
        if trace_steps is not None:
            fields["trace_steps"] = trace_steps
        updated = await self._tree.update_node(
            session_id,
            placeholder_node_id,
            fields,
        )
        if updated is None:
            return None
        await self._sessions.update_current_leaf(session_id, updated.id)
        return updated

    async def maybe_generate_first_round_title(
        self,
        session_id: str,
        assistant_node_id: str,
        llm: Any,
    ) -> str | None:
        """Generate a title from a dedicated LLM request for the first round only."""
        title_context = await self._get_first_round_title_context(
            session_id,
            assistant_node_id,
        )
        if title_context is None:
            return None

        user_message, assistant_message = title_context
        try:
            response = await llm.ainvoke(
                [
                    SystemMessage(content=_TITLE_GENERATION_SYSTEM_PROMPT),
                    HumanMessage(
                        content=_TITLE_GENERATION_USER_PROMPT.format(
                            user_message=user_message,
                            assistant_message=assistant_message,
                        )
                    ),
                ]
            )
        except Exception:
            logger.exception(
                "Async first-round title generation failed for session %s",
                session_id,
            )
            return None

        title = _normalize_title_candidate(_extract_llm_text(response))
        if not title:
            return None

        session = await self._sessions.get_session(session_id)
        if session is None or session.title != "":
            return None

        await self._sessions.update_session_title(session_id, title)
        return title

    async def _get_first_round_title_context(
        self,
        session_id: str,
        assistant_node_id: str,
    ) -> tuple[str, str] | None:
        """Return the first-round user/assistant pair eligible for async titling."""
        assistant_node = await self._tree.get_node(session_id, assistant_node_id)
        if assistant_node is None:
            return None
        if (
            assistant_node.role != MessageRole.AI
            or assistant_node.status != MessageStatus.COMPLETED
            or not assistant_node.response_to_node_id
        ):
            return None

        session = await self._sessions.get_session(session_id)
        if session is None or session.title != "":
            return None

        user_node = await self._tree.get_node(
            session_id, assistant_node.response_to_node_id
        )
        if user_node is None or user_node.parent_id is not None:
            return None

        if not user_node.content.strip() or not assistant_node.content.strip():
            return None

        return user_node.content, assistant_node.content

    async def persist_stream_terminal_state(
        self,
        session_id: str,
        assistant_content: str,
        status: MessageStatus,
    ) -> SessionDetail | None:
        """Finalize the current streaming placeholder if the session is tree-backed."""
        session = await self._sessions.get_session(session_id)
        if session is None or session.current_leaf_node_id is None:
            return None

        leaf = await self._tree.get_node(session_id, session.current_leaf_node_id)
        if leaf is None or leaf.role != MessageRole.AI:
            return None

        updated = await self.finalize_stream_turn(
            session_id,
            leaf.id,
            assistant_content,
            status=status,
        )
        if updated is None:
            return None
        return await self.build_session_detail(session_id)

    async def fail_stream_placeholder(
        self,
        session_id: str,
        placeholder_node_id: str,
        error_summary: str,
    ) -> ChatNodeRecord | None:
        """Mark a placeholder assistant node as failed."""
        return await self._tree.update_node(
            session_id,
            placeholder_node_id,
            {
                "status": MessageStatus.FAILED,
                "content": error_summary,
            },
        )

    async def _bookmark_current_leaf_if_descendant(
        self,
        session_id: str,
        node_id: str,
    ) -> None:
        """Store the current leaf for a node before switching to another version."""
        session = await self._sessions.get_session(session_id)
        if session is None or session.current_leaf_node_id is None:
            return

        if session.current_leaf_node_id == node_id:
            await self._tree.upsert_node_bookmark(
                NodeLeafBookmarkRecord(
                    session_id=session_id,
                    node_id=node_id,
                    selected_leaf_id=session.current_leaf_node_id,
                )
            )
            return

        nodes = await self._tree.list_nodes(session_id)
        node_by_id = {node.id: node for node in nodes}
        if node_id not in node_by_id or session.current_leaf_node_id not in node_by_id:
            return

        subtree_ids = {
            node.id for node in self._collect_subtree_nodes(node_id, node_by_id)
        }
        if session.current_leaf_node_id not in subtree_ids:
            return

        await self._tree.upsert_node_bookmark(
            NodeLeafBookmarkRecord(
                session_id=session_id,
                node_id=node_id,
                selected_leaf_id=session.current_leaf_node_id,
            )
        )

    @staticmethod
    def _build_visible_path(
        leaf_id: str,
        node_by_id: dict[str, ChatNodeRecord],
    ) -> list[ChatNodeRecord]:
        """Walk from leaf to root and return the visible path in root-first order."""
        path: list[ChatNodeRecord] = []
        cursor = node_by_id.get(leaf_id)
        while cursor is not None:
            path.append(cursor)
            cursor = node_by_id.get(cursor.parent_id) if cursor.parent_id else None
        return list(reversed(path))

    @staticmethod
    def _build_version_groups(
        all_nodes: list[ChatNodeRecord],
        visible_nodes: list[ChatNodeRecord],
    ) -> list[SessionVersionGroup]:
        """Build the version-group projection for nodes on the visible path."""
        grouped: dict[str, list[ChatNodeRecord]] = defaultdict(list)
        for node in all_nodes:
            grouped[node.version_group_id].append(node)

        groups: list[SessionVersionGroup] = []
        for position, node in enumerate(visible_nodes):
            group_nodes = sorted(
                grouped[node.version_group_id],
                key=lambda item: (item.version_index, item.created_at, item.id),
            )
            if len(group_nodes) <= 1:
                continue
            groups.append(
                SessionVersionGroup(
                    version_group_id=node.version_group_id,
                    node_ids=[item.id for item in group_nodes],
                    selected_node_id=node.id,
                    position_in_path=position,
                )
            )
        return groups

    @staticmethod
    def _project_messages(visible_nodes: list[ChatNodeRecord]) -> list[MessageRecord]:
        """Project visible tree nodes to the legacy linear message view."""
        messages: list[MessageRecord] = []
        for ordinal, node in enumerate(visible_nodes):
            messages.append(
                MessageRecord(
                    session_id=node.session_id,
                    role=node.role,
                    content=node.content,
                    status=node.status,
                    created_at=node.created_at,
                    ordinal=ordinal,
                )
            )
        return messages

    @staticmethod
    def _collect_subtree_nodes(
        root_id: str,
        node_by_id: dict[str, ChatNodeRecord],
    ) -> list[ChatNodeRecord]:
        """Collect all nodes in the subtree rooted at the given node."""
        children: dict[str | None, list[ChatNodeRecord]] = defaultdict(list)
        for node in node_by_id.values():
            children[node.parent_id].append(node)

        subtree: list[ChatNodeRecord] = []
        stack = [root_id]
        while stack:
            node_id = stack.pop()
            node = node_by_id[node_id]
            subtree.append(node)
            stack.extend(child.id for child in children.get(node_id, []))
        return subtree

    @staticmethod
    def _latest_leaf(nodes: list[ChatNodeRecord]) -> ChatNodeRecord:
        """Return the latest leaf node in a subtree or full session node list."""
        child_ids = {node.parent_id for node in nodes if node.parent_id is not None}
        leaves = [node for node in nodes if node.id not in child_ids]
        return max(
            leaves, key=lambda item: (item.created_at, item.version_index, item.id)
        )
