# Chainlit POC 前端实现详解

本文档详细说明 `packages/poc_frontend` 包的实现，即基于 Chainlit 框架的概念验证（POC）前端。

---

## 1. 概述

**文件：** `packages/poc_frontend/src/poc_frontend/app.py`

Chainlit POC 前端提供了一个开箱即用的对话 GUI，具备以下特性：

- 实时流式响应显示
- 思维链可视化（工具调用显示为可展开的步骤）
- 会话级 Agent 实例管理
- Token 逐字流式输出

---

## 2. 模块依赖

```python
from typing import Any

import chainlit as cl
from agent_core.config import AgentConfig
from agent_core.engine.agent import ReactAgent
from agent_core.tools.calculator import register_calculator_tools
from agent_core.tools.registry import ToolRegistry
```

- `chainlit`：Web 对话界面框架，提供 `@cl.on_chat_start`、`@cl.on_message` 等装饰器
- `agent_core`：核心引擎包，提供 Agent 引擎、工具注册、配置管理

---

## 3. Agent 工厂函数

```python
def _create_agent() -> ReactAgent:
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

- **与 CLI / Server 一致的工厂模式**：三个入口的 Agent 创建逻辑完全相同，保证行为一致性
- **延迟导入 `ChatOpenAI`**：在函数内部导入，避免 Chainlit 启动时不必要的依赖加载
- **条件参数传递**：`api_key` 和 `base_url` 仅在配置非空时传入

---

## 4. 会话初始化处理器

```python
@cl.on_chat_start
async def on_chat_start() -> None:
    agent = _create_agent()
    cl.user_session.set("agent", agent)
    await cl.Message(
        content="Hello! I'm a ReAct Agent with calculator tools. "
        "Ask me to perform calculations!"
    ).send()
```

### 执行流程

1. **创建 Agent**：每个新会话独立创建一个 `ReactAgent` 实例
2. **存入会话**：使用 `cl.user_session.set("agent", agent)` 将 Agent 绑定到当前用户会话
3. **发送欢迎消息**：通过 `cl.Message.send()` 显示欢迎提示

### 会话隔离

每个用户的浏览器连接会触发一次 `@cl.on_chat_start`，创建独立的 Agent 实例。这保证了多用户并发使用时的状态隔离——每个会话有自己的对话历史。

---

## 5. 消息处理器

```python
@cl.on_message
async def on_message(message: cl.Message) -> None:
    agent: ReactAgent = cl.user_session.get("agent")

    # 创建流式响应消息
    response_msg = cl.Message(content="")
    await response_msg.send()

    current_step: cl.Step | None = None

    async for event in agent.stream(message.content):
        event_type = event["type"]

        if event_type == "tool_start":
            current_step = cl.Step(
                name=f"Tool: {event['name']}",
                type="tool",
            )
            current_step.input = str(event.get("input", {}))
            await current_step.send()

        elif event_type == "tool_end":
            if current_step is not None:
                current_step.output = str(event.get("output", ""))
                await current_step.update()
                current_step = None

        elif event_type == "token":
            await response_msg.stream_token(event["content"])

    await response_msg.update()
```

### 5.1 整体流程

1. **获取 Agent**：从 `cl.user_session` 取出当前会话的 Agent 实例
2. **创建空响应消息**：先发送一个空的 `cl.Message`，后续通过 `stream_token` 逐步填充
3. **流式事件处理**：调用 `agent.stream(message.content)` 获取异步事件流
4. **最终更新**：流结束后调用 `response_msg.update()` 刷新最终状态

### 5.2 事件类型处理

#### `tool_start` — 工具调用开始

```python
current_step = cl.Step(
    name=f"Tool: {event['name']}",
    type="tool",
)
current_step.input = str(event.get("input", {}))
await current_step.send()
```

- 创建 `cl.Step` 对象，类型为 `"tool"`
- 名称格式为 `"Tool: <工具名>"`（如 `"Tool: add"`）
- 设置 `input` 为工具参数的字符串表示
- `send()` 后在 Chainlit UI 中显示为可展开的步骤卡片

#### `tool_end` — 工具调用结束

```python
if current_step is not None:
    current_step.output = str(event.get("output", ""))
    await current_step.update()
    current_step = None
```

- 更新当前 Step 的 `output` 字段
- 调用 `update()` 刷新 UI 显示
- 重置 `current_step` 为 `None`

#### `token` — 文本 Token 流

```python
await response_msg.stream_token(event["content"])
```

- 使用 `cl.Message.stream_token()` 逐 Token 追加到响应消息
- 在 Chainlit UI 中呈现为实时打字效果

### 5.3 思维链可视化效果

在 Chainlit 界面中，用户会看到类似以下的交互：

```
用户: What is 15 + 27?

  ▼ Tool: add
    Input: {'a': 15.0, 'b': 27.0}
    Output: 42.0

Agent: 15 + 27 = 42
```

工具调用步骤默认展开，用户可以折叠查看。这种可视化方式让用户清楚地了解 Agent 的推理过程。

---

## 6. Chainlit 配置

Chainlit 运行时会自动生成 `.chainlit/config.toml` 配置文件。项目使用默认配置即可运行。

### 启动方式

```bash
cd packages/poc_frontend
chainlit run src/poc_frontend/app.py
```

Chainlit 默认监听 `http://localhost:8000`，提供完整的 Web 对话界面。

---

## 7. 与其他前端的对比

| 特性 | Chainlit POC | Vue3 GUI | CLI |
|------|-------------|----------|-----|
| 界面类型 | Web GUI（Chainlit 内置） | Web GUI（自定义） | 终端 |
| 流式输出 | ✅ stream_token | ✅ SSE | ❌ 同步 |
| 工具调用可视化 | ✅ cl.Step | ✅ details 折叠 | ❌ |
| 会话管理 | ✅ cl.user_session | ❌ 无状态 | ❌ 单会话 |
| Agent 调用方式 | 直接 Python 调用 | HTTP API | 直接 Python 调用 |
| 适用场景 | 快速原型验证 | 生产级前端 | 开发调试 |

---

## 8. 关键设计决策

1. **直接调用 vs HTTP API**：Chainlit POC 直接导入并调用 `ReactAgent`，不经过 HTTP API 层。这简化了部署（单进程）但不利于前后端分离。
2. **会话级 Agent**：每个用户会话创建独立的 Agent，适合多用户场景，但无持久化存储。
3. **流式优先**：使用 `agent.stream()` 而非 `agent.chat()`，提供更好的用户体验。
4. **错误处理**：当前版本依赖 Chainlit 的默认错误处理机制，未在 `on_message` 中显式 try/except。
