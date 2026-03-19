# 分发与部署

本文档描述 ReAct Agent 项目的构建、打包、发布和部署流程。

## Python 包构建

### 构建系统：Hatchling

所有 Python 包（`core`、`cli`、`poc_frontend`）使用 [Hatchling](https://hatch.pypa.io/) 作为构建后端：

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/agent_core"]   # 指定源码目录
```

### 构建命令

```bash
# 构建单个包
cd packages/core
uv build

# 输出在 dist/ 目录
# dist/agent_core-0.1.0-py3-none-any.whl
# dist/agent_core-0.1.0.tar.gz
```

### 包结构

| 包名 | PyPI 名称 | 入口 | 说明 |
|------|-----------|------|------|
| `agent-core` | `agent-core` | `agent_core` | 核心引擎，无外部包依赖 |
| `agent-cli` | `agent-cli` | `agent_cli.main:main` | CLI 工具，依赖 `agent-core` |
| `agent-poc-frontend` | `agent-poc-frontend` | `poc_frontend` | Chainlit POC，依赖 `agent-core` |

### CLI 入口点

`agent-cli` 包通过 `[project.scripts]` 注册命令行入口：

```toml
[project.scripts]
agent-cli = "agent_cli.main:main"
```

安装后可直接使用：

```bash
agent-cli chat     # 交互式聊天
agent-cli serve    # 启动 API 服务器
```

## PyPI 发布

### 发布考虑

当前项目处于开发阶段，尚未发布到 PyPI。发布前需要注意：

1. **包名唯一性**：确认 `agent-core`、`agent-cli` 在 PyPI 上未被占用，否则需要更换名称
2. **版本号**：遵循 [语义化版本](https://semver.org/)（SemVer）
3. **依赖声明**：移除 `[tool.uv.sources]` 中的本地路径引用，改为版本约束
4. **README**：每个包的 `README.md` 作为 PyPI 页面描述
5. **License**：已配置 Apache 2.0 许可证

### 发布流程（计划）

```bash
# 1. 更新版本号
# 编辑 pyproject.toml 中的 version 字段

# 2. 构建
cd packages/core && uv build

# 3. 发布到 TestPyPI（测试）
uv publish --index testpypi

# 4. 验证安装
pip install --index-url https://test.pypi.org/simple/ agent-core

# 5. 发布到 PyPI（正式）
uv publish
```

### 依赖链发布顺序

由于包间存在依赖关系，发布顺序必须为：

```
1. agent-core      ← 无依赖，最先发布
2. agent-cli       ← 依赖 agent-core
3. agent-poc-frontend ← 依赖 agent-core
```

## Vue 前端构建

### 构建命令

```bash
cd packages/gui
pnpm build
```

该命令执行：
1. `vue-tsc --build` — TypeScript 类型检查
2. `vite build` — Vite 生产构建

### 构建输出

```
packages/gui/dist/
├── index.html
├── assets/
│   ├── index-[hash].js
│   └── index-[hash].css
└── ...
```

构建输出为纯静态文件，可部署到任何静态文件服务器（Nginx、Vercel、Netlify 等）。

### 部署注意事项

- 前端通过 `/api` 前缀访问后端 API，部署时需要配置反向代理
- 开发环境下 Vite 代理 `/api` → `localhost:8000`
- 生产环境需要 Nginx 或类似工具配置相同的代理规则

```nginx
# Nginx 配置示例
server {
    listen 80;

    location / {
        root /path/to/dist;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://localhost:8000/;
    }
}
```

## 发布脚本

项目 `scripts/` 目录下规划了以下发布相关脚本：

| 脚本 | 用途 | 状态 |
|------|------|------|
| `scripts/test_release.sh` | 测试发布流程（发布到 TestPyPI） | 计划中 |
| `scripts/final_release.sh` | 正式发布流程（发布到 PyPI） | 计划中 |

这些脚本将自动化以下流程：
- 版本号验证
- 运行完整测试套件
- 按依赖顺序构建和发布
- 创建 Git Tag
- 更新 CHANGELOG

## 版本管理

### 版本号规范

遵循 [语义化版本 2.0.0](https://semver.org/lang/zh-CN/)：

```
MAJOR.MINOR.PATCH
```

| 版本段 | 何时递增 | 示例 |
|--------|----------|------|
| MAJOR | 不兼容的 API 变更 | 1.0.0 → 2.0.0 |
| MINOR | 新增功能（向后兼容） | 0.1.0 → 0.2.0 |
| PATCH | 向后兼容的 Bug 修复 | 0.1.0 → 0.1.1 |

### 当前版本

| 包 | 当前版本 |
|------|----------|
| `agent-core` | 0.1.0 |
| `agent-cli` | 0.1.0 |
| `agent-poc-frontend` | 0.1.0 |
| `gui` | 0.0.0 |

### 版本同步策略

- 各包版本独立管理，不强制同步
- `agent-core` 的 MAJOR/MINOR 版本变更需要同步更新依赖包
- 使用 Git Tag 标记发布版本：`core-v0.1.0`、`cli-v0.1.0`

### CHANGELOG

项目根目录的 `CHANGELOG.md` 记录所有重要变更。可使用 Commitizen 自动生成：

```bash
cz changelog
```
