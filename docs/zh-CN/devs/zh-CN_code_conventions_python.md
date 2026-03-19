# Python 代码规范

本文档定义 ReAct Agent 项目中所有 Python 代码的格式化、Lint、命名和文档规范。

## 格式化工具：Ruff

项目使用 [Ruff](https://docs.astral.sh/ruff/) 进行代码格式化和 Lint 检查。所有 Python 包（`core`、`cli`、`poc_frontend`）共享统一配置。

### 格式化规则

| 配置项 | 值 | 说明 |
|--------|------|------|
| `line-length` | 88 | 最大行宽 |
| `quote-style` | `"double"` | 使用双引号 |
| 缩进 | 4 空格 | 标准 Python 缩进 |
| `target-version` | `"py312"` | 目标 Python 版本 |

### 配置示例

每个包的 `pyproject.toml` 包含以下 Ruff 配置：

```toml
[tool.ruff]
target-version = "py312"
line-length = 88
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP"]

[tool.ruff.format]
quote-style = "double"
```

## Lint 规则集

| 规则前缀 | 来源 | 说明 |
|----------|------|------|
| `E` | pycodestyle errors | PEP 8 错误 |
| `W` | pycodestyle warnings | PEP 8 警告 |
| `F` | Pyflakes | 未使用变量/导入等常见错误 |
| `I` | isort | 导入排序 |
| `B` | flake8-bugbear | 常见 Bug 和设计问题 |
| `C4` | flake8-comprehensions | 推导式优化 |
| `UP` | pyupgrade | 自动升级到现代 Python 语法 |

## 格式化与 Lint 命令

```bash
# 自动格式化（修改文件）
task format

# 仅检查（不修改文件，用于 CI）
task lint

# 单个包操作
cd packages/core
uv run ruff format src/ tests/       # 格式化
uv run ruff check src/ tests/        # Lint 检查
uv run ruff check --fix src/ tests/  # Lint 检查 + 自动修复
```

## 命名约定

| 类别 | 风格 | 示例 |
|------|------|------|
| 变量、函数、方法 | `snake_case` | `tool_registry`, `register_tools()` |
| 类 | `PascalCase` | `ReactAgent`, `ToolRegistry`, `AgentConfig` |
| 常量 | `UPPER_SNAKE_CASE` | `MAX_ITERATIONS`, `DEFAULT_MODEL` |
| 模块/文件 | `snake_case` | `calculator.py`, `tool_registry.py` |
| 私有成员 | 前缀 `_` | `_build_graph()`, `_agent` |
| 包名 | `snake_case` | `agent_core`, `agent_cli` |

## 类型注解

**所有公共 API 必须有完整的类型注解**，包括：

- 函数参数和返回值
- 类属性
- 公开的模块级变量

```python
# ✅ 正确：完整的类型注解
def register_calculator_tools(registry: ToolRegistry) -> None:
    """Register all calculator tools with the given registry."""
    ...

class ToolDefinition(BaseModel):
    """Metadata for a registered tool."""

    name: str
    description: str
    func: Callable[..., Any]
    sensitivity: ToolSensitivity

# ❌ 错误：缺少类型注解
def register_calculator_tools(registry):
    ...
```

项目配置了 `mypy` 严格模式：

```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
disallow_untyped_defs = true
```

## 文档字符串（Docstring）

采用 **Google 风格** 文档字符串：

```python
def divide(a: float, b: float) -> float | str:
    """Divide a by b, with zero-division protection.

    Args:
        a: The dividend.
        b: The divisor.

    Returns:
        The quotient, or an error message if b is zero.

    Raises:
        ValueError: If inputs are not numeric.
    """
    if b == 0:
        return "Error: Division by zero"
    return a / b
```

### Docstring 要求

- 所有公共模块、类、函数、方法必须有 docstring
- 第一行为简洁的功能摘要
- 复杂函数需要 `Args`、`Returns`、`Raises` 部分
- 模块级 docstring 描述模块用途

```python
"""Tool Registry - Central registration and execution of agent tools.

Provides a decorator-based tool registration system with:
- Type-safe tool definitions via Pydantic
- Sensitivity levels for HITL control
- Async execution support
"""
```

## 语言策略

### 核心规则

**所有源代码必须使用英文**，包括：

- 变量名、函数名、类名
- 注释和行内注释
- 文档字符串（docstring）
- 字符串字面值（用户可见字符串除外）
- 异常消息

**文档**（`docs/` 目录）使用中文。

### 自动检查

项目提供 `check_language.py` 脚本，自动扫描 `packages/` 下所有源代码文件（`.py`, `.ts`, `.vue` 等），检测是否包含中文字符：

```bash
# 运行语言检查
python3 scripts/check_language.py --root .

# 详细输出
python3 scripts/check_language.py --root . --verbose
```

该检查在 CI 中作为独立 Job 执行，不通过则 PR 无法合并。

## 代码示例

### ✅ 良好的代码

```python
"""Calculator tools - POC demonstration tools for the ReAct agent.

Provides basic arithmetic operations as agent tools to demonstrate
the tool calling mechanism.
"""

from agent_core.tools.registry import ToolRegistry, ToolSensitivity


def register_calculator_tools(registry: ToolRegistry) -> None:
    """Register all calculator tools with the given registry.

    Args:
        registry: The tool registry to register tools with.
    """

    @registry.register(
        description="Add two numbers together. Args: a (float), b (float)."
    )
    def add(a: float, b: float) -> float:
        """Add two numbers."""
        return a + b

    @registry.register(
        description="Divide a by b. Args: a (float), b (float). "
        "Returns error if b is zero.",
        sensitivity=ToolSensitivity.SAFE,
    )
    def divide(a: float, b: float) -> float | str:
        """Divide a by b, with zero-division protection."""
        if b == 0:
            return "Error: Division by zero"
        return a / b
```

### ❌ 不良的代码

```python
# 没有模块 docstring

from agent_core.tools.registry import ToolRegistry

# ❌ 缺少类型注解和 docstring
def reg(r):
    # ❌ 中文注释
    # 注册计算工具
    @r.register(description="加法")  # ❌ 中文描述
    def add(a, b):  # ❌ 缺少类型注解
        return a + b

    # ❌ 无错误处理
    @r.register(description="除法")
    def divide(a, b):
        return a / b  # ❌ 没有零除保护
```

### 差异对比

| 方面 | 良好 ✅ | 不良 ❌ |
|------|---------|---------|
| 模块 docstring | 有，描述用途 | 无 |
| 函数 docstring | 有 Google 风格 | 无 |
| 类型注解 | 完整 | 缺失 |
| 语言 | 全英文 | 混用中文 |
| 命名 | `snake_case` 语义明确 | 缩写，含义模糊 |
| 错误处理 | 考虑边界情况 | 忽略 |
