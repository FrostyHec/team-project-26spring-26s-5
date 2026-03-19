"""FastAPI server for the ReAct agent.

Provides REST API endpoints for interacting with the agent,
including chat and streaming responses.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent_core.config import AgentConfig
from agent_core.engine.agent import ReactAgent
from agent_core.tools.calculator import register_calculator_tools
from agent_core.tools.registry import ToolRegistry


class ChatRequest(BaseModel):
    """Request body for chat endpoint.

    Attributes:
        message: The user's message to the agent.
    """

    message: str


class ChatResponse(BaseModel):
    """Response body from chat endpoint.

    Attributes:
        response: The agent's text response.
    """

    response: str


class ToolInfo(BaseModel):
    """Information about a registered tool.

    Attributes:
        name: Tool name.
        description: Tool description.
        sensitivity: HITL sensitivity level.
    """

    name: str
    description: str
    sensitivity: str


# Module-level agent instance (initialized in lifespan)
_agent: ReactAgent | None = None


def _create_agent(config: AgentConfig | None = None) -> ReactAgent:
    """Create and configure a ReactAgent instance.

    Args:
        config: Optional configuration. Uses env if not provided.

    Returns:
        Configured ReactAgent.
    """
    if config is None:
        config = AgentConfig.from_env()

    from langchain_openai import ChatOpenAI

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


def create_app(config: AgentConfig | None = None) -> FastAPI:
    """Create the FastAPI application.

    Args:
        config: Optional agent configuration.

    Returns:
        Configured FastAPI app.
    """
    global _agent

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        global _agent
        _agent = _create_agent(config)
        yield
        _agent = None

    app = FastAPI(
        title="ReAct Agent API",
        description="REST API for the ReAct AI Agent",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok"}

    @app.get("/tools", response_model=list[ToolInfo])
    async def list_tools() -> list[ToolInfo]:
        """List all available tools."""
        assert _agent is not None
        tools = _agent.tool_registry.list_tools()
        return [
            ToolInfo(
                name=t.name,
                description=t.description,
                sensitivity=t.sensitivity.value,
            )
            for t in tools
        ]

    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        """Send a message and get a response."""
        assert _agent is not None
        response = await _agent.chat(request.message)
        return ChatResponse(response=response)

    @app.post("/chat/stream")
    async def chat_stream(request: ChatRequest) -> StreamingResponse:
        """Stream agent execution steps as SSE."""
        assert _agent is not None

        async def event_generator() -> AsyncGenerator[str, None]:
            import json

            async for event in _agent.stream(request.message):
                yield f"data: {json.dumps(event)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
        )

    return app
