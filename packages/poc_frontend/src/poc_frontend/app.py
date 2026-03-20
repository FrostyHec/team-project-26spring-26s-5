"""Chainlit application for the ReAct Agent.

Provides a chat GUI with:
- Real-time streaming responses
- Thought trace display (tool calls shown as steps)
- Human-in-the-Loop confirmation for sensitive operations
"""

from typing import Any

import chainlit as cl
from agent_core.config import AgentConfig
from agent_core.engine.agent import ReactAgent
from agent_core.logging_utils import setup_logger
from agent_core.models.events import EventType
from agent_core.tools.calculator import register_calculator_tools
from agent_core.tools.registry import ToolRegistry


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

    return ReactAgent(
        llm=llm,
        tool_registry=registry,
        system_prompt=config.system_prompt,
    )


@cl.on_chat_start
async def on_chat_start() -> None:
    """Initialize the agent when a new chat session starts."""
    # Ensure logs are set up (loads settings from env)
    config = AgentConfig.from_env()
    setup_logger(log_level=config.log_level, log_file=config.log_file)

    agent = _create_agent()
    cl.user_session.set("agent", agent)
    await cl.Message(
        content="Hello! I'm a ReAct Agent with calculator tools. "
        "Ask me to perform calculations!"
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Handle incoming user messages with streaming thought trace.

    Shows tool calls as expandable steps in the Chainlit UI.

    Args:
        message: The incoming user message.
    """
    import json

    agent: ReactAgent = cl.user_session.get("agent")  # type: ignore[assignment]

    # Overall trace step for ReAct Loop details
    react_step = cl.Step(name="ReAct Engine Loop Trace", type="run")
    await react_step.send()

    # Create the response message for streaming
    response_msg = cl.Message(content="")
    await response_msg.send()

    current_tool_step: cl.Step | None = None

    react_step.output = "**ReAct loop started.**\n\n"
    await react_step.update()

    session_id = cl.user_session.get("id", "chainlit_session")

    async for event in agent.stream(message.content, session_id=session_id):
        event_type = event["type"]

        if event_type == EventType.TOOL_START:
            tool_name = event["name"]
            input_data = event.get("input", {})
            input_str = json.dumps(input_data, indent=2, ensure_ascii=False)

            # Record in parent step
            react_step.output += f"- `🔧 Tool Initiated`: **{tool_name}**\n"
            await react_step.update()

            # Create specific tool child step
            current_tool_step = cl.Step(
                name=f"Tool Execution: {tool_name}",
                type="tool",
                parent_id=react_step.id,
            )
            current_tool_step.output = (
                f"### Input Payload\n```json\n{input_str}\n```\n\n"
                "*Waiting for execution...*"
            )
            await current_tool_step.send()

        elif event_type == EventType.TOOL_END:
            # Complete the tool step with output
            if current_tool_step is not None:
                output_data = str(event.get("output", ""))

                # Update specific tool child step
                current_tool_step.output = current_tool_step.output.replace(
                    "*Waiting for execution...*",
                    f"### Execution Result\n```\n{output_data}\n```",
                )
                await current_tool_step.update()
                current_tool_step = None

                # Record in parent step
                react_step.output += (
                    f"- `✅ Tool Completed`: "
                    f"Returned output length {len(output_data)}\n"
                )
                await react_step.update()

        elif event_type == EventType.TOKEN:
            # Stream text tokens to the response
            await response_msg.stream_token(event["content"])

    react_step.output += "\n**ReAct loop finished successfully.**"
    await react_step.update()
    await response_msg.update()
