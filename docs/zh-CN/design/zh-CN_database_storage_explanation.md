# A015: 数据库存储架构解析

## 文档概览

本文档详细解释项目中数据库（DB）的存储位置、初始化流程、以及为什么会出现多个 `output` 目录的现象。

省流：
  ⭐ cli/output/ 是"真正"运行时的数据库
  • core/output/ 是测试产生的临时数据
  • ./output/ 是其他脚本产生的数据

---

## 1. 项目架构总览

### 1.1 三层包结构

项目由三个独立的 Python 包组成，各自有不同的职责：

| 包名 | 位置 | 职责 | 依赖关系 |
|------|------|------|---------|
| `core` | `packages/core/` | 核心业务逻辑、数据持久化、API 定义 | 无依赖 |
| `cli` | `packages/cli/` | 命令行入口、FastAPI 服务器启动 | 依赖 `core` |
| `gui` | `packages/gui/` | Vue.js 前端 | 调用 CLI 提供的 API |

### 1.2 执行流程

当运行 `task dev:server` 时的执行链路：

```
Taskfile.yml
  ↓
cd packages/cli && uv run agent-cli serve --port 8000
  ↓
packages/cli/src/agent_cli/main.py::run_server()
  ↓
uvicorn 启动 FastAPI 应用 (packages/core/src/agent_core/api/server.py)
  ↓
应用生命周期启动 (lifespan) → init_dependencies()
  ↓
初始化 SessionStore 和 DeadlineStore
```

---

## 2. 数据库存储位置详解

### 2.1 两个数据库文件

项目使用 **两个独立的 SQLite 数据库**：

| DB 名称 | 文件名 | 用途 | 创建者 |
|---------|--------|------|--------|
| **Session DB** | `sessions.db` | 存储聊天会话历史、消息记录 | `SessionStore` |
| **Deadline DB** | `deadlines.db` | 存储学术截止日期任务 | `DeadlineStore` |

### 2.2 为什么有两个 `output` 目录？

问题的根源在于 **工作目录（working directory）** 的不同：

#### 当运行 `task dev:server` 时：

```yaml
# Taskfile.yml 中的定义
dev:server:
  desc: "Start the FastAPI backend server"
  dir: "{{.CLI_DIR}}"              # ← 关键：cd 到 packages/cli/
  cmds:
    - uv run agent-cli serve --port 8000
```

**执行流程：**

1. Taskfile 切换工作目录到 `packages/cli/`
2. 运行 `agent-cli serve`
3. 应用读取配置中的 `db_path = "./output/sessions.db"`
4. 因为当前工作目录是 `packages/cli/`，所以创建 `packages/cli/output/sessions.db`

#### 配置来源（`packages/core/src/agent_core/config.py`）：

```python
@dataclass
class AgentConfig:
    db_path: str = "./output/sessions.db"      # ← 相对路径！
    log_file: str = "./output/logs/agent.log"
```

#### 当在项目根目录运行 pytest 时：

```bash
cd /path/to/project/  # 项目根目录
bash scripts/check.sh --check-only
```

**执行流程：**

1. 工作目录是项目根目录
2. 测试代码运行时，如果创建 `SessionStore("./output/sessions.db")`
3. 则创建 `./output/sessions.db`（项目根目录）

### 2.3 两个目录的内容对比

**`packages/cli/output/`（由 `task dev:server` 创建）：**
```
packages/cli/output/
├── deadlines.db           (13 行 deadline 数据 - 真实数据)
├── deadlines.db-shm       (SQLite WAL 文件)
├── deadlines.db-wal       (SQLite WAL 文件)
├── sessions.db            (94 KB - 聊天历史)
├── sessions.db-shm        (SQLite WAL 文件)
└── sessions.db-wal        (SQLite WAL 文件)
```

**`packages/core/output/`（由 pytest 创建）：**
```
packages/core/output/
├── logs/
│   └── agent.log
└── sessions.db            (24 KB - 测试运行产生的会话)
```

---

## 3. 数据库初始化流程

### 3.1 SessionStore 初始化链路

