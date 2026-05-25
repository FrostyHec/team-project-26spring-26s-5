# CI 说明文档

本文档说明当前仓库中已经配置的 CI 与自动化能力，包括触发条件、支持功能、核心实现方式，以及本地如何复现主要检查流程。

## 总览

当前仓库的 CI 主要由 GitHub Actions、`Taskfile.yml`、`scripts/check.sh`、Semgrep 规则和 Dependabot 配置组成。

| 类型 | 配置文件 | 主要用途 |
| --- | --- | --- |
| 常规 CI | `.github/workflows/ci.yml` | 在 PR 和 `main` 分支 push 时执行代码风格、语言策略、Python 测试、Vue 测试、类型检查和构建 |
| 测试报告 | `.github/workflows/report.yml` | 在 CI 完成后读取 pytest JUnit 报告，发布 GitHub Check Run，并在 PR 下维护测试结果评论 |
| Docker 构建产物 | `.github/workflows/docker-build.yml` | 手动构建 Docker 镜像，并上传可下载的 `docker save` 压缩产物 |
| Docker Hub 发布 | `.github/workflows/docker-publish.yml` | 手动将 Docker 镜像发布到 Docker Hub，支持重新构建或复用构建产物 |
| Release 发布 | `.github/workflows/release.yml` | 在推送 `v*` tag 时构建 Linux、Windows、macOS 桌面发布产物并创建 GitHub Release |
| 依赖更新 | `.github/dependabot.yml` | 每周自动为 Python 依赖和 GitHub Actions 创建依赖升级 PR |
| 本地 CI 入口 | `Taskfile.yml`、`scripts/check.sh` | 提供本地执行 lint、test、build、check-only 的统一入口 |
| 语言策略 | `semgrep-rules.yaml` | 禁止源码、脚本和 GitHub 配置中出现 CJK 字符，必要时允许逐行豁免 |

## 常规 CI

配置文件：`.github/workflows/ci.yml`

### 触发条件

- `pull_request`：所有 PR 都会触发。
- `push` 到 `main`：主分支更新时触发。

### 并发策略

使用 `concurrency.group: ci-${{ github.ref }}`，同一个 ref 上的新 CI 会取消仍在运行的旧 CI，避免 PR 连续 push 时浪费 runner 资源。

### 权限

只授予 `contents: read`。常规 CI 只需要读取仓库内容，不需要写 PR、写 Release 或写 Checks。

### 工具链

- Python：`3.12`
- Node.js：`20`
- pnpm：`10.32.1`
- Python 依赖管理：`uv`
- Python lint/format：`ruff`
- Python 测试：`pytest`，core 包额外生成 coverage 终端报告
- Vue 测试：`vitest`
- Vue 类型检查：`vue-tsc`
- Vue 构建：`vite`
- 语言策略检查：`semgrep`

### Job 结构

#### `lint`

功能：

- 安装 core、cli 的 Python 依赖。
- 安装 gui 的 pnpm 依赖。
- 检查 Python 格式。
- 检查 Python lint。
- 检查 Vue 源码格式。

实现方式：

- `actions/checkout@v6` 拉取代码。
- `astral-sh/setup-uv@v7` 安装 `uv`。
- `actions/setup-python@v6` 固定 Python `3.12`。
- `actions/setup-node@v6` 固定 Node.js `20`。
- `pnpm/action-setup@v6` 固定 pnpm `10.32.1`。
- 在 `packages/core` 和 `packages/cli` 中分别执行：
  - `uv sync --all-extras`
  - `uv run ruff format --check src/ tests/`
  - `uv run ruff check src/ tests/`
- 在 `packages/gui` 中执行：
  - `pnpm install`
  - `pnpm prettier --check --experimental-cli src/`

#### `language-check`

功能：

- 检查源码、GitHub 配置和脚本中是否出现 CJK 字符。
- 防止源码中混入中文、日文、韩文字符。该仓库允许文档使用中文，但源码、脚本、workflow 和 issue/PR 模板等受规则约束。

实现方式：

- 通过 `pip install semgrep` 安装 Semgrep。
- 执行：

