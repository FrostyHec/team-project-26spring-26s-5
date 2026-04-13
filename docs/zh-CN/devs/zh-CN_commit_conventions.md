# 约定式提交规范

## Commit Message 格式

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

- **subject**：简洁描述，英文，小写开头，不加句号
- **body**：可选，详细描述变更原因和内容
- **footer**：可选，关联 issue、Breaking Changes 等

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

fix(core): add error handling for LLM API errors

- Add proper HTTP 502 error response for LLM API failures in chat endpoint
- Add error event handling in SSE stream endpoint
- Add test cases for chat error handling
```

## Pull Request 标题

PR 标题 **必须** 遵循与 commit message 相同的格式：

```
feat(core): implement ReAct agent loop with LangGraph
fix(gui): fix SSE stream parsing for tool events
docs: update developer guide for monorepo structure
```

### PR 描述建议

PR 描述应包含：
- **变更内容**：做了什么
- **变更原因**：为什么要改
- **测试情况**：如何验证（运行了哪些测试）
- **关联 issue**：`Closes #123` 或 `Fixes #456`

## 分支命名约定

分支名格式：`<type>/<short-description>`

| 分支前缀 | 用途 | 示例 |
|----------|------|------|
| `feature/` | 新功能开发 | `feature/add-calculator-tools` |
| `fix/` | Bug 修复 | `fix/stream-parsing-error` |
| `docs/` | 文档更新 | `docs/update-developer-guide` |
| `refactor/` | 代码重构 | `refactor/tool-registry-cleanup` |
| `test/` | 测试补充 | `test/add-api-error-tests` |
| `chore/` | 杂项维护 | `chore/update-dependencies` |

规则：
- 使用英文、小写字母
- 单词之间用 `-` 连接
- 简洁明确，体现变更意图

## 文档管理约定

### 语言策略

| 内容类型 | 语言 | 说明 |
|----------|------|------|
| 源代码 | 英文 | 变量、注释、docstring、字符串 |
| 文档 | 中文 | `docs/zh-CN/` 目录下的 Markdown 文件 |
| Commit Message | 英文 | type、scope、subject、body |
| PR 标题 | 英文 | 遵循 commit message 格式 |
| PR 描述 | 中英文均可 | 建议与团队协商 |
| CHANGELOG | 英文 | 自动生成或手动编写 |

### 文档文件命名

- 文档文件使用 `zh-CN_` 前缀，表明是中文文档
- 索引文件使用 `index.md`，不加前缀
- 示例：`zh-CN_agent.md`、`zh-CN_developers_guideline.md`

## 工具

### Commitizen

```bash
# 交互式提交（引导填写 type、scope、subject 等）
cz commit

# 检查最近的 commit message 是否符合规范
cz check --rev-range HEAD

# 生成 CHANGELOG
cz changelog
```

### Pre-commit Hooks

```bash
# 安装 hooks（仅需一次）
pre-commit install --hook-type commit-msg

# 手动运行所有 hooks
pre-commit run --all-files
```

Hook 会在提交时自动检查：
- Commit message 格式是否符合约定式提交规范
- Ruff 格式化检查

## 合并策略

- **默认**：Squash and Merge — 将 PR 所有 commit 合并为一个，保持主分支历史清晰
- **多个逻辑独立的提交**：可选 Merge Commit — 保留完整提交历史
- **禁止**：Rebase and Merge — 避免历史冲突问题

合并后 squash commit 的消息应与 PR 标题一致。
