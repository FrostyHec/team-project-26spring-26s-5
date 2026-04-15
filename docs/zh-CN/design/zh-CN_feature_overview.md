# 已实现功能模块概览

本文档概述 ReAct Agent 项目中所有已实现的功能模块，涵盖核心引擎、工具系统、API 层、CLI 前端及 Vue3 前端。

---

## 1. ReAct 引擎核心

**相关文件：**
- `packages/core/src/agent_core/engine/agent.py`
- `packages/core/src/agent_core/engine/state.py`

### 1.1 LangGraph StateGraph 工作流

引擎基于 **LangGraph** 的 `StateGraph` 实现 ReAct（Reasoning + Acting）循环推理模式。整体工作流如下：

```
用户输入 → reasoner 节点（LLM 推理）→ 条件边判断 → tool_executor 节点（工具执行）→ 回到 reasoner → … → END
```

- **`reasoner` 节点**：调用 LLM 决定下一步动作（直接回复或调用工具），支持 `system_prompt` 前置注入。
- **`tool_executor` 节点**：遍历 `AIMessage.tool_calls`，通过 `ToolRegistry.execute()` 异步执行工具，将结果封装为 `ToolMessage` 返回图中。
- **条件边 `_should_continue`**：检查最后一条消息是否为带 `tool_calls` 的 `AIMessage`，若是则路由到 `tool_executor`，否则结束（`END`）。

### 1.2 AgentState 状态定义

`AgentState` 是一个 `TypedDict`，使用 LangGraph 的 `add_messages` 注解实现消息列表的自动累积：

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    pending_tool_call: dict | None
```

- `messages`：对话历史，包含 `HumanMessage`、`AIMessage`、`ToolMessage` 等。
- `pending_tool_call`：为 HITL（Human-in-the-Loop）人工审批预留的字段。

### 1.3 异步对话与流式输出

`ReactAgent` 提供两种对话接口：

| 方法 | 说明 |
|------|------|
| `chat(user_input)` | 异步调用 `graph.ainvoke()`，返回最终文本响应 |
| `stream(user_input)` | 异步生成器，通过 `graph.astream_events(version="v2")` 逐步 yield 事件 |

流式事件类型：
- `on_chat_model_stream` → `{"type": "token", "content": "..."}`
- `on_tool_start` → `{"type": "tool_start", "name": "...", "input": {...}}`
- `on_tool_end` → `{"type": "tool_end", "name": "...", "output": "..."}`

---

## 2. 工具系统

**相关文件：**
- `packages/core/src/agent_core/tools/registry.py`
- `packages/core/src/agent_core/tools/calculator.py`

### 2.1 ToolRegistry 类

`ToolRegistry` 是工具的中央注册表，支持装饰器注册和编程式注册两种方式。

**核心方法：**

| 方法 | 说明 |
|------|------|
| `register(description, sensitivity, name)` | 装饰器，注册函数为工具 |
| `add_tool(func, description, sensitivity, name)` | 编程式注册 |
| `get(name)` | 按名称查找 `ToolDefinition` |
| `list_tools()` | 列出所有已注册工具 |
| `execute(name, args)` | 异步执行工具（同步函数自动包装到线程池） |
| `is_sensitive(name)` | 检查工具是否需要人工审批 |
| `get_langchain_tools()` | 转换为 LangChain `StructuredTool` 列表，用于 `llm.bind_tools()` |

### 2.2 ToolDefinition 数据类

基于 Pydantic `BaseModel`，定义工具的元数据：

```python
class ToolDefinition(BaseModel):
    name: str
    description: str
    func: Callable[..., Any]
    sensitivity: ToolSensitivity
```

### 2.3 ToolSensitivity 枚举（HITL）

```python
class ToolSensitivity(StrEnum):
    SAFE = "safe"
    SENSITIVE = "sensitive"
```

`SENSITIVE` 级别的工具在未来将触发人工确认流程。

### 2.4 独立 `@tool` 装饰器

模块级的 `tool()` 装饰器为函数附加 `_tool_meta` 属性，便于后续由 `ToolRegistry` 批量收集：

```python
@tool(description="Add two numbers")
def add(a: float, b: float) -> float:
    return a + b
