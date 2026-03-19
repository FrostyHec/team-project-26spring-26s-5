# 用户指南

本文档介绍如何安装、配置和使用 ReAct Agent。

## 快速开始

### 1. 安装

```bash
# 克隆项目
git clone <repo-url>
cd team-project-26spring-26s-5

# 安装所有依赖（Python + Node.js）
task init
```

> **前提条件**：需要安装 Python ≥ 3.12、Node.js ≥ 20、[uv](https://docs.astral.sh/uv/)、[pnpm](https://pnpm.io/)、[go-task](https://taskfile.dev/)。

### 2. 配置

复制环境变量模板并填入你的 API Key：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```dotenv
# 必填 — OpenAI API Key
OPENAI_API_KEY=sk-your-api-key-here

# 可选配置
OPENAI_BASE_URL=             # 自定义 API 端点（兼容 OpenAI 接口的服务）
MODEL_NAME=gpt-4o-mini       # 使用的模型
TEMPERATURE=0.0              # 模型温度（0.0 = 确定性输出）
MAX_ITERATIONS=10            # 最大推理循环次数
SYSTEM_PROMPT=You are a helpful AI assistant with calculator tools.
```

### 3. 运行

选择以下任一方式启动：

```bash
# 方式一：CLI 聊天
task dev:server               # 先启动后端（终端 1）
cd packages/cli && uv run agent-cli chat  # 启动 CLI（终端 2）

# 方式二：Chainlit 浏览器界面
task dev:poc                  # 打开 http://localhost:8001

# 方式三：Vue 前端
task dev:server               # 先启动后端（终端 1）
task dev:gui                  # 启动前端（终端 2），打开 http://localhost:5173
```

## 三种使用方式

### 方式一：CLI 命令行聊天

在终端中与 Agent 进行文字对话。

**启动步骤**：

```bash
# 1. 启动后端 API 服务器
task dev:server

# 2. 在另一个终端启动 CLI
cd packages/cli
uv run agent-cli chat
```

**使用方式**：

```
$ uv run agent-cli chat
Agent CLI - Type your message (Ctrl+C to exit)
> 你好，请帮我计算 123 + 456
Agent: 123 + 456 = 579
> 3.14 * 2.5 等于多少？
Agent: 3.14 × 2.5 = 7.85
> Ctrl+C
```

**CLI 命令**：

| 命令 | 说明 |
|------|------|
| `agent-cli chat` | 交互式聊天模式 |
| `agent-cli serve` | 启动 FastAPI 服务器（同 `task dev:server`） |
| `agent-cli serve --port 9000` | 指定端口启动服务器 |

### 方式二：Chainlit POC 浏览器界面

在浏览器中使用 Chainlit 提供的聊天界面。

**启动步骤**：

```bash
task dev:poc
```

**使用方式**：

1. 打开浏览器访问 `http://localhost:8001`
2. 在聊天框中输入消息
3. Agent 会实时显示推理过程和工具调用结果

Chainlit 界面特点：
- 自动展示推理步骤
- 可视化工具调用过程
- 支持流式输出

### 方式三：Vue 前端

生产级 Web 聊天界面，基于 Vue3 + TypeScript。

**启动步骤**：

```bash
# 需要先启动后端 API
task dev:server

# 启动 Vue 开发服务器
task dev:gui
```

**使用方式**：

1. 打开浏览器访问 `http://localhost:5173`
2. 在聊天界面输入消息
3. 查看 Agent 回复

Vue 前端特点：
- 现代化 UI 设计
- Pinia 状态管理
- 支持 SSE 流式输出
- 热模块替换（HMR）开发体验

## 内置工具

当前版本提供以下 POC 演示工具（计算器）：

| 工具 | 功能 | 参数 | 示例 |
|------|------|------|------|
| `add` | 加法 | `a: float, b: float` | `add(3, 5)` → `8.0` |
| `subtract` | 减法 | `a: float, b: float` | `subtract(10, 3)` → `7.0` |
| `multiply` | 乘法 | `a: float, b: float` | `multiply(4, 6)` → `24.0` |
| `divide` | 除法 | `a: float, b: float` | `divide(15, 3)` → `5.0` |

**除法零除保护**：`divide(10, 0)` 返回 `"Error: Division by zero"`，不会抛出异常。

Agent 会根据用户的自然语言请求，自动选择合适的工具进行计算：

```
用户：帮我算一下 100 除以 7
Agent：（调用 divide 工具）→ 100 ÷ 7 ≈ 14.2857
```

## API 端点参考

后端 FastAPI 服务器提供以下 REST API 端点：

### GET /health

健康检查，用于确认服务器正常运行。

```bash
curl http://localhost:8000/health
```

**响应**：

```json
{"status": "ok"}
```

### GET /tools

获取所有已注册的工具列表。

```bash
curl http://localhost:8000/tools
```

**响应**：

```json
[
  {
    "name": "add",
    "description": "Add two numbers together. Args: a (float), b (float).",
    "sensitivity": "safe"
  },
  {
    "name": "subtract",
    "description": "Subtract b from a. Args: a (float), b (float).",
    "sensitivity": "safe"
  },
  {
    "name": "multiply",
    "description": "Multiply two numbers. Args: a (float), b (float).",
    "sensitivity": "safe"
  },
  {
    "name": "divide",
    "description": "Divide a by b. Args: a (float), b (float). Returns error if b is zero.",
    "sensitivity": "safe"
  }
]
```

### POST /chat

发送消息并获取完整响应（同步）。

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is 42 + 58?"}'
```

**请求体**：

```json
{
  "message": "What is 42 + 58?"
}
```

**响应**：

```json
{
  "response": "42 + 58 = 100"
}
```

**错误响应**：

| 状态码 | 说明 |
|--------|------|
| 422 | 请求格式错误（缺少 message 字段等） |
| 502 | LLM API 调用失败 |

### POST /chat/stream

发送消息并以 SSE（Server-Sent Events）流式返回执行步骤。

```bash
curl -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Calculate 10 * 5"}' \
  --no-buffer
```

**事件格式**：

```
data: {"type": "thinking", "content": "I need to multiply 10 by 5..."}

data: {"type": "tool_call", "name": "multiply", "args": {"a": 10, "b": 5}}

data: {"type": "tool_result", "content": "50.0"}

data: {"type": "response", "content": "10 × 5 = 50"}

data: [DONE]
```

**事件类型**：

| type | 说明 |
|------|------|
| `thinking` | Agent 的推理过程 |
| `tool_call` | 工具调用请求 |
| `tool_result` | 工具执行结果 |
| `response` | 最终回复 |
| `error` | 执行过程中的错误 |
| `[DONE]` | 流结束标记 |

## 使用示例

### 基本对话

```
用户：你好
Agent：你好！我是一个 AI 助手，可以帮你进行数学计算。请告诉我你需要计算什么。
```

### 数学计算

```
用户：请帮我计算 (100 + 50) * 2
Agent：
  1. 先计算 100 + 50 = 150（调用 add 工具）
  2. 再计算 150 * 2 = 300（调用 multiply 工具）
  结果为 300。
```

### 多步推理

```
用户：我有 500 元，花了 123.5 元买书，又花了 89.9 元买文具，还剩多少？
Agent：
  1. 500 - 123.5 = 376.5（调用 subtract 工具）
  2. 376.5 - 89.9 = 286.6（调用 subtract 工具）
  你还剩 286.6 元。
```

### 使用 curl 调用 API

```bash
# 健康检查
curl http://localhost:8000/health

# 同步聊天
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is 15 divided by 4?"}'

# 流式聊天
curl -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Add 100 and 200, then multiply by 3"}' \
  --no-buffer
```
