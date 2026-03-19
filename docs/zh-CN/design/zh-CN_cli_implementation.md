# CLI 实现详解

本文档详细说明 `packages/cli` 包的实现，即 ReAct Agent 的命令行交互前端。

---

## 1. 概述

**文件：** `packages/cli/src/agent_cli/main.py`

CLI 包提供了一个轻量级的命令行入口，包含两个子命令：

- `agent-cli chat`：启动终端交互式对话
- `agent-cli serve`：启动 FastAPI HTTP 服务器

CLI 依赖 `agent_core` 包，通过 `[project.scripts]` 注册为可执行命令。

---

## 2. 模块依赖

```python
import argparse
import asyncio
import sys

from agent_core.api.server import create_app
from agent_core.config import AgentConfig
from agent_core.engine.agent import ReactAgent
from agent_core.tools.calculator import register_calculator_tools
from agent_core.tools.registry import ToolRegistry
```

CLI 从 `agent_core` 导入以下组件：
- `create_app`：FastAPI 应用工厂，用于 `serve` 子命令
- `AgentConfig`：配置管理，从 `.env` 加载
- `ReactAgent`：核心引擎，用于 `chat` 子命令
- `ToolRegistry` + `register_calculator_tools`：工具注册

---

## 3. Agent 工厂函数

```python
def _create_agent_from_config() -> ReactAgent:
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
```

### 设计要点

- **延迟导入**：`ChatOpenAI` 和 `Any` 在函数内部导入，避免顶层导入 `langchain_openai` 可能带来的启动时间开销
- **条件参数**：`api_key` 和 `base_url` 仅在配置中非空时传入 `llm_kwargs`，兼容纯环境变量配置和自定义 API 代理场景
- **与 `server.py` 的 `_create_agent()` 模式一致**：相同的工厂函数模式保证了所有入口（CLI、Server、Chainlit）创建的 Agent 行为一致

---

## 4. 交互式对话循环

```python
async def _chat_loop() -> None:
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
```

### 执行流程

1. **初始化**：打印欢迎信息，调用 `_create_agent_from_config()` 创建 Agent
2. **循环读取**：使用 `input()` 阻塞读取用户输入
3. **退出条件**：
   - 输入 `quit` 或 `exit`（大小写不敏感）
   - `Ctrl+C`（`KeyboardInterrupt`）或 `Ctrl+D`（`EOFError`）
4. **空输入跳过**：`strip()` 后的空字符串直接 `continue`
5. **异步调用**：使用 `agent.chat(user_input)` 进行对话，注意此函数本身是 `async`，通过 `asyncio.run()` 启动
6. **错误处理**：捕获所有异常并打印错误信息，不中断对话循环

---

## 5. 服务器启动

```python
def run_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    import uvicorn

    app = create_app()
    uvicorn.run(app, host=host, port=port)
```

- 调用 `agent_core.api.server.create_app()` 创建 FastAPI 应用
- 使用 `uvicorn.run()` 同步启动 ASGI 服务器
- 默认监听 `0.0.0.0:8000`，可通过命令行参数覆盖

---

## 6. 入口函数与 argparse 配置

```python
def main() -> None:
    parser = argparse.ArgumentParser(
        description="ReAct Agent CLI",
        prog="agent-cli",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Chat 子命令
    subparsers.add_parser("chat", help="Start interactive chat session")

    # Serve 子命令
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
```

### 子命令详情

| 子命令 | 参数 | 默认值 | 说明 |
|--------|------|--------|------|
| `chat` | 无 | — | 启动交互式终端对话 |
| `serve` | `--host` | `0.0.0.0` | 服务器监听地址 |
| `serve` | `--port` | `8000` | 服务器监听端口 |

### 命令分发

- `chat` → `asyncio.run(_chat_loop())`：启动异步事件循环运行交互对话
- `serve` → `run_server(host, port)`：启动 HTTP 服务器
- 无命令 → 打印帮助信息并以状态码 1 退出

### `__main__` 入口

```python
if __name__ == "__main__":
    main()
```

支持直接运行 `python -m agent_cli.main`。

---

## 7. 包注册

CLI 包通过 `pyproject.toml` 的 `[project.scripts]` 注册为命令行工具：

```toml
[project.scripts]
agent-cli = "agent_cli.main:main"
```

安装后可直接使用：

```bash
agent-cli chat        # 交互式对话
agent-cli serve       # 启动服务器
agent-cli serve --port 9000  # 自定义端口
```

---

## 8. 使用示例

### 交互式对话

```
$ agent-cli chat
ReAct Agent CLI
Type 'quit' or 'exit' to stop.

You: What is 42 + 58?
Agent: 42 + 58 = 100

You: quit
Goodbye!
```

### 启动服务器

```
$ agent-cli serve --host 127.0.0.1 --port 8080
INFO:     Started server process
INFO:     Uvicorn running on http://127.0.0.1:8080
```
