# CI/CD 工作流

## 工作流概览

| 工作流 | 触发条件 | 说明 |
|--------|----------|------|
| CI | PR / push to main | Lint、语言检查、测试 |

## CI 工作流

### 触发条件

- Pull Request（所有分支）
- Push 到 `main` 分支

### 检查步骤

1. **Lint & Format Check** — 使用 Ruff 检查 Python 代码格式和 Lint 规则
2. **Language Check** — 使用 `check_language.py` 检查源代码中是否有中文
3. **Python Tests** — 对 `packages/core`、`packages/cli`、`packages/poc_frontend` 运行 pytest
4. **Vue Tests** — 对 `packages/gui` 运行 Vitest

### 本地模拟

```bash
# 完整 CI 模拟
bash scripts/ci-local.sh

# 或使用 Taskfile
task ci
```

## 开发者使用指南

### PR 前检查清单

1. 运行 `bash scripts/check.sh` 确保所有检查通过
2. 确保 commit message 遵循约定式提交规范
3. 如果新增了源代码文件，确保不包含中文字符

### 常见问题

**Q: CI 中 language check 失败怎么办？**

A: 检查新增/修改的 `.py`、`.ts`、`.vue` 文件中是否有中文字符。源代码（注释、变量名、字符串）必须全部使用英文。

**Q: 如何在本地运行和 CI 完全一致的检查？**

A: 运行 `bash scripts/ci-local.sh`，它模拟了 CI 的所有步骤（不会自动修复代码）。
