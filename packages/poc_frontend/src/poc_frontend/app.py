"""Chainlit application for the ReAct Agent.

Provides a chat GUI with:
- Real-time streaming responses
- Thought trace display (tool calls shown as steps)
- Human-in-the-Loop confirmation for sensitive operations
"""

import json
from typing import Any

import chainlit as cl
from agent_core.config import AgentConfig
from agent_core.engine.agent import ReactAgent
from agent_core.logging_utils import setup_logger
from agent_core.models.events import EventType
from agent_core.tools.calculator import register_calculator_tools
from agent_core.tools.registry import ToolRegistry
from agent_core.tools.weather import register_weather_tools


def _create_agent() -> ReactAgent:
    """Create a configured ReactAgent instance.

    Returns:
        Configured ReactAgent.
    """
    from langchain_openai import ChatOpenAI

    config = AgentConfig.from_env()

    llm_kwargs: dict[str, Any] = {
        "model": config.model_name,
        "temperature": config.temperature,
    }
    if config.openai_api_key:
        llm_kwargs["api_key"] = config.openai_api_key
    if config.openai_base_url:
        llm_kwargs["base_url"] = config.openai_base_url

    llm = ChatOpenAI(**llm_kwargs)
    registry = ToolRegistry()
    register_calculator_tools(registry)
    register_weather_tools(registry)

    return ReactAgent(
        llm=llm,
        tool_registry=registry,
        system_prompt=config.system_prompt,
    )


async def _chainlit_approval_handler(
    tool_name: str, tool_args: dict[str, Any], tool_call_id: str
) -> bool:
    """Ask the user for approval before running a sensitive tool.

    Uses Chainlit's AskActionMessage to display a confirmation dialog.

    Args:
        tool_name: Name of the sensitive tool.
        tool_args: Arguments the LLM wants to pass.
        tool_call_id: Unique ID for this tool invocation.

    Returns:
        True if user approved, False otherwise.
    """
    args_str = json.dumps(tool_args, indent=2, ensure_ascii=False)
    res = await cl.AskActionMessage(
        content=(
            f"⚠️ **Sensitive Tool Detected**\n\n"
            f"The agent wants to call **{tool_name}** with:\n"
            f"```json\n{args_str}\n```\n\n"
            f"Do you approve this action?"
        ),
        actions=[
            cl.Action(
                name="approve",
                payload={"tool_call_id": tool_call_id},
                label="✅ Approve",
            ),
            cl.Action(
                name="reject", payload={"tool_call_id": tool_call_id}, label="❌ Reject"
            ),
        ],
        timeout=120,
    ).send()

    if res and res.get("name") == "approve":
        return True
    return False


@cl.on_chat_start
async def on_chat_start() -> None:
    """Initialize the agent when a new chat session starts."""
    # Ensure logs are set up (loads settings from env)
    config = AgentConfig.from_env()
    setup_logger(log_level=config.log_level, log_file=config.log_file)

    agent = _create_agent()
    agent.approval_handler = _chainlit_approval_handler
    cl.user_session.set("agent", agent)
    await cl.Message(
        content="Hello! I'm a ReAct Agent with calculator and weather tools. "
        "Ask me to perform calculations or check the weather!"
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Handle incoming user messages with linear thought trace.

    Displays the full ReAct loop as a linear trace:
    loop_start -> thinking -> tool_start -> tool_end -> ... -> loop_end

    Args:
        message: The incoming user message.
    """
    agent: ReactAgent = cl.user_session.get("agent")  # type: ignore[assignment]

    # Overall trace step for ReAct Loop details
    react_step = cl.Step(name="ReAct Engine Loop Trace", type="run")
    react_step.output = ""
    await react_step.send()

    # Create the response message for streaming
    response_msg = cl.Message(content="")
    await response_msg.send()

    current_tool_step: cl.Step | None = None
    session_id = cl.user_session.get("id", "chainlit_session")

    async for event in agent.stream(message.content, session_id=session_id):
        event_type = event["type"]

        if event_type == EventType.LOOP_START:
            react_step.output += "**ReAct loop started.**\n\n"
            await react_step.update()

        elif event_type == EventType.THINKING:
            # LLM reasoning before a tool call
            thinking_text = event.get("content", "")
            react_step.output += f"💭 **LLM Thinking:**\n> {thinking_text}\n\n"
            await react_step.update()

        elif event_type == EventType.APPROVAL_REQUEST:
            # Sensitive tool detected — show in trace
            tool_name = event.get("tool_name", "unknown")
            tool_args = event.get("tool_args", {})
            args_str = json.dumps(tool_args, indent=2, ensure_ascii=False)
            react_step.output += (
                f"⚠️ **Approval Required:** {tool_name}\n"
                f"```json\n{args_str}\n```\n"
                f"_Waiting for user decision..._\n\n"
            )
            await react_step.update()

        elif event_type == EventType.TOOL_START:
            tool_name = event["name"]
            input_data = event.get("input", {})
            input_str = json.dumps(input_data, indent=2, ensure_ascii=False)

            # Record in linear trace
            react_step.output += f"🔧 **Tool Call: {tool_name}**\n"
            await react_step.update()

            # Create collapsible child step for tool detail
            current_tool_step = cl.Step(
                name=f"Tool: {tool_name}",
                type="tool",
                parent_id=react_step.id,
            )
            current_tool_step.output = (
                f"### Input\n```json\n{input_str}\n```\n\n*Executing...*"
            )
            await current_tool_step.send()

        elif event_type == EventType.TOOL_END:
            output_data = str(event.get("output", ""))

            # Complete the child step
            if current_tool_step is not None:
                current_tool_step.output = current_tool_step.output.replace(
                    "*Executing...*",
                    f"### Output\n```\n{output_data}\n```",
                )
                await current_tool_step.update()
                current_tool_step = None

            # Record in linear trace with actual output
            react_step.output += f"✅ **Result:** `{output_data}`\n\n"
            await react_step.update()

        elif event_type == EventType.TOKEN:
            await response_msg.stream_token(event["content"])

        elif event_type == EventType.LOOP_END:
            react_step.output += "**ReAct loop finished.**"
            await react_step.update()

    await response_msg.update()
