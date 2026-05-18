# 项目结构

## 目录结构

```
team-project-26spring-26s-5/
├── .env.example               # 环境变量模板
├── .gitignore                 # Git 忽略规则
├── .pre-commit-config.yaml    # Pre-commit hooks
├── .github/
│   └── workflows/
│       └── ci.yml             # GitHub Actions CI 工作流
├── CHANGELOG.md               # 变更日志
├── LICENSE                    # MIT 许可证
├── README.md                  # 项目说明
├── Taskfile.yml               # 任务编排（go-task v3）
├── docs/
│   └── zh-CN/                 # 中文文档
│       ├── index.md
│       ├── design/            # 设计文档
│       │   └── index.md
│       ├── devs/              # 开发指南
│       │   ├── index.md
│       │   ├── zh-CN_agent.md
│       │   ├── zh-CN_code_conventions_python.md
│       │   ├── zh-CN_code_conventions_vue.md
│       │   ├── zh-CN_commit_conventions.md
│       │   ├── zh-CN_developers_guideline.md
│       │   ├── zh-CN_distribution.md
│       │   └── zh-CN_project_structure.md
│       └── user-guide/        # 用户指南
│           ├── index.md
│           └── zh-CN_user_guide.md
├── packages/
│   ├── core/                  # 🔧 核心引擎（Python）
│   │   ├── pyproject.toml     # 包配置和依赖
│   │   ├── README.md
│   │   ├── .venv/             # 独立虚拟环境（uv 管理）
│   │   ├── output/
│   │   │   └── policy_index/  # Policy Search 本地索引产物（不应提交）
│   │   ├── src/agent_core/    # 源代码
│   │   │   ├── __init__.py    # 公共 API 导出
│   │   │   ├── config.py      # 环境配置加载（AgentConfig）
│   │   │   ├── engine/        # ReAct 引擎
│   │   │   │   ├── __init__.py
│   │   │   │   ├── agent.py   # ReactAgent 核心类（LangGraph）
│   │   │   │   └── state.py   # AgentState 类型定义
│   │   │   ├── policy_search/ # Campus Policy Search RAG
│   │   │   │   ├── build_index.py  # 离线索引构建入口
│   │   │   │   ├── embeddings.py   # Embedding API 封装
│   │   │   │   ├── index.py        # FAISS 索引构建/加载
│   │   │   │   ├── ingest.py       # PDF 解析与切片
│   │   │   │   ├── models.py       # Chunk / Metadata / Result 模型
│   │   │   │   └── retriever.py    # Top-K 检索与格式化
│   │   │   ├── skills/        # Agent skills / personas
│   │   │   │   └── policy_search.py # Policy Search 专用 prompt
│   │   │   ├── tools/         # 工具系统
│   │   │   │   ├── __init__.py
│   │   │   │   ├── registry.py    # ToolRegistry + @register 装饰器
│   │   │   │   ├── calculator.py  # POC 计算工具（加减乘除）
│   │   │   │   └── policy_search.py # RAG 检索工具入口
│   │   │   └── api/           # Web API
│   │   │       ├── __init__.py
│   │   │       └── server.py  # FastAPI 应用（REST 端点）
│   │   └── tests/             # 单元测试
│   │       ├── test_api.py        # API 端点测试
│   │       ├── test_calculator.py # 计算工具测试
│   │       ├── test_config.py     # 配置测试
│   │       ├── test_policy_search.py # Policy Search 测试
│   │       ├── test_registry.py   # 工具注册测试
│   │       └── test_state.py      # 状态管理测试
│   ├── cli/                   # 💻 CLI 前端（Python）
│   │   ├── pyproject.toml
│   │   ├── README.md
│   │   ├── .venv/             # 独立虚拟环境
│   │   ├── src/agent_cli/
│   │   │   └── main.py        # CLI 入口（argparse: chat/serve）
│   │   └── tests/
│   │       └── test_cli.py
│   └── gui/                   # 🖥️ Vue3+TS 前端
│       ├── package.json       # Node.js 依赖和脚本
│       ├── pnpm-lock.yaml     # pnpm 锁文件
│       ├── vite.config.ts     # Vite 配置（含 API 代理）
│       ├── vitest.config.ts   # Vitest 测试配置
│       ├── tsconfig.json      # TypeScript 根配置
│       ├── tsconfig.app.json  # 应用 TS 配置
│       ├── tsconfig.node.json # Node 环境 TS 配置
│       ├── eslint.config.ts   # ESLint 配置
│       ├── playwright.config.ts # Playwright E2E 配置
│       ├── index.html         # SPA 入口 HTML
│       ├── src/
│       │   ├── App.vue            # 根组件
│       │   ├── main.ts            # 应用入口
│       │   ├── api/
│       │   │   ├── agent.ts       # API 客户端（HTTP 请求）
│       │   │   └── __tests__/
│       │   │       └── agent.spec.ts
│       │   ├── stores/
│       │   │   ├── chat.ts        # Pinia 聊天状态管理
│       │   │   └── __tests__/
│       │   │       └── chat.spec.ts
│       │   ├── views/
│       │   │   └── ChatView.vue   # 聊天页面
│       │   ├── components/        # 可复用组件
│       │   ├── router/
│       │   │   └── index.ts       # Vue Router 配置
│       │   └── assets/
│       │       └── main.css       # 全局样式
│       └── e2e/               # Playwright E2E 测试
│           └── vue.spec.ts
└── scripts/
    ├── check.sh               # 统一检查脚本（开发 + CI 模式）
    └── check_language.py      # 源代码语言检查（禁止中文）
```

