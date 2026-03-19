"""ReAct Agent - Core agent loop using LangGraph."""

import uuid
from collections.abc import AsyncGenerator
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import END, StateGraph

from agent_core.engine.state import AgentState
from agent_core.logging_utils import get_logger
from agent_core.tools.registry import ToolRegistry

logger = get_logger("agent")


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
                    f"Executing Tool: {tool_name} with args: {tool_args}", extra=extra
                )

                # Emit a custom event right before execution so stream can read it
                await adispatch_custom_event(
                    "tool_call_start",
                    {"tool": tool_name, "args": tool_args},
                    config=config,
                )

                try:
                    result = await self.tool_registry.execute(tool_name, tool_args)
                    logger.debug(
                        f"Tool {tool_name} execution success: {result}", extra=extra
                    )
                    tool_messages.append(
                        ToolMessage(
                            content=str(result),
                            name=tool_name,
                            tool_call_id=tool_id,
                        )
                    )
                except Exception as e:
                    logger.debug(f"Tool {tool_name} execution error: {e}", extra=extra)
                    tool_messages.append(
                        ToolMessage(
                            content=f"Error: {e}",
                            name=tool_name,
                            tool_call_id=tool_id,
                        )
                    )

                # Emit custom event after execution
                await adispatch_custom_event(
                    "tool_call_end",
                    {"tool": tool_name, "output": tool_messages[-1].content},
                    config=config,
                )

        return {"messages": tool_messages}

    async def chat(self, user_input: str, session_id: str | None = None) -> str:
        """Send a message to the agent and get a response.

        Args:
            user_input: The user's message.
            session_id: Optional session identifier for tracking logs.

        Returns:
            The agent's final text response.
        """
        if not session_id:
            session_id = str(uuid.uuid4())

        logger.info(
            f"Starting chat with input: {user_input}", extra={"session_id": session_id}
        )

        initial_state: AgentState = {
            "messages": [HumanMessage(content=user_input)],
            "pending_tool_call": None,
        }

        config = {"configurable": {"session_id": session_id}}

        result = await self.graph.ainvoke(initial_state, config=config)
        last_message = result["messages"][-1]

        logger.info(
            f"Finished chat, final response length: len({str(last_message.content)})",
            extra={"session_id": session_id},
        )
        return str(last_message.content)

    async def stream(
        self, user_input: str, session_id: str | None = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream agent execution steps for real-time UI updates.

        Args:
            user_input: The user's message.
            session_id: Optional session identifier for tracking logs.

        Yields:
            Dicts with step type and content for UI rendering.
        """
        if not session_id:
            session_id = str(uuid.uuid4())

        logger.info(
            f"Starting stream with input: {user_input}",
            extra={"session_id": session_id},
        )

        initial_state: AgentState = {
            "messages": [HumanMessage(content=user_input)],
            "pending_tool_call": None,
        }

        config = {"configurable": {"session_id": session_id}}

        async for event in self.graph.astream_events(
            initial_state, config=config, version="v2"
        ):
            kind = event["event"]

            if kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    yield {"type": "token", "content": content}

            elif kind == "on_custom_event":
                custom_name = event["name"]
                if custom_name == "tool_call_start":
                    yield {
                        "type": "tool_start",
                        "name": event["data"]["tool"],
                        "input": event["data"].get("args", {}),
                    }
                elif custom_name == "tool_call_end":
                    yield {
                        "type": "tool_end",
                        "name": event["data"]["tool"],
                        "output": event["data"].get("output", ""),
                    }

        logger.info("Finished stream.", extra={"session_id": session_id})
