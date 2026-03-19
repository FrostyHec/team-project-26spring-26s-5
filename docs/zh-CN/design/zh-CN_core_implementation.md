# Core 核心引擎实现详解

本文档深入分析 `packages/core` 包的实现细节，包括 ReAct 引擎、工具系统、API 服务器和配置管理。

---

## 1. ReactAgent 类架构

**文件：** `packages/core/src/agent_core/engine/agent.py`

### 1.1 类概述

`ReactAgent` 是整个系统的核心，实现了 ReAct（Reasoning + Acting）模式的推理循环。通过 LangGraph 的 `StateGraph` 编排 LLM 推理与工具执行的交替过程。

```python
class ReactAgent:
    def __init__(self, llm, tool_registry, system_prompt=""):
        self.llm = llm
        self.tool_registry = tool_registry
        self.system_prompt = system_prompt
        lc_tools = self.tool_registry.get_langchain_tools()
        self.llm_with_tools = self.llm.bind_tools(lc_tools) if lc_tools else self.llm
        self.graph = self._build_graph()
```

**构造函数职责：**
1. 接收 LangChain 兼容的 LLM 实例和 `ToolRegistry`
2. 通过 `get_langchain_tools()` 将注册工具转换为 LangChain `StructuredTool` 格式
3. 调用 `llm.bind_tools()` 将工具绑定到 LLM（若无工具则使用原始 LLM）
4. 调用 `_build_graph()` 构建并编译 LangGraph 状态图

### 1.2 `_build_graph()` — 构建 LangGraph 状态图

```python
def _build_graph(self) -> Any:
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("reasoner", self._reason)
    workflow.add_node("tool_executor", self._execute_tools)

    # 设置入口点
    workflow.set_entry_point("reasoner")

    # 添加条件边
    workflow.add_conditional_edges(
        "reasoner",
        self._should_continue,
        {"continue": "tool_executor", "end": END},
    )
    workflow.add_edge("tool_executor", "reasoner")

    return workflow.compile()
```

**状态图结构：**

```
                    ┌───────────┐
                    │  START    │
                    └─────┬─────┘
                          │
                          ▼
                ┌─────────────────┐
         ┌──────│   reasoner      │◄─────────┐
         │      │  (LLM 推理)     │           │
         │      └─────────────────┘           │
         │              │                     │
         │    _should_continue()              │
         │              │                     │
    "end" │      "continue"                   │
         │              │                     │
         │              ▼                     │
         │    ┌─────────────────┐             │
         │    │ tool_executor   │─────────────┘
         │    │ (工具执行)       │
         │    └─────────────────┘
         │
         ▼
    ┌─────────┐
    │   END   │
    └─────────┘
```

### 1.3 `_reason()` — LLM 推理节点

```python
async def _reason(self, state: AgentState) -> dict:
    messages = list(state["messages"])

    if self.system_prompt:
        from langchain_core.messages import SystemMessage
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=self.system_prompt)] + messages

    response = await self.llm_with_tools.ainvoke(messages)
    return {"messages": [response]}
```

**关键逻辑：**
- 复制 `state["messages"]` 避免修改原始状态
- **System Prompt 注入**：若设置了 `system_prompt`，检查消息列表首条是否已为 `SystemMessage`，若不是则前置插入
- 使用 `ainvoke` 异步调用绑定了工具的 LLM
- 返回 `{"messages": [response]}`，LangGraph 通过 `add_messages` 注解自动追加到消息列表

### 1.4 `_should_continue()` — 条件边判断

```python
def _should_continue(self, state: AgentState) -> str:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "continue"
    return "end"
```

判断逻辑简洁：检查最后一条消息是否为 `AIMessage` 且包含 `tool_calls`。若是，路由到 `tool_executor` 继续执行；否则结束循环。

### 1.5 `_execute_tools()` — 工具执行节点

