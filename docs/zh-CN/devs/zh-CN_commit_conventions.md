# 约定式提交规范

## Commit Message 格式

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

### 类型（type）

| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修复 Bug |
| `docs` | 文档修改 |
| `style` | 代码格式（不影响逻辑） |
| `refactor` | 重构 |
| `perf` | 性能优化 |
| `test` | 测试相关 |
| `build` | 构建系统或依赖变更 |
| `ci` | CI/CD 配置 |
| `chore` | 其他杂项 |
| `revert` | 回退提交 |

### 范围（scope）

推荐使用以下 scope：

- `core` — packages/core
- `cli` — packages/cli
- `poc` — packages/poc_frontend
- `gui` — packages/gui
- `docs` — 文档
- `scripts` — 脚本
- `ci` — CI/CD

### 示例

```
feat(core): add calculator tools for POC demo

fix(gui): fix SSE stream parsing for tool events

docs: update developer guide for monorepo structure

test(core): add unit tests for ToolRegistry

chore: update .gitignore for monorepo
```

## Pull Request 标题

PR 标题应遵循与 commit message 相同的格式：

```
feat(core): implement ReAct agent loop with LangGraph
```

## 工具

### Commitizen

```bash
# 交互式提交
cz commit

# 检查最近的 commit message
cz check --rev-range HEAD

# 生成 CHANGELOG
cz changelog
```

### Pre-commit Hooks

```bash
# 安装 hooks
pre-commit install --hook-type commit-msg

# 手动运行
pre-commit run --all-files
```

## 合并策略

- **默认**：Squash and Merge
- **多个逻辑独立的提交**：可选 Merge Commit
