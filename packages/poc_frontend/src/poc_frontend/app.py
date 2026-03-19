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
    agent: ReactAgent = cl.user_session.get("agent")  # type: ignore[assignment]

    # Create the response message for streaming
    response_msg = cl.Message(content="")
    await response_msg.send()

    current_step: cl.Step | None = None

    async for event in agent.stream(message.content):
        event_type = event["type"]

        if event_type == "tool_start":
            # Show tool call as a step
            current_step = cl.Step(
                name=f"Tool: {event['name']}",
                type="tool",
            )
            current_step.input = str(event.get("input", {}))
            await current_step.send()

        elif event_type == "tool_end":
            # Complete the tool step with output
            if current_step is not None:
                current_step.output = str(event.get("output", ""))
                await current_step.update()
                current_step = None

        elif event_type == "token":
            # Stream text tokens to the response
            await response_msg.stream_token(event["content"])

    await response_msg.update()