```python
async def _execute_tools(self, state: AgentState) -> dict:
    last_message = state["messages"][-1]
    tool_messages = []

    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]

            try:
                result = await self.tool_registry.execute(tool_name, tool_args)
                tool_messages.append(
                    ToolMessage(content=str(result), tool_call_id=tool_id)
                )
            except Exception as e:
                tool_messages.append(
                    ToolMessage(content=f"Error: {e}", tool_call_id=tool_id)
                )

    return {"messages": tool_messages}
```

**关键设计：**
- 遍历所有 `tool_calls`，逐一调用 `self.tool_registry.execute()`
- 每次工具调用结果包装为 `ToolMessage`，通过 `tool_call_id` 关联请求
- **错误隔离**：单个工具执行失败不影响其他工具，错误信息作为 `ToolMessage` 返回给 LLM，由 LLM 决定后续行为

### 1.6 `chat()` — 同步对话接口

```python
async def chat(self, user_input: str) -> str:
    initial_state: AgentState = {
        "messages": [HumanMessage(content=user_input)],
        "pending_tool_call": None,
    }
    result = await self.graph.ainvoke(initial_state)
    last_message = result["messages"][-1]
    return str(last_message.content)
```

构造初始状态，使用 `graph.ainvoke()` 运行完整的推理-执行循环，返回最终 `AIMessage` 的文本内容。

### 1.7 `stream()` — 流式对话接口

```python
async def stream(self, user_input: str) -> AsyncGenerator[dict[str, Any], None]:
    initial_state: AgentState = {
        "messages": [HumanMessage(content=user_input)],
        "pending_tool_call": None,
    }

    async for event in self.graph.astream_events(initial_state, version="v2"):
        kind = event["event"]

        if kind == "on_chat_model_stream":
            content = event["data"]["chunk"].content
            if content:
                yield {"type": "token", "content": content}

        elif kind == "on_tool_start":
            yield {
                "type": "tool_start",
                "name": event["name"],
                "input": event["data"].get("input", {}),
            }

        elif kind == "on_tool_end":
            yield {
                "type": "tool_end",
                "name": event["name"],
                "output": event["data"].get("output", ""),
            }
```

**事件映射：**

| LangGraph 事件 | 输出事件类型 | 内容 |
|-----------------|-------------|------|
| `on_chat_model_stream` | `token` | LLM 生成的文本片段 |
| `on_tool_start` | `tool_start` | 工具名称 + 输入参数 |
| `on_tool_end` | `tool_end` | 工具名称 + 执行结果 |

使用 `astream_events(version="v2")` 是 LangGraph 推荐的流式事件 API，提供细粒度的执行过程追踪。

---

## 2. AgentState 状态定义

**文件：** `packages/core/src/agent_core/engine/state.py`

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    pending_tool_call: dict | None
```

### 2.1 `messages` 字段

- 类型：`Annotated[list, add_messages]`
- `add_messages` 是 LangGraph 提供的 **Reducer 函数**，在图的每个节点返回 `{"messages": [...]}` 时，自动将新消息追加到已有列表中，而非覆盖
- 消息类型涵盖 LangChain 的 `HumanMessage`、`AIMessage`、`SystemMessage`、`ToolMessage`

### 2.2 `pending_tool_call` 字段

- 类型：`dict | None`
- 当前未启用，为 HITL 功能预留
- 设计意图：当 LLM 请求执行 `SENSITIVE` 级别工具时，将工具调用信息暂存于此，等待人工审批后再执行

---

## 3. ToolRegistry 工具注册表

**文件：** `packages/core/src/agent_core/tools/registry.py`

### 3.1 注册方式

**方式一：装饰器注册**

```python
registry = ToolRegistry()

@registry.register(description="Add two numbers", sensitivity=ToolSensitivity.SAFE)
def add(a: float, b: float) -> float:
    return a + b
```

装饰器内部创建 `ToolDefinition` 对象并存入 `self._tools` 字典。装饰器返回原始函数不做修改。

**方式二：编程式注册**

```python
registry.add_tool(func=add, description="Add two numbers")
```

效果等价，适用于动态注册场景。

**方式三：独立 `@tool` 装饰器**

```python
@tool(description="Add two numbers")
def add(a: float, b: float) -> float:
    return a + b