```

### 2.5 Calculator 工具（POC 演示）

`register_calculator_tools(registry)` 函数注册四个基本计算工具：

| 工具名 | 说明 | 敏感度 |
|--------|------|--------|
| `add` | 两数相加 | SAFE |
| `subtract` | 两数相减 | SAFE |
| `multiply` | 两数相乘 | SAFE |
| `divide` | 两数相除（含除零保护） | SAFE |

---

## 3. API 层

**相关文件：**
- `packages/core/src/agent_core/api/server.py`
- `packages/core/src/agent_core/config.py`

### 3.1 FastAPI 应用

通过 `create_app(config)` 工厂函数创建 FastAPI 应用，使用 `asynccontextmanager` 的 `lifespan` 模式在启动时初始化 `ReactAgent`，关闭时清理。

**中间件：** CORS 全开放（`allow_origins=["*"]`），支持跨域调用。

### 3.2 API 端点

| 端点 | 方法 | 请求体 | 响应 | 说明 |
|------|------|--------|------|------|
| `/health` | GET | — | `{"status": "ok"}` | 健康检查 |
| `/tools` | GET | — | `ToolInfo[]` | 列出所有可用工具 |
| `/chat` | POST | `ChatRequest{message}` | `ChatResponse{response}` | 同步对话 |
| `/chat/stream` | POST | `ChatRequest{message}` | SSE 流 | 流式对话 |

### 3.2.1 Email API 错误语义（A003 修复）

邮件相关端点在“凭据未配置”场景下统一返回机器可读错误：

- **状态码**：`428 Precondition Required`
- **错误码**：`EMAIL_CREDENTIALS_MISSING`
- **响应结构**：

```json
{
    "detail": {
        "code": "EMAIL_CREDENTIALS_MISSING",
        "message": "Email credentials not configured..."
    }
}
```

这样前端可以精确识别并给出友好引导，而不是仅显示模糊的 `400` 文本。

### 3.3 错误处理

- **同步对话 `/chat`**：LLM 调用失败时抛出 `HTTPException(status_code=502)`，明确表示上游服务错误。
- **流式对话 `/chat/stream`**：异常被捕获后以 `{"type": "error", "content": "..."}` 事件通过 SSE 发送，流正常结束。
- SSE 流结束标记：`data: [DONE]`

### 3.4 AgentConfig 配置

基于 `@dataclass` 的配置类，通过 `python-dotenv` 从 `.env` 文件加载环境变量：

| 配置项 | 环境变量 | 默认值 |
|--------|----------|--------|
| `openai_api_key` | `OPENAI_API_KEY` | `""` |
| `openai_base_url` | `OPENAI_BASE_URL` | `""` |
| `model_name` | `MODEL_NAME` | `"gpt-4o-mini"` |
| `temperature` | `TEMPERATURE` | `0.0` |
| `max_iterations` | `MAX_ITERATIONS` | `10` |
| `system_prompt` | `SYSTEM_PROMPT` | 内置默认提示词 |

### 3.5 公共 API

`packages/core/src/agent_core/__init__.py` 导出三个核心接口：

```python
__all__ = ["ReactAgent", "ToolRegistry", "tool"]
```

---

## 4. CLI 前端

**相关文件：**
- `packages/cli/src/agent_cli/main.py`

### 4.1 子命令架构

使用 `argparse` 实现两个子命令：

| 子命令 | 说明 |
|--------|------|
| `agent-cli chat` | 启动交互式终端对话 |
| `agent-cli serve` | 启动 FastAPI 服务器（支持 `--host` 和 `--port` 参数） |

### 4.2 核心功能

- **`_create_agent_from_config()`**：工厂函数，从 `AgentConfig.from_env()` 加载配置，创建 `ChatOpenAI` + `ToolRegistry` + `ReactAgent` 实例。
- **`_chat_loop()`**：异步交互循环，读取用户输入，调用 `agent.chat()`，支持 `quit`/`exit`/`Ctrl+C` 退出。
- **`run_server()`**：调用 `create_app()` 创建 FastAPI 应用，通过 `uvicorn.run()` 启动 HTTP 服务。

---

## 5. Vue3 前端

**相关文件：**
- `packages/gui/src/api/agent.ts`
- `packages/gui/src/stores/chat.ts`
- `packages/gui/src/views/ChatView.vue`
- `packages/gui/src/router/index.ts`
- `packages/gui/vite.config.ts`

### 6.1 API 客户端层（`agent.ts`）

| 函数 | 说明 |
|------|------|
| `fetchTools()` | GET `/api/tools`，获取可用工具列表 |
| `sendMessage(message)` | POST `/api/chat`，同步对话 |
| `streamMessage(message)` | POST `/api/chat/stream`，AsyncGenerator 逐条 yield `AgentEvent` |
| `checkHealth()` | GET `/api/health`，检查后端连通性 |

SSE 解析实现：使用 `ReadableStream` 的 `getReader()` 逐块读取，按 `data: ` 前缀解析 JSON，遇到 `[DONE]` 标记结束。

### 6.2 状态管理（`chat.ts` Pinia Store）

基于 **Pinia** 的 `defineStore` 实现响应式状态管理：

**状态：**
- `messages: ChatMessage[]` — 消息列表（含 `toolCalls` 数组）
- `isLoading: boolean` — 加载状态
- `isConnected: boolean` — 后端连接状态
- `error: string | null` — 错误信息

**Actions：**
- `sendMessage(content)` — 添加用户消息占位 → 创建助手消息占位 → 流式消费 `streamMessage()` → 实时更新内容和工具调用状态
- `clearMessages()` — 清空消息列表
- `checkConnection()` — 调用 `checkHealth()` 更新连接状态

**工具调用追踪：** `ToolCallInfo` 接口包含 `name`、`input`、`output`、`status`（`running` | `completed` | `error`），在 `tool_start` 时创建、`tool_end` 时更新。

### 6.3 对话视图（`ChatView.vue`）

基于 **Vue3 Composition API** 的单文件组件：

- **连接状态栏**：显示连接/断开状态，提供 Retry 和 Clear 按钮
- **消息列表**：根据 `role` 区分用户/助手样式，助手消息中展示可折叠的工具调用详情（`<details>` 标签）
- **输入区域**：`<textarea>` + Send 按钮，支持 Enter 快捷发送（Shift+Enter 换行）
- **自动滚动**：通过 `watch` 监听消息数量变化，`nextTick` 后自动滚动到底部
- **加载指示器**：脉冲动画提示等待中
- **错误显示栏**：底部红色提示条

### 6.4 路由与开发服务器

- **Vue Router**：单路由 `/` 指向 `ChatView` 组件，使用 `createWebHistory` 模式。
- **Vite 代理**：开发模式下 `/api` 路径代理到 `http://localhost:8000`，去除 `/api` 前缀后转发。

