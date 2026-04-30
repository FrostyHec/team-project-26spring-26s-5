"""ReAct Agent - Core agent loop using LangGraph."""

import uuid
from collections.abc import AsyncGenerator, Callable
from typing import TYPE_CHECKING, Annotated, Any, Union

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import END, StateGraph
from pydantic import Field, TypeAdapter, ValidationError

from agent_core.engine.reasoning import (
    ReasoningSegment,
    ReasoningSegmentKind,
    ReasoningStreamSplitter,
    has_think_protocol,
    sanitize_visible_answer,
    split_reasoning_segments,
)
from agent_core.engine.state import AgentState
from agent_core.logging_utils import get_logger
from agent_core.models.events import (
    ApprovalRequestEvent,
    CustomEventName,
    LangGraphEventKind,
    LoopEndEvent,
    LoopStartEvent,
    ThinkingEvent,
    TokenEvent,
    ToolEndEvent,
    ToolStartEvent,
    WidgetData,
    WidgetDisplayEvent,
)
from agent_core.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from agent_core.persistence.session_store import SessionStore

logger = get_logger("agent")


def _sanitize_ai_message_content(message: BaseMessage) -> BaseMessage:
    """Strip supported `<think>` blocks from persisted/returned AI text."""
    if not isinstance(message, AIMessage):
        return message
    if not isinstance(message.content, str) or not has_think_protocol(message.content):
        return message
    return message.model_copy(
        update={"content": sanitize_visible_answer(message.content)}
    )


def _emit_reasoning_events(
    segments: list[ReasoningSegment],
) -> list[dict[str, Any]]:
    """Convert split text fragments into protocol events."""
    events: list[dict[str, Any]] = []
    for segment in segments:
        if not segment.content:
            continue
        if segment.kind == ReasoningSegmentKind.THINKING:
            events.append(ThinkingEvent(content=segment.content).model_dump())
            continue
        events.append(TokenEvent(content=segment.content).model_dump())
    return events


def _build_widget_adapter() -> TypeAdapter | None:
    """Build a TypeAdapter for all registered WidgetData subclasses.

    Called at stream-time so that every tool module has already been
    imported and all ``WidgetData`` subclasses are visible.

    Returns:
        A ``TypeAdapter`` over the discriminated union, or ``None``
        if no subclasses have been registered.
    """
    subs = WidgetData.__subclasses__()
    if not subs:
        return None
    union = Union[tuple(subs)]  # noqa: UP007 – dynamic union built at runtime
    annotated = Annotated[union, Field(discriminator="widget_type")]
    return TypeAdapter(annotated)


# Type for the HITL approval handler callback.
# Signature: (tool_name, tool_args, tool_call_id) -> bool
# Returns True to approve execution, False to reject.
ApprovalHandler = Callable[[str, dict[str, Any], str], Any]