```
1. packages/core/api/dependencies.py::init_dependencies()
   ↓
2. config = AgentConfig.from_env()
   - 读取 db_path = "./output/sessions.db"
   ↓
3. store = SessionStore(config.db_path)
   ↓
4. await store.initialize()
   - 打开数据库连接
   - 创建 sessions 和 messages 表
```

### 3.2 DeadlineStore 初始化链路

```
1. 工具调用时（首次访问 /deadlines 端点）
   ↓
2. packages/core/tools/deadline.py::list_deadlines()
   → await get_deadline_store()
   ↓
3. packages/core/persistence/deadline_provider.py::get_deadline_store()
   - 检查单例是否已初始化
   - 如果未初始化：
     - 读取 AgentConfig.db_path（"./output/sessions.db"）
     - 提取目录：Path(db_path).parent = "./output/"
     - 创建 deadlines.db 放在同一目录
   ↓
4. await store.initialize()
   - 创建异步引擎
   - 创建 deadlines 表
```

### 3.3 关键代码片段：`deadline_provider.py`

```python
async def get_deadline_store() -> DeadlineStore:
    """Return (and lazily initialise) the deadline store singleton."""
    global _store
    if _store is None or not _store.is_connected:
        try:
            from agent_core.config import AgentConfig
            cfg = AgentConfig.from_env()
            # 关键：提取 sessions.db 所在目录，将 deadlines.db 放在同一位置
            db_path = str(Path(cfg.db_path).with_name("deadlines.db"))
        except Exception:
            db_path = ":memory:"
        _store = DeadlineStore(db_path)
        await _store.initialize()
    return _store
```

**逻辑：**
- `cfg.db_path` = `"./output/sessions.db"`
- `Path(...).with_name("deadlines.db")` = `"./output/deadlines.db"`
- 两个数据库存储在同一目录，便于管理和备份

---

## 4. 依赖注入与单例管理

### 4.1 SessionStore 的单例模式

**位置：** `packages/core/api/dependencies.py`

```python
# 模块级单例（应用启动时初始化）
_store: SessionStore | None = None

async def init_dependencies(config: AgentConfig | None = None) -> None:
    """应用启动时调用（FastAPI lifespan）"""
    global _store
    _store = SessionStore(config.db_path)
    await _store.initialize()

async def shutdown_dependencies() -> None:
    """应用关闭时调用"""
    global _store
    if _store:
        await _store.close()
        _store = None

def get_store() -> SessionStore:
    """FastAPI 依赖注入：routes 调用此函数获得单例"""
    if _store is None:
        raise RuntimeError("Store not initialized")
    return _store
```

**使用示例：**
```python
# 在 routes 中
from fastapi import Depends
from agent_core.api.dependencies import get_store

@router.get("/sessions")
async def list_sessions(store: SessionStore = Depends(get_store)):
    return await store.list_sessions()
```

### 4.2 DeadlineStore 的懒初始化单例

**位置：** `packages/core/persistence/deadline_provider.py`

```python
# 模块级单例（使用时才初始化 - lazy initialization）
_store: DeadlineStore | None = None

async def get_deadline_store() -> DeadlineStore:
    """获取或创建 DeadlineStore 单例"""
    global _store
    if _store is None or not _store.is_connected:
        # 首次访问时创建
        db_path = str(Path(AgentConfig.from_env().db_path).with_name("deadlines.db"))
        _store = DeadlineStore(db_path)
        await _store.initialize()
    return _store

async def set_deadline_store(store: DeadlineStore | None) -> None:
    """用于测试：替换或清除单例"""
    global _store
    _store = store
```

**与 SessionStore 的区别：**

| 特性 | SessionStore | DeadlineStore |
|------|--------------|---------------|
| 初始化时机 | 应用启动时（eager） | 首次使用时（lazy） |
| 初始化位置 | `init_dependencies()` | `get_deadline_store()` |
| 生命周期管理 | FastAPI lifespan | 模块级单例 |
| 测试支持 | 无特殊支持 | `set_deadline_store()` 替换单例 |

---

## 5. 实际运行场景演示

### 5.1 场景一：`task dev:server` 启动

