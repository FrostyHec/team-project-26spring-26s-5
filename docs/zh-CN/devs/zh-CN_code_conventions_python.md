# Python 代码规范

本文档定义 ReAct Agent 项目中所有 Python 代码的格式化、Lint、命名和文档规范。

## 格式化工具：Ruff

项目使用 [Ruff](https://docs.astral.sh/ruff/) 进行代码格式化和 Lint 检查。所有 Python 包（`core`、`cli`）共享统一配置。

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

### 编码要求

**所有源代码文件必须使用 UTF-8 编码**。非 UTF-8 编码的文件（如 GBK、Latin-1 等）将被 Semgrep 无法正常读取并标记为异常。这是行业标准，确保跨平台和工具链的一致性。

### 禁止字符范围

CI 使用 Semgrep 检测并拒绝以下 **CJK 字符**：

| 范围 | 说明 |
|------|------|
| `U+4E00 – U+9FFF` | CJK 统一表意文字 |
| `U+3400 – U+4DBF` | CJK 统一表意文字扩展 A |
| `U+3000 – U+303F` | CJK 符号和标点（如 `、`、`。`、`〇`） |
| `U+FF00 – U+FFEF` | 全角 / 半角形式（如 `！`、`＂`） |
| `U+3040 – U+309F` | 平假名 |
| `U+30A0 – U+30FF` | 片假名 |
| `U+AC00 – U+D7AF` | 谚文音节（韩文） |

**以下字符不受限制（允许使用）**：Emoji、em-dash（`—`）、degree sign（`°`）、箭头（`→`、`↔`）、项目符号（`•`、`▶`）及其他非 CJK Unicode 字符。

### 自动检查工具：Semgrep

项目使用 **Semgrep** 进行语言检查，规则文件为 `semgrep-rules.yaml`。

扫描范围：

| 目录 | 说明 |
|------|------|
| `packages/` | 所有源代码文件 |
| `.github/` | CI 配置文件 |
| `scripts/` | 脚本文件 |

排除的目录：`__pycache__`、`.venv`、`node_modules`、`dist`、`build`、`output/` 等（见 `.semgrepignore`）。

```bash
# 安装 Semgrep（首次使用）
pip install semgrep

# 运行语言检查（本地开发，等价于 check.sh 的 Language Check 步骤）
semgrep --config semgrep-rules.yaml --no-git-ignore --error packages/ .github/ scripts/

# 通过 check.sh 运行（推荐）
bash scripts/check.sh --check-only
```

### 行级豁免

如果某行确实需要包含 CJK 字符（例如测试用例中的测试数据），在行末添加 `# nosemgrep`（Python/YAML/Shell）或 `// nosemgrep`（JS/TS/Vue）：

```python
# Python / YAML / Shell
test_data = "你好"  # nosemgrep
```

```typescript
// JS / TS / Vue
const data = "你好"; // nosemgrep
```

> **推荐做法**：如果需要在源代码中包含 CJK 字符串（例如 i18n 翻译），建议将这些字符串抽离到独立的 JSON / YAML 配置文件中（这些文件不在检查范围内），而非在源代码中直接使用行级豁免。

该检查在 CI 中作为独立 Job 执行，不通过则 PR 无法合并。

## 后端分层架构

项目后端采用 **Controller – Service – Store** 三层架构。每一层有明确的职责边界和校验分工。

### 架构概览

```
┌─────────────────────────────────────────────────────────┐
│  入口：REST API Controller  /  LLM Tool Function        │
│  （Pydantic 自动拦截格式错误 → HTTP 422）               │
├──────────────────────┬──────────────────────────────────┤
│                      │                                  │
│  Controller / DTO    │  Tool layer                      │
│  date / Enum 类型    │  字符串 → 强类型 (parse_date_field)│
│  Pydantic 422        │  无效值 → fallback + warning      │
├──────────────────────┴──────────────────────────────────┤
│  Service 层（唯一的业务逻辑层）                           │
│  业务校验（日期范围、状态机、权限等）                      │
│  date_type 自动降级、start_date 矫正                     │
├─────────────────────────────────────────────────────────┤
│  Store 层（纯粹的执行者）                                │
│  SQLModel async ORM — 只接收强类型对象，不做校验          │
└─────────────────────────────────────────────────────────┘
```

### 校验分工口诀

| 层 | 职责 | 比喻 |
|----|------|------|
| **Controller / DTO** | "长得对不对"——日期格式、枚举值、字符串长度 | 防君子 |
| **Service** | "道理上通不通"——日期范围、状态冲突、权限 | 防小人 |
| **Store** | "翻译和搬运"——接收强类型对象，纯 DB 操作 | 绝对执行者 |

### 关键约束

1. **层间传输强类型**：各层之间传递 `DeadlineRecord` 等 Pydantic/SQLModel 对象，**禁止传递裸 `dict` 或 JSON 字符串**。
2. **Store 层不做格式校验**：数据到达 Store 时必须已经是 `date`、`Enum` 等强类型值。
3. **Service 层是唯一的业务逻辑层**：REST Controller 和 Tool 函数都委托给同一个 Service，避免重复逻辑。

## 数据校验与类型安全

### Pydantic 自动格式校验

利用 Pydantic v2 的类型系统替代手写正则：

```python
# ✅ 声明 datetime 类型，Pydantic 自动校验 ISO-8601 格式
class CreateDeadlineRequest(BaseModel):
    title: str
    due_date: datetime | None = None      # 自动 422 如果格式不对
    priority: DeadlinePriority = ...      # 自动 422 如果不在枚举范围
```

### 枚举替代字符串常量

状态类字符串**必须**使用 `Enum`，禁止硬编码散落：

```python
# ✅ 正确
class DeadlinePriority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

record.priority = DeadlinePriority.HIGH

# ❌ 错误——magic string
record.priority = "high"
```

### SQLModel ORM

持久层使用 SQLModel 代替手写 SQL：

```python
# ✅ SQLModel table model
class DeadlineRecord(SQLModel, table=True):
    __tablename__ = "deadlines"
    id: str = Field(default="", primary_key=True)
    title: str
    due_date: datetime | None = Field(default=None)

# Store 层 CRUD（无手写 SQL）
async def add(self, record: DeadlineRecord) -> DeadlineRecord:
    async with self._session() as session:
        session.add(record)
        await session.commit()
        await session.refresh(record)
    return record
```

更多 SQLModel CRUD 模式请参考 [CRUD 开发指南](../design/zh-CN_crud_development_guide.md)。

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