```bash
semgrep --config semgrep-rules.yaml \
        --no-git-ignore \
        --error \
        --quiet \
        packages/ .github/ scripts/
```

- 规则定义在 `semgrep-rules.yaml`，核心规则是 `no-cjk-characters`。
- 如果确实需要在单行中保留相关字符，可以按规则说明追加 `# nosemgrep` 或 `// nosemgrep`。

#### `test-python`

功能：

- 执行 Python 单元测试。
- 为后续测试报告 workflow 生成 JUnit XML。
- 上传合并后的 pytest 结果产物。

依赖：

- `needs: [lint, language-check]`

实现方式：

- 安装 `uv` 和 Python `3.12`。
- 在 `packages/core` 和 `packages/cli` 中执行 `uv sync --all-extras`。
- core 测试命令：

```bash
cd packages/core
uv run pytest tests/ -v --cov=agent_core --cov-report=term-missing --junitxml=pytest-report.xml
```

- cli 测试命令：

```bash
cd packages/cli
uv run pytest tests/ -v --junitxml=pytest-report.xml
```

- 通过内联 Python 脚本读取 `packages/*/pytest-report.xml`，合并为 `test-results/pytest-report.xml`。
- 使用 `actions/upload-artifact@v7` 上传名为 `pytest-results-3.12` 的测试报告产物。
- 合并和上传步骤使用 `if: always()`，即使测试失败也尽量保留报告，便于后续展示失败详情。

#### `test-vue`

功能：

- 执行 Vue 前端测试。
- 执行 Vue 类型检查。
- 执行前端构建。

依赖：

- `needs: [lint, language-check]`

实现方式：

- 安装 Node.js `20` 和 pnpm `10.32.1`。
- 在 `packages/gui` 中执行：
  - `pnpm install`
  - `pnpm prettier --check --experimental-cli src/`
  - `pnpm vitest run`
  - `pnpm run type-check`
  - `pnpm build`

其中 `pnpm build` 在 `packages/gui/package.json` 中定义为：

```bash
run-p type-check "build-only {@}" --
```

实际会同时覆盖 `vue-tsc --build` 和 `vite build`。

## 测试报告 Workflow

配置文件：`.github/workflows/report.yml`

### 触发条件

通过 `workflow_run` 监听 `CI` workflow 完成事件：

- 只处理 `completed`。
- 只在 CI 结论为 `success` 或 `failure` 时执行报告逻辑。

### 支持功能

- 从 CI run 中下载 pytest JUnit 报告产物。
- 发布 GitHub Check Run，展示 Python 测试结果。
- 在 PR 下创建或更新固定评论，展示测试总数、通过数、失败数、耗时、commit、branch 和失败详情。

### 实现方式

#### `report` job

- 使用 `actions/checkout@v6` checkout base repository 的 `main` 分支。
- 使用 `actions/download-artifact@v8` 从触发它的 CI run 下载 `pytest-results-3.12`。
- 使用 `dorny/test-reporter@v3` 读取 `test-results/pytest-report.xml`，以 `java-junit` reporter 格式发布 Check Run。

#### `comment` job

- 只在原始 CI 事件来自 `pull_request` 且能解析到 PR 编号时运行。
- 下载同一个 pytest 报告产物。
- 用内联 Python 脚本解析 JUnit XML：
  - 统计 tests、failures、errors、skipped、duration。
  - 分组收集 passed、failed、errored、skipped test cases。
  - 生成 Markdown 格式的 PR 评论内容。
- 使用 `marocchino/sticky-pull-request-comment@v3`，以 `ci-test-summary` 作为 header 更新同一条评论，避免每次 push 都新增评论。

### 安全设计

该 workflow 使用 `workflow_run`，会在 base repository 的权限上下文中运行，因此配置中特别避免 checkout fork 代码：

- `Checkout base repository` 固定 `ref: main`。
- 事件中的 branch、sha、run URL 等不可信输入通过环境变量传给脚本，不直接在 shell 脚本中插入 `${{ }}`。
- 权限最小化为 `checks: write`、`pull-requests: write`、`actions: read`、`contents: read`。

## Docker 构建产物 Workflow

配置文件：`.github/workflows/docker-build.yml`

### 触发条件

