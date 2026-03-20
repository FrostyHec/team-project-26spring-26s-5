"""FastAPI web API for the ReAct agent.

Structured as:
  - server.py: App factory (assembles routers + middleware)
  - dependencies.py: Dependency injection (agent lifecycle)
  - routes/: Individual endpoint routers (health, chat, tools)
"""

from agent_core.api.server import create_app

__all__ = ["create_app"]
