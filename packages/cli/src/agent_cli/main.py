"""CLI entry point for the ReAct agent.

Provides a simple interactive command-line chat interface
and a server launch command.
"""

import argparse
import asyncio
import sys

from agent_core.api.server import create_app
from agent_core.config import AgentConfig
from agent_core.engine.agent import ReactAgent
from agent_core.tools.calculator import register_calculator_tools
from agent_core.tools.registry import ToolRegistry


def _create_agent_from_config() -> ReactAgent:
    """Create agent from environment configuration.

    Returns:
        Configured ReactAgent instance.
    """
    from typing import Any

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


async def _chat_loop() -> None:
    """Run an interactive chat loop in the terminal."""
    print("ReAct Agent CLI")
    print("Type 'quit' or 'exit' to stop.\n")

    agent = _create_agent_from_config()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        try:
            response = await agent.chat(user_input)
            print(f"Agent: {response}\n")
        except Exception as e:
            print(f"Error: {e}\n")


def run_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Start the FastAPI server.

    Args:
        host: Server host address.
        port: Server port number.
    """
    import uvicorn

    app = create_app()
    uvicorn.run(app, host=host, port=port)


def main() -> None:
    """CLI entry point with subcommands."""
    parser = argparse.ArgumentParser(
        description="ReAct Agent CLI",
        prog="agent-cli",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Chat subcommand
    subparsers.add_parser("chat", help="Start interactive chat session")

    # Server subcommand
    server_parser = subparsers.add_parser("serve", help="Start API server")
    server_parser.add_argument(
        "--host", default="0.0.0.0", help="Server host (default: 0.0.0.0)"
    )
    server_parser.add_argument(
        "--port", type=int, default=8000, help="Server port (default: 8000)"
    )

    args = parser.parse_args()

    if args.command == "chat":
        asyncio.run(_chat_loop())
    elif args.command == "serve":
        run_server(host=args.host, port=args.port)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