```
初始条件：
  工作目录 = packages/cli/

执行步骤：
  1. 读取 Taskfile.yml → dir: "./packages/cli"
  2. 切换工作目录到 packages/cli/
  3. 运行 uv run agent-cli serve --port 8000
  
创建的文件：
  - packages/cli/output/sessions.db
  - packages/cli/output/deadlines.db
  - packages/cli/output/logs/agent.log

原因：
  - 配置中 db_path = "./output/sessions.db" 是相对路径
  - 当前工作目录是 packages/cli/
  - 所以相对路径解析到 packages/cli/output/
```

### 5.2 场景二：`bash scripts/check.sh` 运行测试

```
初始条件：
  工作目录 = /home/frosty/files/.../team-project-26spring-26s-5/

执行步骤：
  1. scripts/check.sh 调用 cd packages/core && pytest
  2. pytest 运行测试
  
创建的文件：
  - packages/core/output/sessions.db
  
原因：
  - pytest 使用 ":memory:" 数据库（临时）
  - 但 init_dependencies() 仍会读取配置
  - 如果配置中 db_path 没被覆盖，会创建实际文件
  - 最终位置取决于执行时的工作目录
```

### 5.3 场景三：`GET /deadlines` API 调用

```
调用链路：
  1. HTTP GET /deadlines
  2. routes/deadlines.py::list_deadlines()
  3. services/deadline_service.py::list_deadlines()
  4. deadline_provider.py::get_deadline_store()  ← 首次初始化在此
  5. DeadlineStore.list_all()
  
创建的数据库：
  - deadlines.db 在 Path(sessions.db).parent/ 中
  - 即 packages/cli/output/deadlines.db（如果从 CLI 启动）
```

---

## 6. 总结与最佳实践

### 6.1 核心要点

✅ **SessionStore** 和 **DeadlineStore** 都存储在同一目录中（`./output/`）
✅ 相对路径在不同工作目录下会产生不同的实际位置
✅ SessionStore 在应用启动时初始化（eager）
✅ DeadlineStore 在首次使用时初始化（lazy）
✅ 两个 `output` 目录共存是正常现象，取决于执行位置

### 6.2 避免混淆的方式

**方案 1：统一使用绝对路径**
```python
from pathlib import Path
db_dir = Path(__file__).parent.parent.parent / "output"
db_path = str(db_dir / "sessions.db")
```

**方案 2：使用环境变量**
```bash
export AGENT_DB_PATH="/data/agent_databases/sessions.db"
```

**方案 3：在 `.env` 文件中配置**
```ini
# .env
DB_PATH=./output/sessions.db
DEADLINE_DB_PATH=./output/deadlines.db
```

### 6.3 测试时的最佳实践

```python
# tests/test_deadline.py
import pytest
from agent_core.persistence.deadline_store import DeadlineStore
from agent_core.tools.deadline import set_deadline_store

@pytest.fixture
async def isolated_store():
    """为每个测试创建隔离的内存数据库"""
    store = DeadlineStore(":memory:")
    await store.initialize()
    await set_deadline_store(store)
    yield store
    await store.close()
    await set_deadline_store(None)
```

---

## 7. 文件结构总览

```
team-project-26spring-26s-5/
├── packages/
│   ├── core/
│   │   ├── output/
│   │   │   ├── logs/
│   │   │   │   └── agent.log
│   │   │   └── sessions.db          (pytest 创建)
│   │   └── src/
│   │       └── agent_core/
│   │           ├── config.py        (db_path = "./output/sessions.db")
│   │           ├── api/
│   │           │   ├── server.py    (FastAPI 应用工厂)
│   │           │   └── dependencies.py  (SessionStore 依赖注入)
│   │           └── persistence/
│   │               ├── session_store.py
│   │               ├── deadline_store.py
│   │               └── deadline_provider.py  (DeadlineStore 单例管理)
│   │
│   └── cli/
│       ├── output/
│       │   ├── logs/
│       │   ├── sessions.db          (task dev:server 创建)
│       │   └── deadlines.db         (首次调用 /deadlines)
│       └── src/
│           └── agent_cli/
│               └── main.py          (CLI 入口 + serve 命令)
│
├── Taskfile.yml                     (task dev:server 配置)
└── scripts/
    └── check.sh                     (pytest 启动脚本)
```

---

**文档完成于：2026-04-13**
**最后更新：A013 deadline management 完成后**
