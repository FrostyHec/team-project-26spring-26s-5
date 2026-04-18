"""FastAPI application factory for the ReAct agent.

Assembles routers, middleware, and lifecycle hooks.
Follows a controller-service layering pattern:
  - Routes (controllers): api/routes/*.py
  - Dependencies (service DI): api/dependencies.py
  - Engine (service logic): engine/agent.py
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_core.api.dependencies import init_dependencies, shutdown_dependencies
from agent_core.api.routes.alarm_settings import router as alarm_settings_router
from agent_core.api.routes.chat import router as chat_router
from agent_core.api.routes.deadlines import router as deadlines_router
from agent_core.api.routes.email import router as email_router
from agent_core.api.routes.evaluate import router as evaluate_router
from agent_core.api.routes.health import router as health_router
from agent_core.api.routes.notifications import router as notifications_router
from agent_core.api.routes.sessions import router as sessions_router
from agent_core.api.routes.settings import router as settings_router
from agent_core.api.routes.skills import router as skills_router
from agent_core.api.routes.tools import router as tools_router
from agent_core.config import AgentConfig
from agent_core.logging_utils import setup_logger


def create_app(config: AgentConfig | None = None) -> FastAPI:
    """Create the FastAPI application.

    Args:
        config: Optional agent configuration. Defaults to env.

    Returns:
        Configured FastAPI app with all routes mounted.
    """
    init_config = config or AgentConfig.from_env()
    setup_logger(log_level=init_config.log_level, log_file=init_config.log_file)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        await init_dependencies(config)
        yield
        await shutdown_dependencies()

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

    # Mount routers (controllers)
    app.include_router(health_router)
    app.include_router(tools_router)
    app.include_router(skills_router)
    app.include_router(chat_router)
    app.include_router(sessions_router)
    app.include_router(deadlines_router)
    app.include_router(evaluate_router)
    app.include_router(settings_router)
    app.include_router(email_router)
    app.include_router(alarm_settings_router)
    app.include_router(notifications_router)

    return app
