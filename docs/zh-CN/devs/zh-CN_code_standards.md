# 代码规范

本文档定义了 `deep-solutions` 项目的代码规范、提交规范和 Pull Request 流程。

## 目录
- [代码风格](#代码风格)
- [提交规范](#提交规范)
- [Pull Request 流程](#pull-request-流程)
- [代码审查要求](#代码审查要求)
- [合并要求](#合并要求)

---

## 代码风格

### 工具链

本项目使用以下工具保证代码质量：

| 工具 | 用途 | 配置文件 |
|------|------|----------|
| **Ruff** | 代码格式化 + Lint（替代 black/isort/flake8） | `pyproject.toml` |
| **MyPy** | 静态类型检查 | `pyproject.toml` |
| **pytest** | 单元测试 | `pyproject.toml` |

### Ruff 配置

```toml
[tool.ruff]
target-version = "py38"
line-length = 88

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # Pyflakes
    "I",      # isort (import sorting)
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade
]
```

### 代码格式化命令

```bash
# 格式化代码
ruff format src/ tests/

# 检查格式（不修改）
ruff format --check src/ tests/

# Lint 检查
ruff check src/ tests/

# 自动修复 Lint 问题
ruff check --fix src/ tests/
```

### 类型注解要求

所有公共 API 必须有类型注解：

```python
from typing import Optional, List, Dict

def process_data(
    data: List[int],
    options: Optional[Dict[str, str]] = None
) -> List[int]:
    """处理数据。
    
    Args:
        data: 输入数据列表
        options: 可选的配置选项
        
    Returns:
        处理后的数据列表
    """
    if options is None:
        options = {}
    return data
```

### 文档字符串

使用 Google 风格的 docstring：

```python
def function_name(param1: str, param2: int) -> bool:
    """函数简短描述。
    
    更详细的描述（如有必要）。
    
    Args:
        param1: 参数1的描述
        param2: 参数2的描述
        
    Returns:
        返回值的描述
        
    Raises:
        ValueError: 何时抛出该异常
    """
    pass
```

---

## 提交规范

### Commit Message 格式

使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### 类型 (type)

| Type | 说明 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat: add data validation function` |
| `fix` | Bug 修复 | `fix: resolve issue #123` |
| `docs` | 文档更新 | `docs: update developer guide` |
| `style` | 代码格式（不影响功能） | `style: format with ruff` |
| `refactor` | 代码重构 | `refactor: simplify data processing` |
| `test` | 测试相关 | `test: add unit tests for core` |
| `chore` | 构建/工具相关 | `chore: update CI workflow` |
| `perf` | 性能优化 | `perf: optimize data loading` |

### 示例

```bash
# 新功能
git commit -m "feat(core): add data processing pipeline"

# Bug 修复
git commit -m "fix(utils): handle edge case in parser"

# 文档更新
git commit -m "docs: add API documentation"

# 多行提交信息
git commit -m "feat: add new feature X

- Add function A
- Add function B
- Update related tests

Closes #42"
```

### 提交原则

1. **原子性**: 每个提交只做一件事
2. **完整性**: 每个提交后项目应可正常运行
3. **描述性**: 提交信息清晰说明改动内容

---

## Pull Request 流程

### 1. 创建 PR 前的检查清单

在创建 PR 前，确保完成以下检查：

- [ ] 代码已格式化（`ruff format`）
- [ ] 通过 Lint 检查（`ruff check`）
- [ ] 通过类型检查（`mypy`）
- [ ] 添加了必要的测试
- [ ] 所有测试通过（`pytest`）
- [ ] 更新了相关文档
- [ ] 更新了 CHANGELOG.md（如适用）

**快速检查命令**：

```bash
./scripts/check.sh
```

### 2. PR 标题格式

与 commit message 格式一致：

```
<type>(<scope>): <description>
```

**示例**：
- `feat(core): add data validation`
- `fix(utils): resolve parsing issue`
- `docs: update API documentation`

### 3. PR 描述模板

```markdown
## 概述
简要描述本 PR 的目的和主要更改。

## 更改内容
- 更改 1
- 更改 2
- 更改 3

## 测试
- [ ] 添加了单元测试
- [ ] 所有测试通过
- [ ] 本地 CI 检查通过 (`./scripts/ci-local.sh`)

## 相关 Issue
Closes #xxx

## 其他说明
任何需要 reviewer 注意的事项。
```

### 4. 创建 PR 后

1. 确保 CI 检查自动启动
2. 等待所有检查完成
3. 关注 CI 失败的原因并修复
4. 请求代码审查

---

## 代码审查要求

### 审查重点

审查者应关注以下方面：

1. **功能正确性**: 代码是否正确实现了预期功能
2. **代码质量**: 代码是否清晰、可维护
3. **测试覆盖**: 是否有足够的测试覆盖
4. **性能**: 是否有明显的性能问题
5. **安全性**: 是否存在安全隐患
6. **文档**: API 是否有适当的文档

### 审查回复

使用以下标签回复：

| 标签 | 含义 |
|------|------|
| `LGTM` | Looks Good To Me - 批准合并 |
| `nit:` | 小建议，非阻塞 |
| `question:` | 需要解释 |
| `suggestion:` | 改进建议 |
| `blocking:` | 必须修改才能合并 |

---

## 合并要求

### 必须满足的条件

PR 合并前必须满足以下所有条件：

1. **CI 通过** ✅
   - Lint 检查通过
   - 类型检查通过
   - 所有测试通过
   - 构建检查通过

2. **代码审查** ✅
   - 至少获得 **1 个 LGTM** 审批
   - 所有 blocking 问题已解决

3. **分支更新** ✅
   - 与目标分支无冲突

### 合并策略

- **功能分支 → main**: Squash and merge（推荐）
- **紧急修复 → main**: Merge commit

### CI 测试策略

| 场景 | 测试范围 | 预计时长 |
|------|----------|----------|
| PR / 普通 Push | 仅 Python 3.8 | < 3 分钟 |
| Push to main | Python 3.8-3.12 全矩阵 | ~5-7 分钟 |

> 这种差异化策略在保证代码质量的同时，大幅提升 PR 的反馈速度。

---

## 常用检查命令汇总

```bash
# 代码格式化
ruff format src/ tests/

# Lint 检查
ruff check src/ tests/

# 类型检查
mypy src/

# 运行测试
pytest

# 一键检查（推荐）
./scripts/check.sh

# 完整 CI 模拟
./scripts/ci-local.sh

# 语言检查（仅源码）
python scripts/check_language.py --source-only

# 文档检查（双语结构 + 断链检查）
python scripts/document_checker.py

# 所有语言和文档检查
python scripts/check_language.py
```

---

## 相关文档

- [开发者入门指南](./zh-CN_developers_guide.md)
- [本地测试指南](./zh-CN_local_testing.md)
- [CI 工作流](./zh-CN_ci_workflow.md)