class ReactAgent:
    """ReAct agent that reasons and acts using tools via LangGraph.

    This agent implements the ReAct (Reasoning + Acting) pattern:
    1. Receive user input
    2. LLM decides to respond or call a tool
    3. If tool call: check HITL -> execute -> observe result -> loop
    4. If final answer: return to user

    Attributes:
        llm: The language model to use for reasoning.
        tool_registry: Registry of available tools.
        graph: Compiled LangGraph state machine.
    """

    def __init__(
        self,
        llm: Any,
        tool_registry: ToolRegistry,
        system_prompt: str = "",
    ) -> None:
        """Initialize the ReAct agent.

        Args:
            llm: A LangChain-compatible chat model.
            tool_registry: Registry containing available tools.
            system_prompt: Optional system prompt for the agent.
        """
        self.llm = llm
        self.tool_registry = tool_registry
        self.system_prompt = system_prompt
        self.session_store: SessionStore | None = None
        self.approval_handler: ApprovalHandler | None = None

        # Bind tools to the LLM
        lc_tools = self.tool_registry.get_langchain_tools()
        self.llm_with_tools = self.llm.bind_tools(lc_tools) if lc_tools else self.llm

        # Build the graph
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        """Build the LangGraph state machine for the ReAct loop."""
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("reasoner", self._reason)
        workflow.add_node("tool_executor", self._execute_tools)

        # Set entry point
        workflow.set_entry_point("reasoner")

        # Add conditional edges
        workflow.add_conditional_edges(
            "reasoner",
            self._should_continue,
            {"continue": "tool_executor", "end": END},
        )
        workflow.add_edge("tool_executor", "reasoner")

        return workflow.compile()

    def _get_session_extra(self, config: RunnableConfig | None = None) -> dict:
        """Extract session_id from config for logging context."""
        session_id = "Global"
        if config and "configurable" in config:
            session_id = config["configurable"].get("session_id", "Global")
        return {"session_id": session_id}

    async def _reason(
        self, state: AgentState, config: RunnableConfig | None = None
    ) -> dict:
        """LLM reasoning node: decide next action or final response.

        Args:
            state: Current agent state.
            config: RunnableConfig injected by LangGraph.

        Returns:
            Updated state with LLM response.
        """
        extra = self._get_session_extra(config)
        messages = list(state["messages"])

        # Prepend system prompt if set
        if self.system_prompt:
            from langchain_core.messages import SystemMessage

            # TODO: system prompt is fixed and auto-prepended;
            # this may change to support dynamic system prompts
            # Only add system message if not already present
            if not messages or not isinstance(messages[0], SystemMessage):
                messages = [SystemMessage(content=self.system_prompt)] + messages

        logger.debug(f"LLM Input (prompt): {messages}", extra=extra)

        response = await self.llm_with_tools.ainvoke(messages, config=config)

        logger.debug(f"LLM Output: {response}", extra=extra)

        return {"messages": [response]}

    def _should_continue(self, state: AgentState) -> str:
        """Determine whether to continue tool execution or end.

        Args:
            state: Current agent state.

        Returns:
            'continue' if tools need execution, 'end' otherwise.
        """
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "continue"
        return "end"

    async def _execute_tools(
        self, state: AgentState, config: RunnableConfig | None = None
    ) -> dict:
        """Execute tool calls from the LLM response.

        For SENSITIVE tools, invokes the approval_handler callback
        before execution. If the handler rejects or no handler is set
        for a sensitive tool, returns a cancellation message.

        Args:
            state: Current agent state.
            config: RunnableConfig injected by LangGraph.

        Returns:
            Updated state with tool execution results.
        """
        extra = self._get_session_extra(config)
        last_message = state["messages"][-1]
        tool_messages = []

        from langchain_core.callbacks.manager import adispatch_custom_event

        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            for tool_call in last_message.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id = tool_call["id"]

                logger.debug(
                    f"Executing Tool: {tool_name} with args: {tool_args}",
                    extra=extra,
                )

                # HITL: check if tool is sensitive
                if self.tool_registry.is_sensitive(tool_name):
                    logger.info(
                        f"Sensitive tool detected: {tool_name}",
                        extra=extra,
                    )
                    # Emit approval request event
                    await adispatch_custom_event(
                        CustomEventName.APPROVAL_REQUEST,
                        {
                            "tool": tool_name,
                            "args": tool_args,
                            "tool_call_id": tool_id,
                        },
                        config=config,
                    )

                    # Check with approval handler
                    approved = False
                    if self.approval_handler is not None:
                        result = self.approval_handler(tool_name, tool_args, tool_id)
                        # Support both sync and async handlers
                        if hasattr(result, "__await__"):
                            approved = await result
                        else:
                            approved = bool(result)

                    if not approved:
                        logger.info(
                            f"Tool {tool_name} rejected by user",
                            extra=extra,
                        )
                        tool_messages.append(
                            ToolMessage(
                                content="Tool call cancelled by user.",
                                name=tool_name,
                                tool_call_id=tool_id,
                            )
                        )
                        await adispatch_custom_event(
                            CustomEventName.TOOL_CALL_END,
                            {
                                "tool": tool_name,
                                "output": "Tool call cancelled by user.",
                            },
                            config=config,
                        )
                        continue

                # Emit a custom event right before execution
                await adispatch_custom_event(
                    CustomEventName.TOOL_CALL_START,
                    {"tool": tool_name, "args": tool_args},
                    config=config,
                )

                try:
                    result = await self.tool_registry.execute(tool_name, tool_args)
                    logger.debug(
                        f"Tool {tool_name} execution success: {result}",
                        extra=extra,
                    )
                    tool_messages.append(
                        ToolMessage(
                            content=str(result),
                            name=tool_name,
                            tool_call_id=tool_id,
                        )
                    )
                except Exception as e:
                    logger.warning(
                        f"Tool {tool_name} execution error: {e}",
                        extra=extra,
                    )
                    tool_messages.append(
                        ToolMessage(
                            content=f"Error: {e}",
                            name=tool_name,
                            tool_call_id=tool_id,
                        )
                    )

                # Emit custom event after execution
                await adispatch_custom_event(
                    CustomEventName.TOOL_CALL_END,
                    {
                        "tool": tool_name,
                        "output": tool_messages[-1].content,
                    },
                    config=config,
                )

        return {"messages": tool_messages}

    async def _load_history(self, session_id: str) -> list[BaseMessage]:
        """Load conversation history from the session store.

        Args:
            session_id: The session UUID.

        Returns:
            List of LangChain messages from history.
        """
        if not self.session_store:
            return []

        from agent_core.persistence.converters import record_to_message

        records = await self.session_store.get_messages(session_id)
        return [record_to_message(r) for r in records]

    async def _persist_messages(
        self,
        session_id: str,
        messages: list[BaseMessage],
        start_ordinal: int,
    ) -> None:
        """Persist new messages to the session store.

        Args:
            session_id: The session UUID.
            messages: New messages to persist.
            start_ordinal: Ordinal offset for the first message.
        """
        if not self.session_store:
            return

        from agent_core.persistence.converters import message_to_record

        for i, msg in enumerate(messages):
            record = message_to_record(msg, session_id, start_ordinal + i)
            await self.session_store.add_message(record)

    async def _ensure_session(self, session_id: str) -> None:
        """Ensure a session exists in the store, creating if needed.

        Args:
            session_id: The session UUID.
        """
        if not self.session_store:
            return
        existing = await self.session_store.get_session(session_id)
        if existing is None:
            await self.session_store.create_session_with_id(session_id)

    async def chat(self, user_input: str, session_id: str | None = None) -> str:
        """Send a message to the agent and get a response.

        If session_id is provided and a SessionStore is attached,
        conversation history is loaded and new messages are persisted.

        Args:
            user_input: The user's message.
            session_id: Optional session identifier.

        Returns:
            The agent's final text response.
        """
        if not session_id:
            session_id = str(uuid.uuid4())

        extra = {"session_id": session_id}
        logger.info(f"Starting chat with input: {user_input}", extra=extra)

        # Load history and build initial state
        history = await self._load_history(session_id)
        await self._ensure_session(session_id)
        new_msg = HumanMessage(content=user_input)
        all_messages = history + [new_msg]

        initial_state: AgentState = {
            "messages": all_messages,
            "pending_tool_call": None,
        }

        config = {"configurable": {"session_id": session_id}}

        result = await self.graph.ainvoke(initial_state, config=config)

        # Persist new messages (everything after history)
        new_messages = [
            _sanitize_ai_message_content(message)
            for message in result["messages"][len(history) :]
        ]
        await self._persist_messages(session_id, new_messages, len(history))

        last_message = new_messages[-1]
        logger.info("Finished chat.", extra=extra)
        return str(last_message.content)

    async def chat_with_history(
        self,
        user_input: str,
        history: list[BaseMessage],
        session_id: str | None = None,
        *,
        persist_messages: bool = False,
    ) -> str:
        """Run a chat turn with caller-provided history.

        This is used by the conversation-tree flow, where the route/service
        computes the visible branch history and controls persistence.
        """
        if not session_id:
            session_id = str(uuid.uuid4())

        extra = {"session_id": session_id}
        logger.info(f"Starting chat with input: {user_input}", extra=extra)

        await self._ensure_session(session_id)
        new_msg = HumanMessage(content=user_input)
        all_messages = history + [new_msg]
        initial_state: AgentState = {
            "messages": all_messages,
            "pending_tool_call": None,
        }
        config = {"configurable": {"session_id": session_id}}
        result = await self.graph.ainvoke(initial_state, config=config)

        if persist_messages:
            new_messages = [
                _sanitize_ai_message_content(message)
                for message in result["messages"][len(history) :]
            ]
            await self._persist_messages(session_id, new_messages, len(history))

        last_message = _sanitize_ai_message_content(result["messages"][-1])
        logger.info("Finished chat.", extra=extra)
        return str(last_message.content)

    async def _stream_graph_events(
        self,
        initial_state: AgentState,
        config: dict[str, Any],
        new_messages: list[BaseMessage],
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Normalize LangGraph events into the agent streaming protocol."""
        reasoning_splitter = ReasoningStreamSplitter()
        saw_stream_content = False

        async for event in self.graph.astream_events(
            initial_state, config=config, version="v2"
        ):
            kind = event["event"]

            if kind == LangGraphEventKind.CHAT_MODEL_STREAM:
                content = event["data"]["chunk"].content
                if isinstance(content, str) and content:
                    saw_stream_content = True
                    for protocol_event in _emit_reasoning_events(
                        reasoning_splitter.feed_segments(content)
                    ):
                        yield protocol_event
                elif content:
                    saw_stream_content = True
                    yield TokenEvent(content=str(content)).model_dump()

            elif kind == LangGraphEventKind.CHAT_MODEL_END:
                ai_msg = event["data"]["output"]
                if isinstance(ai_msg, AIMessage):
                    if saw_stream_content:
                        segments = reasoning_splitter.flush_segments()
                    elif isinstance(ai_msg.content, str):
                        segments = split_reasoning_segments(ai_msg.content)
                    else:
                        segments = []

                    for protocol_event in _emit_reasoning_events(segments):
                        yield protocol_event

                    new_messages.append(_sanitize_ai_message_content(ai_msg))

                reasoning_splitter = ReasoningStreamSplitter()
                saw_stream_content = False

            elif kind == LangGraphEventKind.CUSTOM_EVENT:
                custom_name = event["name"]
                if custom_name == CustomEventName.APPROVAL_REQUEST:
                    yield ApprovalRequestEvent(
                        tool_name=event["data"]["tool"],
                        tool_args=event["data"].get("args", {}),
                        tool_call_id=event["data"].get("tool_call_id", ""),
                    ).model_dump()
                elif custom_name == CustomEventName.TOOL_CALL_START:
                    yield ToolStartEvent(
                        name=event["data"]["tool"],
                        input=event["data"].get("args", {}),
                    ).model_dump()
                elif custom_name == CustomEventName.TOOL_CALL_END:
                    tool_name = event["data"]["tool"]
                    output = event["data"].get("output", "")
                    yield ToolEndEvent(name=tool_name, output=output).model_dump()

                    adapter = _build_widget_adapter()
                    if adapter is not None:
                        try:
                            widget_obj = adapter.validate_json(output)
                            if isinstance(widget_obj, WidgetData):
                                yield WidgetDisplayEvent.from_widget_data(
                                    widget_obj
                                ).model_dump()
                        except (ValidationError, ValueError):
                            pass

                    new_messages.append(
                        ToolMessage(
                            content=output,
                            name=tool_name,
                            tool_call_id="",
                        )
                    )

    async def stream(
        self, user_input: str, session_id: str | None = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream agent execution steps for real-time UI updates.

        If session_id is provided and a SessionStore is attached,
        conversation history is loaded and new messages are persisted.

        Args:
            user_input: The user's message.
            session_id: Optional session identifier.

        Yields:
            Dicts with step type and content for UI rendering.
        """
        if not session_id:
            session_id = str(uuid.uuid4())

        extra = {"session_id": session_id}
        logger.info(f"Starting stream with input: {user_input}", extra=extra)

        # Load history and build initial state
        history = await self._load_history(session_id)
        await self._ensure_session(session_id)
        new_msg = HumanMessage(content=user_input)
        all_messages = history + [new_msg]

        initial_state: AgentState = {
            "messages": all_messages,
            "pending_tool_call": None,
        }

        config = {"configurable": {"session_id": session_id}}

        # Collect new messages for persistence
        new_messages: list[BaseMessage] = [new_msg]

        yield LoopStartEvent().model_dump()

        async for event in self._stream_graph_events(
            initial_state, config, new_messages
        ):
            yield event

        yield LoopEndEvent().model_dump()

        # Persist all new messages
        await self._persist_messages(session_id, new_messages, len(history))

        logger.info("Finished stream.", extra=extra)

    async def stream_with_history(
        self,
        user_input: str,
        history: list[BaseMessage],
        session_id: str | None = None,
        *,
        persist_messages: bool = False,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream a turn with caller-provided history.

        Used by the conversation-tree flow so routes/services can control
        branch selection and persistence themselves.
        """
        if not session_id:
            session_id = str(uuid.uuid4())

        extra = {"session_id": session_id}
        logger.info(f"Starting stream with input: {user_input}", extra=extra)

        await self._ensure_session(session_id)
        new_msg = HumanMessage(content=user_input)
        all_messages = history + [new_msg]
        initial_state: AgentState = {
            "messages": all_messages,
            "pending_tool_call": None,
        }
        config = {"configurable": {"session_id": session_id}}
        new_messages: list[BaseMessage] = [new_msg]

        yield LoopStartEvent().model_dump()

        async for event in self._stream_graph_events(
            initial_state, config, new_messages
        ):
            yield event

        yield LoopEndEvent().model_dump()

        if persist_messages:
            await self._persist_messages(session_id, new_messages, len(history))

        logger.info("Finished stream.", extra=extra)

    async def stream_from_messages(
        self,
        messages: list[BaseMessage],
        session_id: str | None = None,
        *,
        persist_messages: bool = False,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream from a caller-provided full message list.

        Used when the caller has already materialized the exact visible branch,
        including the final user message that should trigger the assistant turn.
        """
        if not session_id:
            session_id = str(uuid.uuid4())

        extra = {"session_id": session_id}
        logger.info("Starting stream from explicit messages.", extra=extra)

        await self._ensure_session(session_id)
        initial_state: AgentState = {
            "messages": messages,
            "pending_tool_call": None,
        }
        config = {"configurable": {"session_id": session_id}}
        new_messages: list[BaseMessage] = []

        yield LoopStartEvent().model_dump()

        async for event in self._stream_graph_events(
            initial_state, config, new_messages
        ):
            yield event

        yield LoopEndEvent().model_dump()

        if persist_messages:
            await self._persist_messages(session_id, new_messages, len(messages))

        logger.info("Finished explicit-message stream.", extra=extra)
