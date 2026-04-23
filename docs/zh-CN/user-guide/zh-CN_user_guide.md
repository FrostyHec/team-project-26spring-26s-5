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

# Policy Search 使用的 Embedding 配置
EMBEDDING_API_KEY=your-dashscope-api-key-here
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v4
```

### 3. 运行

选择以下任一方式启动：

```bash
# 方式一：CLI 聊天
task dev:server               # 先启动后端（终端 1）
cd packages/cli && uv run agent-cli chat  # 启动 CLI（终端 2）

# 方式二：Vue 前端
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

### 方式二：Vue 前端

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

当前版本包含两类能力：

- 通用演示工具：计算器
- 专用 skill：Campus Policy Search

### Calculator 工具

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

### Campus Policy Search

Campus Policy Search 用于回答校园政策、培养方案、课程要求、毕业要求等问题。当前实现基于本地 RAG：

```text
PDF 文档 → 切片 → Embedding → FAISS 索引
用户问题 → search_campus_policy → Top-K 检索 → LLM 基于结果回答
```

使用前需要先构建索引：

```bash
cd packages/core
uv run python -m agent_core.policy_search.build_index
```

默认约定：
- 原始 PDF 放在仓库根目录 `pdfs/`
- 索引输出到 `packages/core/output/policy_index/`
- 第一版只支持中文 PDF，且只支持本地离线构建索引

当前建议通过 API 使用该能力，而不是通过 `agent-cli chat`。
原因是当前 CLI 交互入口尚未接入 `policy_search` skill 选择。

### 课程管理与资料库

课程管理功能支持添加课程、上传课程资料（PDF/DOCX/PPTX/XLSX/TXT/MD，≤10 MB）、管理和下载文件。

**后端 API：**

| 端点 | 方法 | 说明 |
|------|------|------|
| `/courses` | GET | 列出所有课程（可选 `?semester=` 筛选） |
| `/courses` | POST | 创建新课程（body: name, code?, credits?, instructor?, description?, tags?, semester?） |
| `/courses/{course_id}` | GET | 获取单个课程 |
| `/courses/{course_id}` | PATCH | 更新课程字段 |
| `/courses/{course_id}` | DELETE | 删除课程（同时删除所有关联资料文件和记录） |
| `/course-materials` | GET | 列出资料（可选 `?course_id=` 筛选） |
| `/course-materials` | POST | 上传文件到课程（`multipart/form-data`：file, course_id, description?, tags?） |
| `/course-materials/{id}` | GET | 获取资料记录 |
| `/course-materials/{id}` | PATCH | 更新资料描述/标签 |
| `/course-materials/{id}` | DELETE | 删除资料记录及物理文件 |
| `/course-materials/{id}/download` | GET | 下载资料物理文件 |
| `/pdfs/{filename}` | GET | 安全地提供 PDF 文件（防路径穿越） |

**前端使用：**

1. 在右侧工作区切换到"课程"面板
2. 点击"添加课程"输入课程名称等信息
3. 点击课程卡片右侧箭头进入该课程的文件管理页面
4. 在蓝色区域填写资料描述和标签，点击"上传"选择文件
5. 文件列表支持编辑描述/标签、下载、删除操作

**AI 课程助手：**

`skill=course_assistant` 会话模式下，Agent 可以：
- `analyze_document`：分析课程资料，提取摘要、关键点、难点
- `generate_quiz`：根据资料内容生成测验题（支持选择题/判断题/填空题/简答题，自动推断难度）
- `read_course_material`：读取指定资料内容供 AI 分析

使用示例：

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "帮我分析这份课程资料的主要知识点",
    "skill": "course_assistant"
  }'
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
  },
  {
    "name": "search_campus_policy",
    "description": "Search campus policy documents for information about university regulations, curriculum requirements, academic procedures, course plans, graduation requirements, and other campus policies.",
    "sensitivity": "safe"
  }
]
```

### GET /skills

获取所有可用 skill 列表。

```bash
curl http://localhost:8000/skills
```

Policy Search 对应的 skill 标识为 `policy_search`。

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

`skill` 字段可选；当需要启用专用 persona 时传入。例如 Policy Search：

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "航空航天工程专业需要多少学分？",
    "skill": "policy_search"
  }'
```

此时 Agent 会在 `policy_search` skill 的系统提示词约束下优先调用 `search_campus_policy`。

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

## 邮件功能使用与排错

### 收件箱同步

在右侧工作区切换到“收件箱”后，点击“同步邮件”会调用 `POST /email/sync` 拉取最近邮件。

如果没有配置邮箱账号或密码，界面会弹窗提示先去设置页完成配置。

### 写邮件 / 回复

点击“写邮件”或“回复”会进入邮件编辑界面。若此前遇到点击无反应的问题，请更新到最新版本（已修复相关 i18n 文案编译错误）。

### 常见错误

- **提示需先配置邮箱账号密码**：进入“设置 → 邮件服务”填写账号与密码后重试。
- **同步无结果**：先确认邮箱确有新邮件，再检查邮箱服务是否可连通（可在设置页使用“测试连接”）。

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
