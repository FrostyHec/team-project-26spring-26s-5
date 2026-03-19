# 本地测试指南

## 测试方法概览

| 方法 | 耗时 | 说明 |
|------|------|------|
| `bash scripts/check.sh` | ~30s | 快速检查（格式+lint+语言+测试） |
| `bash scripts/ci-local.sh` | ~1min | CI 模拟（不自动修复） |
| `task test` | ~20s | 运行所有测试 |
| `task test:core` | ~5s | 仅核心包测试 |

## 快速检查脚本（check.sh）

开发过程中最常用的检查方式：

```bash
bash scripts/check.sh
```

执行步骤：
1. **Step 1/5**: Code Formatting — 使用 Ruff 自动格式化 Python 代码
2. **Step 2/5**: Lint Check — 使用 Ruff 检查 Python 代码质量
3. **Step 3/5**: Language Check — 检查源代码中是否有中文
4. **Step 4/5**: Python Tests — 运行 pytest 测试
5. **Step 5/5**: Vue Tests — 运行 Vitest 测试

## CI 模拟脚本（ci-local.sh）

提交 PR 前使用，模拟 CI 环境（不自动修复代码）：

```bash
bash scripts/ci-local.sh
```

执行步骤：
1. **Step 1/4**: Lint & Format Check — 检查但不修复
2. **Step 2/4**: Language Check — 中文检查
3. **Step 3/4**: Python Tests — pytest
4. **Step 4/4**: Vue Tests — Vitest

## 使用 Taskfile 运行测试

```bash
# 运行所有测试
task test

# 运行特定包测试
task test:core        # 核心引擎测试（含覆盖率）
task test:cli         # CLI 测试
task test:poc         # POC 前端测试
task test:gui         # Vue 前端测试
```

## 单独运行测试工具

### Python 测试（pytest）

```bash
# 运行特定包
cd packages/core && uv run pytest tests/ -v

# 运行特定测试文件
cd packages/core && uv run pytest tests/test_registry.py -v

# 运行带覆盖率
cd packages/core && uv run pytest tests/ -v --cov=agent_core --cov-report=term-missing
```

### Python Lint（ruff）

```bash
# 检查
cd packages/core && uv run ruff check src/ tests/

# 自动修复
cd packages/core && uv run ruff check --fix src/ tests/

# 格式化
cd packages/core && uv run ruff format src/ tests/
```

### Vue 测试（Vitest）

```bash
cd packages/gui && pnpm vitest run
```

### 语言检查

```bash
python3 scripts/check_language.py --root .
```

## 常见问题

**Q: 测试找不到 `agent_core` 模块？**

A: 确保运行了 `task init` 或 `cd packages/core && uv sync --all-extras`。各包通过 editable install（`uv.sources` path reference）互相引用。

**Q: Vue 测试超时？**

A: 检查 `packages/gui/node_modules` 是否存在，运行 `cd packages/gui && pnpm install`。

**Q: CI 和本地测试结果不一致？**

A: 运行 `bash scripts/ci-local.sh`，它更接近 CI 环境。CI 不会自动格式化代码。
