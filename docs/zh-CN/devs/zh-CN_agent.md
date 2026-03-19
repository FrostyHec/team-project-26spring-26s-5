# 综合技术参考（面向开发者和 AI 代理）

本文档为 ReAct Agent 项目的综合技术参考，面向人类开发者和 AI 代理。

## 项目工程结构

```
team-project-26spring-26s-5/
├── Taskfile.yml              # 任务编排（go-task）
├── .env.example              # 环境变量模板
├── scripts/                  # 脚本
│   ├── check.sh              # 开发者检查脚本
│   ├── ci-local.sh           # CI 本地模拟
│   └── check_language.py     # 语言检查工具
├── packages/
│   ├── core/                 # 核心引擎（Python）
│   │   ├── pyproject.toml
│   │   ├── src/agent_core/
│   │   │   ├── engine/       # ReAct 循环引擎
│   │   │   │   ├── agent.py  # ReactAgent（LangGraph）
│   │   │   │   └── state.py  # AgentState 类型
│   │   │   ├── tools/        # 工具系统
│   │   │   │   ├── registry.py   # ToolRegistry + @tool
│   │   │   │   └── calculator.py # POC 计算工具
│   │   │   ├── api/
│   │   │   │   └── server.py # FastAPI 服务端
│   │   │   └── config.py     # 环境配置
│   │   └── tests/            # pytest 测试
│   ├── cli/                  # CLI 前端（Python）
│   │   ├── pyproject.toml
│   │   ├── src/agent_cli/
│   │   │   └── main.py       # argparse CLI
│   │   └── tests/
│   ├── poc_frontend/         # Chainlit POC（Python）
│   │   ├── pyproject.toml
│   │   ├── src/poc_frontend/
│   │   │   └── app.py        # Chainlit 应用
│   │   └── tests/
│   └── gui/                  # Vue3+TS 前端
│       ├── package.json
│       ├── vite.config.ts
│       ├── src/
│       │   ├── api/agent.ts      # API 客户端
│       │   ├── stores/chat.ts    # Pinia 状态管理
│       │   ├── views/ChatView.vue # 聊天界面
│       │   └── router/index.ts   # 路由
│       └── e2e/              # Playwright e2e 测试
└── docs/zh-CN/               # 中文文档
```

## 技术栈

| 组件 | 技术 | 版本 |
|------|------|------|
| Python 运行时 | Python | ≥3.12 |
| 包管理（Python） | uv | 最新 |
| 包管理（Node） | pnpm | 最新 |
| 任务编排 | Taskfile（go-task） | v3 |
| LLM 框架 | LangChain + LangGraph | ≥0.3.0 / ≥0.4.0 |
| Web 框架 | FastAPI + Uvicorn | ≥0.115.0 |
| POC 前端 | Chainlit | ≥2.0.0 |
| GUI 前端 | Vue3 + TypeScript | 最新 |
| 状态管理 | Pinia | 最新 |
| 构建工具 | Vite | 最新 |
| Python Lint/Format | Ruff | ≥0.4.0 |
| Python 测试 | pytest + pytest-asyncio | 最新 |
| Vue 测试 | Vitest | 最新 |
| E2E 测试 | Playwright | 最新 |

## 依赖信息

### Core 包核心依赖

- `langchain>=0.3.0` — LLM 抽象层
- `langgraph>=0.4.0` — 有状态图执行引擎
- `langchain-openai>=0.3.0` — OpenAI 模型绑定
- `pydantic>=2.0.0` — 数据验证
- `fastapi>=0.115.0` — REST API 框架
- `uvicorn>=0.34.0` — ASGI 服务器
- `python-dotenv>=1.0.0` — 环境变量加载

### 开发依赖

- `pytest`, `pytest-asyncio`, `pytest-cov` — Python 测试
- `ruff` — 代码格式化与 Lint
- `httpx` — 异步 HTTP 测试客户端

## 开发环境搭建

```bash
# 1. 安装工具链
pip install uv               # Python 包管理
npm install -g pnpm           # Node.js 包管理
# 安装 go-task: https://taskfile.dev/installation/

# 2. 克隆并初始化
git clone <repo-url>
cd team-project-26spring-26s-5
task init                     # 安装所有依赖

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 OPENAI_API_KEY 等

# 4. 验证安装
task test                     # 运行所有测试
```

## 代码格式与开发规范

### 语言策略

- **源代码**：所有注释、变量名、文档字符串必须使用英文
- **文档**：中文为主
- **Commit Messages**：英文

### 代码风格

- **Python**：Ruff 格式化（行宽 88，双引号，4 空格缩进）
- **TypeScript/Vue**：ESLint + Prettier

### 类型注解

所有公共 API 必须有完整的类型注解。

## 本地测试指南

```bash
# 快速检查（开发时使用）
bash scripts/check.sh

# CI 模拟（提交前使用）
bash scripts/ci-local.sh

# 仅运行特定包测试
task test:core
task test:cli
task test:poc
task test:gui

# 运行所有测试
task test
```

## 核心架构

### ReAct 循环

```
reasoner (LLM) → should_continue? → tool_executor → reasoner → ...
```

- `ReactAgent._build_graph()` 构建 LangGraph StateGraph
- `ReactAgent._reason()` 调用 LLM 生成推理
- `ReactAgent._execute_tools()` 执行工具调用
- `ReactAgent.stream()` 返回 SSE 事件的异步生成器

### 工具系统

```python
from agent_core import tool

@tool(name="my_tool", description="Do something")
def my_tool(x: int) -> str:
    return str(x * 2)
```

`ToolRegistry` 管理工具注册、转换为 LangChain Tool、异步执行。

### API 层

FastAPI 提供 REST 接口：
- `GET /health` — 健康检查
- `GET /tools` — 工具列表
- `POST /chat` — 同步聊天
- `POST /chat/stream` — SSE 流式聊天

### 前端

Vue3 前端通过 Vite 代理 `/api` → `localhost:8000`，使用 Pinia 管理聊天状态。
