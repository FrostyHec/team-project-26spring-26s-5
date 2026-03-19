# Commit 和 PR 规范

本文档描述 `deep-solutions` 项目的 commit message 和 pull request 规范。

## 目录
- [Commit Message 格式](#commit-message-格式)
- [Commit 类型](#commit-类型)
- [示例](#示例)
- [Pull Request 指南](#pull-request-指南)
- [工具](#工具)
- [合并策略](#合并策略)

---

## Commit Message 格式

我们遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>(<scope>): <subject>

[可选 body]

[可选 footer]
```

### 结构说明

| 部分 | 是否必须 | 说明 |
|------|----------|------|
| `type` | ✅ 必须 | 变更类型（见下表） |
| `scope` | ❌ 可选 | 影响的模块/组件（如 `core`, `api`, `docs`） |
| `subject` | ✅ 必须 | 简短描述（≤50字符，祈使句，无句号） |
| `body` | ❌ 可选 | 详细说明（每行≤72字符） |
| `footer` | ❌ 可选 | Issue 引用、破坏性变更 |

---

## Commit 类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(core): add data validation` |
| `fix` | Bug 修复 | `fix(utils): resolve parsing error` |
| `docs` | 仅文档修改 | `docs(readme): update installation guide` |
| `style` | 代码格式（不影响功能） | `style: format with ruff` |
| `refactor` | 代码重构（既不是新功能也不是修复） | `refactor(core): simplify data processing` |
| `perf` | 性能优化 | `perf: optimize data loading` |
| `test` | 添加或更新测试 | `test(core): add unit tests` |
| `build` | 构建系统或依赖 | `build: update setuptools` |
| `ci` | CI/CD 配置 | `ci: add Python 3.12 to matrix` |
| `chore` | 其他变更（维护） | `chore: update gitignore` |
| `revert` | 回退提交 | `revert: revert "feat: add X"` |

---

## 示例

### 简单提交
```
feat(core): add dynamic batch sampler
```

### 带 body 的提交
```
fix(cli): handle config path with tilde expansion

The CLI was not expanding ~ in file paths, causing
FileNotFoundError when users specified paths like
~/.config/app.yaml

Closes #55
```

### 破坏性变更
```
feat(api): change return type of process()

BREAKING CHANGE: process() now returns a dataclass instead of dict.
Users should update their code to access fields as attributes.

Migration:
- Before: result["value"]
- After: result.value
```

---

## Pull Request 指南

### PR 标题格式

PR 标题应遵循与 commit message 相同的格式：

```
<type>(<scope>): <description>
```

**示例：**
- `feat(core): add data validation pipeline`
- `fix(utils): resolve edge case in parser`
- `docs: update API documentation`

### PR 描述

使用提供的 PR 模板，包括：
- 变更描述
- 变更类型
- 相关 Issue
- 检查清单

### 合并要求

1. **所有 CI 检查必须通过**
   - Lint 检查
   - 类型检查
   - 所有测试通过
   - 构建检查

2. **至少一个审批（LGTM）**

3. **无合并冲突**

---

## 工具

### Commitizen

我们使用 [Commitizen](https://commitizen-tools.github.io/commitizen/) 来：
- 交互式创建 commit message
- 验证 commit message
- 自动生成 CHANGELOG

#### 使用方法

```bash
# 交互式提交（推荐）
cz commit
# 或
cz c

# 检查最后一次提交是否有效
cz check --rev-range HEAD

# 生成/更新 CHANGELOG
cz changelog
```

### Pre-commit

Pre-commit hooks 自动验证 commit message：

```bash
# 安装 hooks（一次性设置）
pre-commit install --hook-type commit-msg

# 手动运行所有 hooks
pre-commit run --all-files
```

### Git Commit 模板

项目提供了 commit message 模板 `.gitmessage`。使用方法：

```bash
# 仅为本仓库设置
git config commit.template .gitmessage

# 或全局设置
git config --global commit.template ~/.gitmessage
```

---

## 合并策略

大多数 PR 使用 **Squash and Merge**：

- 保持 `main` 分支历史干净线性
- 每个 PR 变成单个原子提交
- PR 标题成为 commit message

### 何时使用其他策略

| 策略 | 使用场景 |
|------|----------|
| **Squash and Merge** | 大多数 PR（默认） |
| **Merge Commit** | 历史重要的大型 PR |
| **Rebase and Merge** | 应该保持分开的小型 PR |

---

## CHANGELOG 生成

CHANGELOG 从 commit messages 自动生成：

- `feat` → **Added** 部分
- `fix` → **Fixed** 部分
- `BREAKING CHANGE` → **Breaking Changes** 部分

生成/更新 CHANGELOG：

```bash
cz changelog
```

---

## 相关文档

- [代码规范](./zh-CN_code_standards.md)
- [开发者指南](./zh-CN_developers_guide.md)
- [语言规范](./zh-CN_language_guidelines.md)
