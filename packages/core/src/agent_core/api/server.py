"""FastAPI application factory for the ReAct agent.

Assembles routers, middleware, and lifecycle hooks.
Follows a controller-service layering pattern:
  - Routes (controllers): api/routes/*.py
  - Dependencies (service DI): api/dependencies.py
  - Engine (service logic): engine/agent.py
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_core.api.dependencies import init_dependencies, shutdown_dependencies
from agent_core.api.routes.alarm_settings import router as alarm_settings_router
from agent_core.api.routes.chat import router as chat_router
from agent_core.api.routes.course_materials import router as course_materials_router
from agent_core.api.routes.courses import router as courses_router
from agent_core.api.routes.deadlines import router as deadlines_router
from agent_core.api.routes.email import router as email_router
from agent_core.api.routes.evaluate import router as evaluate_router
from agent_core.api.routes.files import router as files_router
from agent_core.api.routes.health import router as health_router
from agent_core.api.routes.news import router as news_router
from agent_core.api.routes.notifications import router as notifications_router
from agent_core.api.routes.sessions import router as sessions_router
from agent_core.api.routes.settings import router as settings_router
from agent_core.api.routes.skills import router as skills_router
from agent_core.api.routes.tools import router as tools_router
from agent_core.api.routes.wrong_questions import router as wrong_questions_router
from agent_core.config import AgentConfig
from agent_core.logging_utils import setup_logger
from agent_core.policy_search.config import PolicySearchConfig
from agent_core.policy_search.index import log_index_startup_check

API_ROUTERS: tuple[APIRouter, ...] = (
    health_router,
    tools_router,
    skills_router,
    chat_router,
    sessions_router,
    deadlines_router,
    courses_router,
    course_materials_router,
    evaluate_router,
    settings_router,
    email_router,
    news_router,
    alarm_settings_router,
    notifications_router,
    wrong_questions_router,
)


def _resolve_config(config: AgentConfig | None = None) -> AgentConfig:
    """Resolve and initialize runtime configuration shared by app factories."""
    init_config = config or AgentConfig.from_env()
    setup_logger(log_level=init_config.log_level, log_file=init_config.log_file)
    return init_config


def _create_lifespan(config: AgentConfig) -> object:
    """Create a shared FastAPI lifespan handler for all API app variants."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        await init_dependencies(config)
        policy_config = PolicySearchConfig.from_env()
        log_index_startup_check(policy_config.index_dir)
        yield
        await shutdown_dependencies()

    return lifespan


def _configure_middleware(app: FastAPI) -> None:
    """Configure middleware shared by normal and packaged apps."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _include_api_routers(
    app: FastAPI,
    *,
    prefix: str = "",
    include_files: bool = True,
) -> None:
    """Mount API routers with an optional prefix.

    Args:
        app: FastAPI application to mutate.
        prefix: Prefix for business API routers.
        include_files: Whether to include the top-level files router.
    """
    for router in API_ROUTERS:
        app.include_router(router, prefix=prefix)
    if include_files:
        app.include_router(files_router, prefix="/files", tags=["files"])


def _create_base_app(config: AgentConfig) -> FastAPI:
    """Create the shared FastAPI shell before router/static mounting."""
    return FastAPI(
        title="ReAct Agent API",
        description="REST API for the ReAct AI Agent",
        version="0.1.0",
        lifespan=_create_lifespan(config),
    )


def create_app(config: AgentConfig | None = None) -> FastAPI:
    """Create the FastAPI application.

    Args:
        config: Optional agent configuration. Defaults to env.

    Returns:
        Configured FastAPI app with all routes mounted.
    """
    init_config = _resolve_config(config)
    app = _create_base_app(init_config)
    _configure_middleware(app)
    _include_api_routers(app)

    return app
