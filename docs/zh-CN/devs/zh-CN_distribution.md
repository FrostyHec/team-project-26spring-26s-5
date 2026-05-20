# 分发与部署

本文档描述 SUSTech Campus Assistant 项目的构建、打包、发布和部署流程。

## Python 包构建

### 构建系统：Hatchling

所有 Python 包（`core`、`cli`）使用 [Hatchling](https://hatch.pypa.io/) 作为构建后端：

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
agent-cli serve --env-file /path/to/.env  # 使用指定运行时配置
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

运行时数据默认由 `DATA_PATH` 控制。`DB_PATH` 留空时等于 `DATA_PATH`，运行时数据库会以固定文件名写入该目录，例如 `sessions.db`、`courses.db`、`course_materials.db`、`email.db`、`deadlines.db`。`LOG_FILE`、`LLM_SETTINGS_PATH`、`POLICY_PDF_DIR`、`POLICY_INDEX_DIR` 留空时会分别派生到 `DATA_PATH` 下的日志、LLM 设置、PDF 与索引目录。

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

## 桌面应用与本地 Web 打包

当前桌面分发采用：

- PyInstaller 打包 `agent-cli serve` 作为后端 sidecar。
- Electron 启动后端 sidecar，并打开同一个本地 Web 应用。
- Vite 构建后的 `packages/gui/dist` 由后端 packaged app 同源托管。

打包后的路由结构：

| 路径 | 用途 |
|------|------|
| `/api/*` | 后端业务 API |
| `/files/*` | PDF 与文件访问，保持顶层路径 |
| `/*` | Vue 静态资源与 history fallback |

### 本地打包当前平台

```bash
bash scripts/packaging/package_all_local.sh
```

该脚本只构建当前运行环境对应的平台产物：

| 本机环境 | 本地目标 |
|----------|----------|
| Linux | AppImage + tar.gz |
| Windows | NSIS exe |
| macOS | dmg + zip |

不支持在单个本机环境中可靠地交叉打出三平台产物。原因是 PyInstaller 不是通用交叉编译器，且本项目包含 `faiss-cpu`、`PyMuPDF`、`cryptography` 等 native 依赖。正式三平台产物由 GitHub Actions release matrix 分别在 `ubuntu-20.04`、`windows-latest`、`macos-latest` 上构建。

本地打包默认使用内部版本号 `internal`，桌面包内部的 Electron semver 会临时写为 `0.0.0-internal`，产物文件名使用 `internal`。如果需要本地指定显示版本，可执行：

```bash
PACKAGE_VERSION=demo DESKTOP_APP_VERSION=0.0.0-demo bash scripts/packaging/package_desktop.sh
```

Release workflow 只在 `v*` tag 上运行，并校验 tag 形如 `v1.2.3` 或 `v1.2.3-beta.1`。CI 会从 tag 自动提取版本，传给 backend manifest、桌面 `package.json.version` 和桌面产物文件名。

### 后端 staging 调试

可单独生成并调试后端 staging：

```bash
pnpm --dir packages/gui build
python scripts/packaging/package_backend.py --skip-gui-build
bash scripts/packaging/debug_packaged_app.sh --staging-dir build/package/backend-staging
```

调试脚本默认复制 staging 到临时目录运行，因此健康检查产生的数据库和日志不会污染待上传的 staging 产物。只有需要保留现场时才使用 `--in-place`。

staging 结构：

```text
backend-staging/
├── bin/
│   └── react-agent-backend(.exe)
├── gui/
│   ├── index.html
│   └── assets/
├── config/
│   └── .env
├── output/
│   └── pdfs/
└── package-manifest.json
```

`config/.env` 是用户可编辑配置文件。打包脚本会把发行包内默认值写为 `DATA_PATH=../output`，因此在 `config/.env` 旁边的上级发行目录中使用 `output/` 作为默认数据目录。仓库根目录 `pdfs/` 下的文件会复制到默认 `output/pdfs/`，未配置 `POLICY_PDF_DIR` 时可直接通过 `/files/pdfs/<filename>` 访问。

桌面发行包内的初始化模板使用 `resources/env-template/env.template`，首次启动时复制为用户可编辑的 `config/.env`。Linux 桌面产物会在 electron-builder 的 `linux.executableArgs` 中写入 Chromium `--no-sandbox` 参数，并通过 `afterPack` hook 把 Linux 可执行文件替换为 wrapper，使 AppImage 直接执行时也会在进入 Electron 前自动追加 `--no-sandbox`；应用启动后也会保留同名 Electron command-line switch 作为兜底，以避免部分 Ubuntu/AppImageLauncher 环境中 `chrome-sandbox` 不能以 root/setuid 权限挂载导致启动前崩溃。

### 清理打包缓存

清理本地打包产物和打包缓存：

```bash
bash scripts/packaging/clear_package_build.sh
```

默认清理 `build/package`、历史遗留的 `.nonpublic/build/package`、以及 `packages/desktop/dist`。如果需要同时清理桌面端依赖或用户运行时配置，可显式执行：

```bash
bash scripts/packaging/clear_package_build.sh --desktop-deps
bash scripts/packaging/clear_package_build.sh --runtime-config
```

### Policy Index 预构建

Release workflow 会在存在 `EMBEDDING_API_KEY` secret 时执行：

```bash
agent-cli build-policy-index --env-file config/.env
```

如果缺少该 secret，release 不会失败，只会打包默认 PDF，并在 workflow 日志与 summary 中输出 warning。用户后续配置 embedding key 后，可以在发行包目录中手动执行同一命令生成 `${DATA_PATH}/policy_index`。

### Linux AppImage 说明

Linux 主产物为 AppImage，同时提供 tar.gz fallback。部分 Linux 环境缺少 FUSE 时可能无法直接运行 AppImage；这种情况下优先使用 tar.gz fallback，或按系统要求安装 `libfuse2`。

## 发布脚本

项目 `scripts/` 目录下规划了以下发布相关脚本：

| 脚本 | 用途 | 状态 |
|------|------|------|
| `scripts/packaging/package_backend.py` | 构建 PyInstaller 后端 sidecar 与 backend staging | 已实现 |
| `scripts/packaging/debug_packaged_app.sh` | 调试 backend staging 的配置、静态资源、健康检查和 PDF 访问 | 已实现 |
| `scripts/packaging/package_desktop.sh` | 调用 Electron Builder 构建当前平台桌面产物 | 已实现 |
| `scripts/packaging/package_all_local.sh` | 本地一键检查并打包当前平台 | 已实现 |
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
| `desktop` | 0.0.0-internal |

### 版本同步策略

- 各包版本独立管理，不强制同步
- `agent-core` 的 MAJOR/MINOR 版本变更需要同步更新依赖包
- 桌面 release 使用 Git Tag 标记发布版本：`v1.2.3` 或 `v1.2.3-beta.1`
- release CI 会从 tag 自动推导版本；本地打包默认使用 `internal`

### CHANGELOG

项目根目录的 `CHANGELOG.md` 记录所有重要变更。可使用 Commitizen 自动生成：

```bash
cz changelog
```