仅支持 `workflow_dispatch` 手动触发。

### 输入参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `image_name` | `sustech-campus-assistant` | 存入 artifact 元数据中的本地镜像名 |
| `image_tag` | `manual` | 镜像 tag；为 `manual` 时自动生成 `manual-<run>-<sha>` |
| `platform` | `linux/amd64` | 构建单平台 Docker archive |

### 支持功能

- 手动构建 Docker 镜像。
- 使用 GitHub Actions cache 加速 Buildx 构建。
- 将镜像保存为 `docker save` 格式的 tar 包并 gzip 压缩。
- 上传可下载的 Docker 镜像 artifact，保留 14 天。
- 写入 GitHub Step Summary，记录镜像名、artifact 名和 run ID。

### 实现方式

- `docker/setup-buildx-action@v3` 初始化 Buildx。
- `Resolve image metadata` 根据输入生成：
  - `IMAGE_REF`
  - `IMAGE_TAG`
  - `/tmp/image-metadata.env`
- `docker/build-push-action@v6` 使用根目录 `Dockerfile` 构建镜像：
  - `context: .`
  - `file: ./Dockerfile`
  - `platforms: ${{ inputs.platform }}`
  - `load: true`
  - `cache-from: type=gha`
  - `cache-to: type=gha,mode=max`
- 通过 `docker save "$IMAGE_REF" -o /tmp/docker-image.tar` 保存镜像。
- 上传 artifact：
  - `/tmp/docker-image.tar.gz`
  - `/tmp/image-metadata.env`

### Dockerfile 构建内容

根目录 `Dockerfile` 使用多阶段构建：

- `gui-builder` 阶段：
  - 使用 Node 20。
  - 安装 pnpm 依赖。
  - 执行 `pnpm build` 生成 `packages/gui/dist`。
- `app` 阶段：
  - 使用 `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`。
  - 安装运行时依赖 `ca-certificates`、`gosu`、`libgomp1`。
  - 复制 core、cli 源码和 lock 文件。
  - 执行 `uv sync --directory packages/cli --frozen --no-dev`。
  - 复制 GUI dist。
  - 配置 `/data` volume、`8000` 端口、健康检查和 entrypoint。
  - 默认命令为 `agent-cli serve --static-dir /app/packages/gui/dist`。

## Docker Hub 发布 Workflow

配置文件：`.github/workflows/docker-publish.yml`

### 触发条件

仅支持 `workflow_dispatch` 手动触发。

### 输入参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `dockerhub_namespace` | 无，必填 | Docker Hub 用户名或组织名 |
| `image_name` | `sustech-campus-assistant` | Docker Hub 仓库名 |
| `image_tag` | `manual` | tag；为 `manual` 时自动生成 `manual-<run>-<sha>` |
| `push_latest` | `false` | 是否额外推送 `latest` tag |
| `artifact_run_id` | 空 | 可选。填写 Docker Build Artifact 的 run ID 时，复用已构建镜像 |
| `platform` | `linux/amd64` | 重新构建时的目标平台；复用 artifact 时忽略 |

### 支持功能

- 发布镜像到 Docker Hub。
- 支持两种来源：
  - 不传 `artifact_run_id`：从当前 checkout 重新构建并推送。
  - 传 `artifact_run_id`：下载此前 Docker Build Artifact 的镜像 tar，load 后重新 tag 并推送。
- 支持额外推送 `latest` tag。
- 写入 GitHub Step Summary，记录目标仓库、主 tag 和来源。

### 实现方式

- 通过 `Resolve target image metadata` 生成：
  - `TARGET_REPOSITORY`
  - `TARGET_TAG`
  - `TARGET_IMAGE_REF`
  - `DOCKER_TAGS`
- 使用 `docker/login-action@v3` 登录 Docker Hub。
- Docker Hub 凭据来自 repository secrets：
  - `DOCKERHUB_USERNAME`
  - `DOCKERHUB_TOKEN`
- 无 artifact 时：
  - 初始化 Buildx。
  - 使用 `docker/build-push-action@v6` 重新构建并 `push: true`。
