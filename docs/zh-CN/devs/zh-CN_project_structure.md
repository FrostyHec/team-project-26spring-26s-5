# 项目结构

## 目录结构

```
team-project-26spring-26s-5/
├── .env.example               # 环境变量模板
├── .gitignore                 # Git 忽略规则
├── .pre-commit-config.yaml    # Pre-commit hooks
├── CHANGELOG.md               # 变更日志
├── LICENSE                    # 许可证
├── README.md                  # 项目说明
├── Taskfile.yml               # 任务编排
├── docs/
│   └── zh-CN/                 # 中文文档
│       ├── index.md
│       ├── design/            # 设计文档
│       ├── devs/              # 开发指南
│       └── user-guide/        # 用户指南
├── packages/
│   ├── core/                  # 🔧 核心引擎
│   │   ├── pyproject.toml     # 包配置和依赖
│   │   ├── src/agent_core/    # 源代码
│   │   │   ├── __init__.py    # 公共 API 导出
│   │   │   ├── config.py      # 环境配置加载
│   │   │   ├── engine/        # ReAct 引擎
│   │   │   │   ├── agent.py   # ReactAgent 核心类
│   │   │   │   └── state.py   # AgentState 类型定义
│   │   │   ├── tools/         # 工具系统
│   │   │   │   ├── registry.py    # ToolRegistry + @tool 装饰器
│   │   │   │   └── calculator.py  # POC 计算工具
│   │   │   └── api/           # Web API
│   │   │       └── server.py  # FastAPI 应用
│   │   └── tests/             # 单元测试
│   ├── cli/                   # 💻 CLI 前端
│   │   ├── pyproject.toml
│   │   ├── src/agent_cli/
│   │   │   └── main.py        # CLI 入口
│   │   └── tests/
│   ├── poc_frontend/          # 🎨 Chainlit POC
│   │   ├── pyproject.toml
│   │   ├── src/poc_frontend/
│   │   │   └── app.py         # Chainlit 应用
│   │   └── tests/
│   └── gui/                   # 🖥️ Vue3 前端
│       ├── package.json
│       ├── vite.config.ts     # Vite 配置（含 API 代理）
│       ├── vitest.config.ts   # Vitest 配置
│       ├── src/
│       │   ├── api/           # API 客户端
│       │   ├── stores/        # Pinia 状态管理
│       │   ├── views/         # 页面组件
│       │   └── router/        # 路由配置
│       └── e2e/               # Playwright e2e
└── scripts/
    ├── check.sh               # 开发者检查脚本
    ├── ci-local.sh            # CI 本地模拟
    └── check_language.py      # 源代码语言检查
```

## Monorepo 架构

本项目采用 monorepo 结构，各包相互独立但可以引用：

```
packages/core  ← 核心引擎，不依赖其他包
packages/cli   ← 依赖 core（通过 uv.sources path reference）
packages/poc_frontend ← 依赖 core
packages/gui   ← 独立的 Node.js 项目，通过 HTTP API 与 core 通信
```

## 依赖管理

### Python 包（uv）

每个 Python 包有独立的 `pyproject.toml` 和 `.venv`：

```bash
# 安装单个包
cd packages/core && uv sync --all-extras

# 安装所有
task init:python
```

包间引用通过 `[tool.uv.sources]` 实现：

```toml
[tool.uv.sources]
agent-core = { path = "../core", editable = true }
```

### Node.js 包（pnpm）

Vue 前端使用 pnpm 管理依赖：

```bash
cd packages/gui && pnpm install
# 或
task init:gui
```

## 配置文件说明

| 文件 | 说明 |
|------|------|
| `Taskfile.yml` | 项目级任务编排（init, dev, test, lint, format, ci, clean） |
| `pyproject.toml` | 各 Python 包的依赖和构建配置 |
| `package.json` | Vue 前端依赖和脚本 |
| `vite.config.ts` | Vite 构建配置 + 开发服务器代理 |
| `.pre-commit-config.yaml` | Git hooks（ruff, commitizen） |
| `.env.example` | 环境变量模板 |
