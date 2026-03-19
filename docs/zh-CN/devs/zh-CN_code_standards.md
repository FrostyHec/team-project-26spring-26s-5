# 代码规范

## 代码风格

### Python

| 规则 | 值 |
|------|------|
| 格式化工具 | Ruff |
| 行宽 | 88 字符 |
| 引号 | 双引号 |
| 缩进 | 4 空格 |
| Lint 规则集 | E, W, F, I, B, C4, UP |

### TypeScript / Vue

| 规则 | 值 |
|------|------|
| 格式化工具 | Prettier |
| Lint 工具 | ESLint + oxlint |
| 引号 | 单引号 |
| 缩进 | 2 空格 |
| 分号 | 无 |

## 命名规范

| 类型 | Python | TypeScript |
|------|--------|-----------|
| 变量/函数 | `snake_case` | `camelCase` |
| 类/接口 | `PascalCase` | `PascalCase` |
| 常量 | `UPPER_SNAKE_CASE` | `UPPER_SNAKE_CASE` |
| 文件名 | `snake_case.py` | `camelCase.ts` / `PascalCase.vue` |

## 类型注解

所有公共函数和方法必须有类型注解：

```python
# Good
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b

# Bad
def add(a, b):
    return a + b
```

## 文档字符串

使用 Google 风格：

```python
def calculate(x: float, y: float, operation: str = "add") -> float:
    """Perform a calculation on two numbers.

    Args:
        x: First operand.
        y: Second operand.
        operation: The operation to perform. Defaults to "add".

    Returns:
        The result of the calculation.

    Raises:
        ValueError: If the operation is not supported.
    """
```

## Pull Request 流程

### PR 前检查清单

- [ ] 代码风格符合规范（运行 `task format`）
- [ ] 所有测试通过（运行 `task test`）
- [ ] 没有中文出现在源代码中
- [ ] commit message 遵循约定式提交规范
- [ ] 如果修改了公共 API，更新了相关文档

### 合并要求

- CI 通过
- 至少 1 个 LGTM
- 无合并冲突
- 采用 Squash and Merge 策略