- 有 artifact 时：
  - 使用 `actions/download-artifact@v8` 下载 `sustech-campus-assistant-docker-image`。
  - 读取 `image-metadata.env`。
  - `gunzip -c docker-image/docker-image.tar.gz | docker load`。
  - `docker tag` 到目标 Docker Hub image。
  - `docker push` 主 tag，必要时再推送 `latest`。

## Release Workflow

配置文件：`.github/workflows/release.yml`

### 触发条件

推送 tag 时触发，tag 必须匹配：

```text
v*
```

workflow 内部还会校验 tag 去掉前缀 `v` 后是否满足语义化版本格式，例如：

- `v1.2.3`
- `v1.2.3-beta.1`

### 支持功能

- 同时构建 Linux、Windows、macOS 三个平台的发布产物。
- 在构建前运行仓库检查。
- 构建前端 GUI。
- 构建后端 staging 目录。
- 如果配置了 `EMBEDDING_API_KEY`，预构建 policy index。
- 如果没有配置 `EMBEDDING_API_KEY`，在 Step Summary 中写入警告，说明产物不包含预构建 policy index。
- 对后端 staging 目录执行 smoke test。
- 构建桌面包。
- 上传各平台构建产物。
- 所有平台构建完成后，整理 release 文件并创建 GitHub Release。

### 构建矩阵

| 平台名 | runner |
| --- | --- |
| `linux` | `ubuntu-22.04` |
| `windows` | `windows-latest` |
| `macos` | `macos-latest` |

### 实现方式

#### `build` job

- `actions/checkout@v6` 拉取代码。
- `Resolve release version` 从 `GITHUB_REF_NAME` 解析版本号，并写入：
  - `RELEASE_VERSION`
  - `PACKAGE_VERSION`
  - `DESKTOP_APP_VERSION`
- 安装工具链：
  - `uv`
  - Python `3.12`
  - Node.js `20`
  - pnpm `10.32.1`
- 安装依赖：
  - `packages/core`: `uv sync --all-extras`
  - `packages/cli`: `uv sync --all-extras`
  - `packages/gui`: `pnpm install`
- 运行仓库检查：

```bash
bash scripts/check.sh --check-only
```

- 构建 GUI：

```bash
pnpm --dir packages/gui build
```

- 构建后端 staging：

```bash
python scripts/packaging/package_backend.py --skip-gui-build --version "$RELEASE_VERSION"
```

- 如果存在 `EMBEDDING_API_KEY`：

```bash
cd packages/cli
uv run agent-cli build-policy-index --env-file ../../build/package/backend-staging/config/.env
```

- smoke test：

```bash
bash scripts/packaging/debug_packaged_app.sh --staging-dir build/package/backend-staging
```

- 桌面打包：

```bash
bash scripts/packaging/package_desktop.sh
```

- 上传 artifact：
  - `build/package/backend-staging`
  - `build/package/artifacts/desktop`

#### `publish` job

- 依赖所有 matrix `build` 完成。
- 下载 artifact：

```text
sustech-campus-assistant-*
```

- 整理 release 文件：

```bash
bash scripts/packaging/prepare_release_files.sh release-artifacts release-files
```

- 使用 `softprops/action-gh-release@v2` 发布 GitHub Release，并上传 `release-files/*`。

### 权限

Release workflow 使用 `contents: write`，因为它需要创建或更新 GitHub Release。

## Dependabot 自动依赖更新

配置文件：`.github/dependabot.yml`

该配置不是测试流水线，但属于 CI 周边自动化。

### Python 依赖更新

- ecosystem：`pip`
- directory：`/`
- 周期：每周一 `03:00`
- PR 上限：10
- reviewer 和 assignee：`FrostyHec`
- commit message prefix：
  - 生产依赖：`build(deps)`
  - 开发依赖：`build(deps-dev)`
- 自动 rebase。
- 分组策略：
  - minor/patch 更新合并到 `minor-patch` 组。
  - major 更新合并到 `major` 组。

### GitHub Actions 更新

- ecosystem：`github-actions`
- directory：`/`
- 周期：每周一 `04:00`
- PR 上限：5
- reviewer 和 assignee：`FrostyHec`
- commit message prefix：`ci(actions)`
- 自动 rebase。
- 所有 actions 更新合并到 `actions-all` 组。