```

此装饰器不直接注册到 Registry，而是在函数上附加 `_tool_meta` 属性：

```python
func._tool_meta = {
    "description": description,
    "sensitivity": sensitivity,
    "name": name or func.__name__,
}
```

便于后续由 ToolRegistry 批量扫描和收集。

### 3.2 工具执行

```python
async def execute(self, name: str, args: dict[str, Any]) -> Any:
    tool_def = self._tools.get(name)
    if tool_def is None:
        raise KeyError(f"Tool '{name}' is not registered")

    func = tool_def.func
    if inspect.iscoroutinefunction(func):
        return await func(**args)
    else:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(**args))
```

**异步执行策略：**
- 若工具函数为 `async` 协程，直接 `await` 调用
- 若为同步函数，通过 `run_in_executor(None, ...)` 在线程池中执行，避免阻塞事件循环

### 3.3 LangChain 工具转换

```python
def get_langchain_tools(self) -> list[StructuredTool]:
    lc_tools = []
    for tool_def in self._tools.values():
        lc_tool = StructuredTool.from_function(
            func=tool_def.func,
            name=tool_def.name,
            description=tool_def.description,
        )
        lc_tools.append(lc_tool)
    return lc_tools
```

使用 `StructuredTool.from_function()` 将内部工具定义转换为 LangChain 格式。LangChain 会自动从函数签名的类型注解推断参数 Schema，供 LLM 的 `bind_tools()` 使用。

---

## 4. Calculator 工具（POC 演示）

**文件：** `packages/core/src/agent_core/tools/calculator.py`

`register_calculator_tools()` 函数接收一个 `ToolRegistry` 实例，通过装饰器模式注册四个基本计算工具：

```python
def register_calculator_tools(registry: ToolRegistry) -> None:
    @registry.register(description="Add two numbers together. Args: a (float), b (float).")
    def add(a: float, b: float) -> float:
        return a + b

    @registry.register(description="Subtract b from a. Args: a (float), b (float).")
    def subtract(a: float, b: float) -> float:
        return a - b

    @registry.register(description="Multiply two numbers. Args: a (float), b (float).")
    def multiply(a: float, b: float) -> float:
        return a * b

    @registry.register(
        description="Divide a by b. Args: a (float), b (float). Returns error if b is zero.",
        sensitivity=ToolSensitivity.SAFE,
    )
    def divide(a: float, b: float) -> float | str:
        if b == 0:
            return "Error: Division by zero"
        return a / b
```

**设计要点：**
- 工具函数定义在 `register_calculator_tools()` 内部，利用闭包绑定到传入的 `registry`
- `divide` 实现了除零保护，返回错误字符串而非抛出异常，让 LLM 能理解并向用户解释
- 所有工具均为 `SAFE` 级别，不需要人工审批

---

## 5. FastAPI 服务器

**文件：** `packages/core/src/agent_core/api/server.py`

### 5.1 应用创建与生命周期

```python
def create_app(config: AgentConfig | None = None) -> FastAPI:
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
```

**生命周期模式：**
- 使用 FastAPI 的 `lifespan` 异步上下文管理器
- 启动时调用 `_create_agent()` 初始化模块级 `_agent` 实例
- 关闭时将 `_agent` 置为 `None`
- 好处：避免在每次请求时重新创建 Agent，确保 LLM 连接和工具注册只执行一次

### 5.2 Agent 工厂函数

```python
def _create_agent(config: AgentConfig | None = None) -> ReactAgent:
    if config is None:
        config = AgentConfig.from_env()

    llm = ChatOpenAI(
        model=config.model_name,
        temperature=config.temperature,
        api_key=config.openai_api_key,    # 可选
        base_url=config.openai_base_url,  # 可选
    )

    registry = ToolRegistry()
    register_calculator_tools(registry)

    return ReactAgent(llm=llm, tool_registry=registry, system_prompt=config.system_prompt)
```

**条件参数传递：** `api_key` 和 `base_url` 仅在配置中非空时传入 `llm_kwargs`，支持使用环境变量中的默认值或自定义代理 URL。

### 5.3 端点实现

#### 健康检查

```python
@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