### 6.5 Inbox 邮件功能稳定性修复（A003）

- **i18n 编译错误修复**：修复邮件编辑/写信界面中占位文案触发 `Invalid linked format` 的问题，确保点击“写邮件/回复”可正常打开编辑界面。
- **错误提示可读性提升**：邮箱凭据缺失时，前端通过错误码识别并弹窗提示用户先到设置页配置邮箱账号和密码。
- **API 客户端错误解析统一化**：`src/api/email.ts` 统一解析后端 `detail`（字符串或对象），保留错误码用于界面分支处理。

---

## 模块依赖关系

```
┌─────────────────────────────────────────────────────────────┐
│                      前端层                                  │
│  ┌──────────┐  ┌───────────────────────┐  │
│  │ CLI      │  │ Vue3 GUI              │  │
│  │ (chat/   │  │ (agent.ts/chat.ts/    │  │
│  │  serve)  │  │  ChatView.vue)        │  │
│  └────┬─────┘  └──────────┬────────────┘  │
│       │                   │               │
│       │   直接调用        │ HTTP /api     │
│       ▼                   ▼               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              API 层 (server.py)                       │   │
│  │  /health  /tools  /chat  /chat/stream                │   │
│  └────────────────────────┬─────────────────────────────┘   │
│                           │                                  │
│                           ▼                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │          引擎核心 (agent.py + state.py)               │   │
│  │  ReactAgent → LangGraph StateGraph → LLM             │   │
│  └────────────────────────┬─────────────────────────────┘   │
│                           │                                  │
│                           ▼                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │        工具系统 (registry.py + calculator.py)         │   │
│  │  ToolRegistry → ToolDefinition → LangChain Tools     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              配置 (config.py + .env)                   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```