## 本地 CI 与检查入口

### Taskfile

配置文件：`Taskfile.yml`

`Taskfile.yml` 提供跨包任务入口。与 CI 直接相关的任务包括：

| 任务 | 功能 |
| --- | --- |
| `task init` | 安装全部依赖 |
| `task init:python` | 安装 core 和 cli 的 Python 依赖 |
| `task init:gui` | 安装 Vue 前端依赖 |
| `task lint` | 执行全部 lint 和格式检查 |
| `task lint:core` | 检查 core 包 Python lint 和格式 |
| `task lint:cli` | 检查 cli 包 Python lint 和格式 |
| `task lint:gui` | 检查 GUI Prettier 格式 |
| `task test` | 执行全部测试 |
| `task test:core` | 执行 core 测试和 coverage |
| `task test:cli` | 执行 cli 测试 |
| `task test:gui` | 执行 GUI Vitest 测试 |
| `task ci` | 本地执行完整 CI 基础流程，即 `task lint` 后接 `task test` |

本地基础 CI 命令：

```bash
task ci
```

需要注意：`task ci` 覆盖 lint 和测试，但不包含 Semgrep 语言策略检查、Vue type-check 和 Vue build。更接近 GitHub Release 检查的是 `scripts/check.sh --check-only`。

### scripts/check.sh

配置文件：`scripts/check.sh`

这是仓库推荐的端到端检查脚本，也是 Release workflow 使用的检查入口。

支持模式：

| 命令 | 模式 | 行为 |
| --- | --- | --- |
| `bash scripts/check.sh` | dev mode | 先自动格式化，再执行检查、测试、类型检查和构建 |
| `bash scripts/check.sh --check-only` | CI mode | 不修改文件，只执行检查、测试、类型检查和构建 |
| `bash scripts/check.sh --help` | help | 输出帮助 |

#### dev mode 步骤

1. 使用 Ruff 格式化 core 和 cli，并执行 Ruff auto-fix。
2. 使用 pnpm format 格式化 GUI。
3. 执行 Python lint 和 Vue 格式检查。
4. 执行 Semgrep 语言策略检查。
5. 执行 core 和 cli 的 pytest。
6. 执行 GUI Vitest。
7. 执行 GUI type-check 和 build。

#### check-only 模式步骤

1. 跳过自动格式化。
2. 执行 Python lint 和 Vue 格式检查。
3. 执行 Semgrep 语言策略检查。
4. 执行 core 和 cli 的 pytest。
5. 执行 GUI Vitest。
6. 执行 GUI type-check 和 build。

#### Semgrep 查找方式

`scripts/check.sh` 会优先使用本机 `semgrep`，如果不存在则尝试：

- `uvx --from semgrep semgrep`
- `uv tool run --from semgrep semgrep`

如果都不可用，脚本会失败并提示安装 Semgrep 或 uv。

## Pre-commit 辅助检查

配置文件：`.pre-commit-config.yaml`

该配置不是 GitHub Actions CI，但可以在本地提交前提前拦截问题。

已配置的 hooks：

- Ruff：
  - `ruff --fix`
  - `ruff-format`
- Commitizen：
  - 校验 commit message
- 通用文件检查：
  - trailing whitespace
  - end-of-file-fixer
  - check-yaml
  - check-added-large-files
  - check-merge-conflict

启用方式：

```bash
pip install pre-commit
pre-commit install
```

手动运行：

```bash
pre-commit run --all-files
```

## 常见开发验证建议

提交前建议至少运行：

```bash
bash scripts/check.sh --check-only
```

如果正在本地开发并希望自动修复格式问题，可以运行：

```bash
bash scripts/check.sh
```

如果只想快速覆盖基础 lint 和测试，可以运行：

```bash
task ci
```

如果改动涉及 Dockerfile 或运行时打包，应额外手动触发：

- `Docker Build Artifact`
- 必要时再触发 `Docker Publish to Docker Hub`

如果改动涉及 release 打包脚本、桌面端构建、版本号或后端 staging 结构，应通过推送符合格式的 `v*` tag 验证 Release workflow。
