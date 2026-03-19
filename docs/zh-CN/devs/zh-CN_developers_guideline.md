# 开发者完整指南

本文档为 ReAct Agent 项目的完整开发指南，涵盖从环境搭建到代码合并的全流程。

## 前提条件

### 必需工具

| 工具 | 版本要求 | 安装方式 |
|------|----------|----------|
| Python | ≥ 3.12 | [python.org](https://www.python.org/) 或系统包管理器 |
| Node.js | ≥ 20 | [nodejs.org](https://nodejs.org/) 或 nvm |
| uv | 最新 | `pip install uv` 或 `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| pnpm | 最新 | `npm install -g pnpm` |
| go-task | v3 | [taskfile.dev/installation](https://taskfile.dev/installation/) |
| Git | 最新 | 系统包管理器 |

### 可选工具

| 工具 | 用途 |
|------|------|
| Commitizen (`cz`) | 交互式提交辅助 |
| pre-commit | Git Hooks 管理 |

### 环境验证

```bash
python3 --version   # 应 ≥ 3.12
node --version      # 应 ≥ 20
uv --version        # 确认已安装
pnpm --version      # 确认已安装
task --version      # 确认已安装
```

## 环境搭建

### 1. 克隆仓库

```bash
git clone <repo-url>
cd team-project-26spring-26s-5
```

### 2. 安装所有依赖

```bash
task init
```

该命令会执行：
- `task init:python` — 为 `core`、`cli`、`poc_frontend` 三个 Python 包各自运行 `uv sync --all-extras`，创建独立的 `.venv` 并安装所有依赖（含开发依赖）
- `task init:gui` — 在 `packages/gui` 下运行 `pnpm install`

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入以下配置：

```dotenv
# 必填
OPENAI_API_KEY=your-api-key-here

# 可选
OPENAI_BASE_URL=             # 自定义 API 端点（留空使用默认）
MODEL_NAME=gpt-4o-mini       # 模型名称
TEMPERATURE=0.0              # 模型温度
MAX_ITERATIONS=10            # 最大推理循环次数
SYSTEM_PROMPT=You are a helpful AI assistant with calculator tools.
```

### 4. 验证安装

```bash
task test    # 运行所有测试，确认环境正常
```

## 开发工作流

### 完整流程

```
创建分支 → 开发 → 本地检查 → 提交 → 推送 → 创建 PR → CI 通过 → 代码审查 → 合并
```

### 步骤详解

#### 1. 创建分支

从 `main` 分支创建功能分支：

```bash
git checkout main
git pull origin main
git checkout -b feature/add-new-tool
```

分支命名规范参见 [提交规范](zh-CN_commit_conventions.md)。

#### 2. 开发

根据需要修改代码。启动开发服务器：

```bash
# 启动后端 API（端口 8000）
task dev:server

# 启动 Chainlit POC（端口 8001）
task dev:poc

# 启动 Vue 前端开发服务器（端口 5173）
task dev:gui
```

#### 3. 本地检查

**提交前必须运行检查脚本**：

```bash
# 开发阶段检查（会自动修复格式问题）
bash scripts/check.sh

# 或模拟 CI 检查（不自动修复，更严格）
bash scripts/ci-local.sh
```

#### 4. 提交

```bash
git add .
git commit -m "feat(core): add new calculator tool"
```

Commit message 格式参见 [提交规范](zh-CN_commit_conventions.md)。

#### 5. 推送并创建 PR

```bash
git push origin feature/add-new-tool
```

在 GitHub 上创建 Pull Request，标题遵循 commit message 格式。

#### 6. CI 检查 & 代码审查

CI 自动运行，审查人审核代码。如有问题，修改后重新推送。

#### 7. 合并

CI 通过且审查通过后，使用 Squash and Merge 合并到 `main`。

## 本地检查脚本详解

### check.sh（开发时使用）

`bash scripts/check.sh` 执行 **5 个步骤**：

| 步骤 | 名称 | 说明 |
|------|------|------|
| 1/5 | Code Formatting | 对所有 Python 包运行 `ruff format`（**自动修复**格式问题） |
| 2/5 | Lint Check | 对所有 Python 包运行 `ruff check`（检查代码质量） |
| 3/5 | Language Check | 运行 `check_language.py`（确保源代码中无中文字符） |
| 4/5 | Python Tests | 对 `core`、`cli`、`poc_frontend` 运行 `pytest` |
| 5/5 | Vue Tests | 在 `packages/gui` 中运行 `pnpm vitest run` |

**推荐在每次提交前运行**。格式化步骤会自动修改文件，修复后需要重新 `git add`。

### ci-local.sh（提交前使用）

`bash scripts/ci-local.sh` 执行 **4 个步骤**：

| 步骤 | 名称 | 说明 |
|------|------|------|
| 1/4 | Lint & Format Check | `ruff format --check` + `ruff check`（**不自动修复**，仅报告） |
| 2/4 | Language Check | 运行 `check_language.py` |
| 3/4 | Python Tests | 对所有 Python 包运行 `pytest` |
| 4/4 | Vue Tests | 在 `packages/gui` 中运行 `pnpm vitest run` |

**模拟 CI 环境**，与 GitHub Actions 行为一致。如果此脚本全部通过，CI 也应该通过。

### 关键区别

| | `check.sh` | `ci-local.sh` |
|---|---|---|
| 格式化 | 自动修复 | 仅检查 |
| 适用场景 | 开发过程中 | 创建 PR 前 |
| 失败处理 | 修改文件后继续 | 直接报错退出 |

## CI 工作流

### 触发条件

CI 在以下事件时自动运行：
- 创建或更新 Pull Request
- Push 到 `main` 分支

### CI Jobs

GitHub Actions 工作流（`.github/workflows/ci.yml`）包含 **4 个 Job**：

| Job | 名称 | 依赖 | 说明 |
|-----|------|------|------|
| 1 | `lint` | — | Lint & Format Check：对所有 Python 包检查 `ruff format --check` 和 `ruff check` |
| 2 | `language-check` | — | Language Check：运行 `check_language.py` 确保无中文 |
| 3 | `test-python` | lint, language-check | Python Tests：对 core（含覆盖率）、cli、poc_frontend 运行 pytest |
| 4 | `test-vue` | lint, language-check | Vue Tests：运行 vitest + type-check + build |

```
lint ──────────┐
               ├──→ test-python
language-check ┤
               └──→ test-vue
```

- `lint` 和 `language-check` 并行执行
- `test-python` 和 `test-vue` 在前两个 Job 通过后并行执行
- 任何 Job 失败，PR 无法合并

### CI 环境

| 配置 | 值 |
|------|------|
| 运行器 | `ubuntu-latest` |
| Python | 3.12 |
| Node.js | 20 |
| Python 包管理 | uv（via `astral-sh/setup-uv@v5`） |
| Node 包管理 | pnpm（via `pnpm/action-setup@v4`） |
| 并发控制 | 同分支新提交取消旧运行 |

## PR 检查清单

创建 PR 前，请确认以下所有项目：

- [ ] **格式化通过**：`task format` 后无 diff，或 `ruff format --check` 通过
- [ ] **Lint 通过**：`task lint` 无错误
- [ ] **语言检查通过**：`python3 scripts/check_language.py --root .` 无中文
- [ ] **Python 测试通过**：`task test:core && task test:cli && task test:poc`
- [ ] **Vue 测试通过**：`task test:gui`
- [ ] **类型检查通过**：`cd packages/gui && pnpm run type-check`
- [ ] **Commit Message 规范**：遵循约定式提交格式
- [ ] **PR 标题规范**：格式同 commit message
- [ ] **新功能有测试**：单元测试 + 必要时的集成/E2E 测试
- [ ] **ci-local.sh 通过**：`bash scripts/ci-local.sh` 全绿

快速一键检查：

```bash
bash scripts/ci-local.sh
```

## 常用命令速查

### 初始化与依赖

| 命令 | 说明 |
|------|------|
| `task init` | 安装所有依赖 |
| `task init:python` | 仅安装 Python 依赖 |
| `task init:gui` | 仅安装 Vue 依赖 |

### 开发服务器

| 命令 | 说明 | 端口 |
|------|------|------|
| `task dev:server` | 启动 FastAPI 后端 | 8000 |
| `task dev:poc` | 启动 Chainlit POC | 8001 |
| `task dev:gui` | 启动 Vue 开发服务器 | 5173 |

### 测试

| 命令 | 说明 |
|------|------|
| `task test` | 运行所有测试 |
| `task test:core` | Core 包测试（含覆盖率） |
| `task test:cli` | CLI 包测试 |
| `task test:poc` | POC 前端测试 |
| `task test:gui` | Vue 前端测试 |

### 代码质量

| 命令 | 说明 |
|------|------|
| `task format` | 自动格式化所有 Python 代码 |
| `task lint` | Lint 检查所有 Python 代码 |
| `bash scripts/check.sh` | 完整开发检查（5 步） |
| `bash scripts/ci-local.sh` | CI 模拟检查（4 步） |
| `python3 scripts/check_language.py --root .` | 语言检查 |

### 清理

| 命令 | 说明 |
|------|------|
| `task clean` | 清理所有构建产物（`__pycache__`、`.pytest_cache` 等） |

## 常见问题排查

### Q: `task init` 失败

**可能原因**：
- uv 未安装 → `pip install uv`
- pnpm 未安装 → `npm install -g pnpm`
- go-task 未安装 → 参考 [taskfile.dev](https://taskfile.dev/installation/)
- Python 版本过低 → 需要 ≥ 3.12
- Node.js 版本过低 → 需要 ≥ 20

### Q: `ruff format --check` 失败

**解决方法**：运行 `task format` 自动修复，然后重新 `git add` 修改的文件。

### Q: `check_language.py` 报错有中文

**解决方法**：检查报错文件和行号，将源代码中的中文改为英文。注意：注释、变量名、字符串、docstring 都不能包含中文。

### Q: Python 测试找不到模块

**可能原因**：
- 未运行 `task init` → 先安装依赖
- 虚拟环境未激活 → 使用 `uv run pytest` 而非直接 `pytest`
- 跨包引用未配置 → 检查 `[tool.uv.sources]` 配置

### Q: Vue 测试失败

**可能原因**：
- 未安装依赖 → `cd packages/gui && pnpm install`
- TypeScript 类型错误 → `pnpm run type-check` 查看详情
- 组件渲染错误 → 检查测试中 Pinia 是否正确初始化

### Q: `task dev:server` 启动失败

**可能原因**：
- `.env` 文件不存在或 `OPENAI_API_KEY` 未配置
- 端口 8000 被占用 → `lsof -i :8000` 检查并释放端口
- 依赖未安装 → `task init:python`

### Q: Vue 前端无法连接后端 API

**可能原因**：
- 后端未启动 → 先运行 `task dev:server`
- Vite 代理配置问题 → 检查 `vite.config.ts` 中 `/api` 代理配置
- 端口不匹配 → 确认后端运行在 8000 端口
