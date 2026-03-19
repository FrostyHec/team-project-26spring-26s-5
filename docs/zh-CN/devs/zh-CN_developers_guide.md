# 开发者指南

## 前置条件

| 工具 | 版本 | 说明 |
|------|------|------|
| Python | ≥3.12 | 运行时 |
| Node.js | ≥20 | Vue 前端 |
| Git | ≥2.0 | 版本控制 |
| uv | 最新 | Python 包管理 |
| pnpm | 最新 | Node.js 包管理 |
| go-task | ≥3 | 任务编排 |

### 安装工具链

```bash
# uv（Python 包管理器）
pip install uv
# 或 curl -LsSf https://astral.sh/uv/install.sh | sh

# pnpm（Node.js 包管理器）
npm install -g pnpm

# go-task（任务编排工具）
# 参考 https://taskfile.dev/installation/
```

## 环境设置

```bash
# 1. 克隆仓库
git clone <repo-url>
cd team-project-26spring-26s-5

# 2. 一键安装所有依赖
task init

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API Key

# 4. 验证安装
task test
```

`task init` 会自动执行：
- `uv sync --all-extras` 为 core、cli、poc_frontend 安装 Python 依赖
- `pnpm install` 为 gui 安装 Node.js 依赖

## 开发工作流

### 常用命令

| 命令 | 说明 |
|------|------|
| `task init` | 安装所有依赖 |
| `task dev:server` | 启动 FastAPI 后端 |
| `task dev:poc` | 启动 Chainlit POC |
| `task dev:gui` | 启动 Vue 前端 |
| `task test` | 运行所有测试 |
| `task lint` | Lint 检查 |
| `task format` | 自动格式化 |
| `task clean` | 清理构建产物 |
| `bash scripts/check.sh` | 完整检查（格式+lint+语言+测试） |
| `bash scripts/ci-local.sh` | CI 模拟 |

### 开发流程

1. 创建功能分支：`git checkout -b feature/xxx`
2. 开发并频繁运行 `bash scripts/check.sh`
3. 使用约定式提交：`git commit -m "feat(core): description"`
4. 推送并创建 PR
5. 等待 CI 通过和 Code Review

### 目录导航

```bash
# Python 包
cd packages/core    # 核心引擎
cd packages/cli     # CLI 工具
cd packages/poc_frontend  # Chainlit POC

# Vue 前端
cd packages/gui

# 脚本
ls scripts/

# 文档
ls docs/zh-CN/
```