#### 工具列表

```python
@app.get("/tools", response_model=list[ToolInfo])
async def list_tools() -> list[ToolInfo]:
    assert _agent is not None
    tools = _agent.tool_registry.list_tools()
    return [
        ToolInfo(name=t.name, description=t.description, sensitivity=t.sensitivity.value)
        for t in tools
    ]
```

将内部 `ToolDefinition` 转换为 `ToolInfo` Pydantic 模型返回，`sensitivity` 使用 `.value` 转为字符串。

#### 同步对话

```python
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    assert _agent is not None
    try:
        response = await _agent.chat(request.message)
    except Exception as e:
        logger.exception("Chat request failed")
        raise HTTPException(status_code=502, detail=str(e)) from e
    return ChatResponse(response=response)
```

**错误处理：** 使用 HTTP 502（Bad Gateway）状态码，表示作为代理的 API 服务器从上游 LLM 收到了无效响应。

#### SSE 流式对话

```python
@app.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    async def event_generator() -> AsyncGenerator[str, None]:
        import json
        try:
            async for event in _agent.stream(request.message):
                yield f"data: {json.dumps(event)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.exception("Stream request failed")
            error_event = {"type": "error", "content": str(e)}
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**SSE 协议实现：**
- 每个事件以 `data: ` 前缀 + JSON 编码 + `\n\n` 分隔
- 流正常结束时发送 `data: [DONE]\n\n` 作为结束标记
- 异常时发送 `{"type": "error", "content": "..."}` 事件，不中断 SSE 连接

### 5.4 CORS 配置

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

全开放 CORS 策略，适合开发阶段。生产环境应限制 `allow_origins` 为具体前端域名。

### 5.5 Pydantic 模型

| 模型 | 用途 | 字段 |
|------|------|------|
| `ChatRequest` | 请求体 | `message: str` |
| `ChatResponse` | 响应体 | `response: str` |
| `ToolInfo` | 工具信息 | `name: str`, `description: str`, `sensitivity: str` |

---

## 6. 配置管理

**文件：** `packages/core/src/agent_core/config.py`

### 6.1 AgentConfig 数据类

```python
@dataclass
class AgentConfig:
    openai_api_key: str = ""
    openai_base_url: str = ""
    model_name: str = "gpt-4o-mini"
    temperature: float = 0.0
    max_iterations: int = 10
    system_prompt: str = field(default=(
        "You are a helpful AI assistant. You can use tools to help "
        "answer questions. When you need to perform calculations, "
        "use the available calculator tools."
    ))
```

### 6.2 环境变量加载

```python
@classmethod
def from_env(cls, env_file: str | Path | None = None) -> "AgentConfig":
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()

    return cls(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_base_url=os.getenv("OPENAI_BASE_URL", ""),
        model_name=os.getenv("MODEL_NAME", "gpt-4o-mini"),
        temperature=float(os.getenv("TEMPERATURE", "0.0")),
        max_iterations=int(os.getenv("MAX_ITERATIONS", "10")),
        system_prompt=os.getenv("SYSTEM_PROMPT", cls.system_prompt),
    )
```

**加载策略：**
1. 优先使用指定的 `.env` 文件路径
2. 若未指定，调用 `load_dotenv()` 自动查找项目根目录的 `.env` 文件
3. 每个配置项使用 `os.getenv()` 读取，提供合理的默认值
4. `temperature` 和 `max_iterations` 进行类型转换（`float` / `int`）

---

## 7. 公共 API 导出

**文件：** `packages/core/src/agent_core/__init__.py`

```python
from agent_core.engine.agent import ReactAgent
from agent_core.tools.registry import ToolRegistry, tool

__all__ = ["ReactAgent", "ToolRegistry", "tool"]
```

对外只暴露三个核心接口：
- `ReactAgent`：Agent 引擎类
- `ToolRegistry`：工具注册表类
- `tool`：独立装饰器函数

其他内部模块（`state.py`、`config.py`、`server.py`、`calculator.py`）通过各自的导入路径使用，不作为公共 API。