## Monorepo 架构

本项目采用 monorepo 结构，所有代码在一个仓库中管理，但各包职责清晰、相互独立。

### 包依赖关系

```
packages/core          ← 核心引擎，不依赖其他包
    ↑
    └── packages/cli   ← 依赖 core（通过 uv.sources path reference）

packages/gui           ← 独立的 Node.js 项目，通过 HTTP API 与 core 通信
```

### 各包职责

| 包 | 语言 | 职责 | 对外接口 |
|------|------|------|----------|
| `core` | Python | ReAct 引擎、工具系统、Skills、FastAPI 服务、Policy Search RAG | REST API（HTTP） |
| `cli` | Python | 命令行交互界面 | 终端命令 |
| `gui` | TypeScript/Vue | 生产级 Web 聊天界面 | Web UI（Vue SPA） |

## 依赖管理

### Python 包管理（uv）

每个 Python 包有独立的 `pyproject.toml` 和 `.venv`（虚拟环境）：

```bash
packages/core/.venv/         # core 的虚拟环境
packages/cli/.venv/          # cli 的虚拟环境
```

安装命令：

```bash
# 安装单个包的所有依赖（含开发依赖）
cd packages/core && uv sync --all-extras

# 安装所有 Python 包
task init:python
```

### 跨包依赖（tool.uv.sources）

`cli` 依赖 `core`，通过 `[tool.uv.sources]` 配置本地路径引用：

```toml
# packages/cli/pyproject.toml
[project]
dependencies = [
    "agent-core",
]

[tool.uv.sources]
agent-core = { path = "../core", editable = true }
```

这种方式允许：
- 开发时直接引用本地源码（editable 模式），修改 core 立即生效
- 发布时替换为版本约束（`agent-core>=0.1.0`）

### Node.js 包管理（pnpm）

Vue 前端使用 pnpm 管理依赖：

```bash
# 安装依赖
cd packages/gui && pnpm install

# 或通过 task
task init:gui
```

pnpm 使用 `pnpm-lock.yaml` 锁定依赖版本。

## 配置文件说明

### 项目级配置

| 文件 | 说明 |
|------|------|
| `Taskfile.yml` | 项目级任务编排（go-task v3），定义 init/dev/test/lint/format/clean 等任务 |
| `.env.example` | 环境变量模板（LLM、Embedding、日志、数据库等） |
| `.pre-commit-config.yaml` | Git hooks 配置（Ruff 格式化、Commitizen 检查） |
| `.github/workflows/ci.yml` | GitHub Actions CI 工作流（lint → language-check → test） |
| `.gitignore` | Git 忽略规则 |

### Python 包配置

| 文件 | 位置 | 说明 |
|------|------|------|
| `pyproject.toml` | 各 Python 包根目录 | 包元数据、依赖、构建配置、Ruff/pytest/mypy 配置 |

`pyproject.toml` 中包含的工具配置：

```toml
[tool.ruff]          # Ruff 格式化 + Lint 配置
[tool.mypy]          # MyPy 类型检查配置（仅 core）
[tool.pytest.ini_options]  # pytest 配置
[tool.hatch.build]   # Hatchling 构建配置
[tool.uv.sources]    # 跨包依赖路径（仅 cli）
```

### Vue 前端配置

| 文件 | 说明 |
|------|------|
| `package.json` | 依赖和 npm scripts |
| `vite.config.ts` | Vite 构建配置 + 开发服务器代理（`/api` → `localhost:8000`） |
| `vitest.config.ts` | Vitest 测试配置 |
| `tsconfig.json` | TypeScript 根配置（引用 app/node 子配置） |
| `tsconfig.app.json` | 应用源码的 TS 配置 |
| `tsconfig.node.json` | Node 环境（vite.config.ts 等）的 TS 配置 |
| `eslint.config.ts` | ESLint + oxlint 配置 |
| `playwright.config.ts` | Playwright E2E 测试配置 |

## 包间通信

### Python 包间通信

`cli` 通过 Python 导入直接调用 `core` 的 API：

```python
# packages/cli/src/agent_cli/main.py
from agent_core.api.server import create_app
from agent_core.config import AgentConfig
```

### GUI → Core 通信

Vue 前端通过 HTTP API 与 Core 通信，开发时 Vite 代理转发请求：

```
Vue (localhost:5173) --/api/--> Vite Proxy --> FastAPI (localhost:8000)
```

Vite 代理配置：

```typescript
// vite.config.ts
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, ''),
    },
  },
}
```

前端发起 `/api/chat` 请求 → Vite 代理重写为 `/chat` → 转发到 FastAPI。

## Policy Search 相关约定

- PDF 原始文档默认放在仓库根目录 `pdfs/`
- 离线索引构建命令：

```bash
cd packages/cli
uv run agent-cli build-policy-index
```

- 索引产物默认输出到 `packages/core/output/policy_index/`
- 索引构建配置集中在 `agent_core.policy_search.config.PolicySearchConfig`
- 可通过 `.env` 配置 `POLICY_PDF_DIR`、`POLICY_INDEX_DIR`、`POLICY_CHUNK_SIZE`、`POLICY_CHUNK_OVERLAP`
- `build-policy-index` 不接受命令行覆盖参数，避免不同开发者临时构建出不一致索引
- 后端启动时会检查索引文件是否存在；缺失时只记录 warning，不自动构建
- 这些索引产物属于本地生成文件，不应提交到 Git
- 当前实现不包含 GUI 改造，主要落在 `core` 与 API 层
