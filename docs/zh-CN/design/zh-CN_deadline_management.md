# Deadline Management 功能设计文档

本文档描述 Deadline Management (DDL 管理) 功能的设计方案，涵盖数据模型、
持久化、工具函数、技能提示词、REST API 和前端展示。

---

## 1. 需求概述

### 1.1 用户故事

| US   | 描述                                         | 状态     |
|------|----------------------------------------------|----------|
| US1  | 跨平台数据收集 — 从 Blackboard、Email、TAS 抓取并提取 DDL，HITL 确认后存储 | ✅ 已实现 |
| US2  | 统一看板 — CalendarWidget 展示所有 DDL，支持按课程/紧急度过滤        | ✅ 已实现 |
| US3  | 自然语言添加 — 用户口述 DDL，LLM 提取结构化数据并存储              | ✅ 已实现 |
| US4  | 考前提醒 — 定时任务 + WebSocket 推送（需独立基础设施）             | 🔜 延期  |

### 1.2 范围决策

- 外部工具（Blackboard、Email、TAS）当前返回 **mock 数据**
- US4 需要后台调度器 + WebSocket，为独立基础设施工作，暂不纳入
- DDL 存储使用独立 SQLite 实例（`DeadlineStore`），遵循现有 Session Store 模式
- 所有新代码均使用自动发现机制（tools + skills），无需手动注册

---

## 2. 架构总览

```
┌──────────────────────────────────────────────────────┐
│                      Frontend                         │
│  CalendarWidget.vue ◄── show_deadline_dashboard()     │
│  REST Client        ◄── GET/DELETE /api/deadlines     │
└──────────────┬───────────────────────┬───────────────┘
               │  Chat SSE            │  REST
┌──────────────▼───────────────────────▼───────────────┐
│                   FastAPI Server                      │
│  chat_router  │  deadlines_router  │  tools_router    │
└──────┬────────┴────────┬───────────┴────────┬────────┘
       │                 │                    │
┌──────▼─────┐  ┌────────▼──────┐  ┌─────────▼────────┐
│  LangGraph │  │ DeadlineStore │  │  ToolRegistry    │
│  Agent     │  │ (SQLite)      │  │  (auto-discover) │
└──────┬─────┘  └───────────────┘  └──────────────────┘
       │
┌──────▼──────────────────────────────────────────────┐
│              tools/deadline.py (7 tools)             │
│  get_announcements | query_email | get_exams         │
│  save_deadlines (HITL) | list_deadlines              │
│  add_deadline | show_deadline_dashboard               │
└─────────────────────────────────────────────────────┘
```

---

## 3. 数据模型

### 3.1 枚举定义

文件：`models/deadline.py`

```python
class DeadlinePriority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class DeadlineSource(StrEnum):
    BLACKBOARD = "blackboard"
    EMAIL = "email"
    TAS = "tas"
    MANUAL = "manual"
```

- 使用 `StrEnum` 确保序列化值为小写字符串，与 JSON/SQLite 交互一致
- 完全消除 magic string

### 3.2 DeadlineRecord

```python
class DeadlineRecord(BaseModel):
    id: str = ""
    title: str
    course: str
    due_date: str          # ISO-8601 格式 YYYY-MM-DD
    priority: DeadlinePriority = DeadlinePriority.MEDIUM
    source: DeadlineSource = DeadlineSource.MANUAL
    description: str = ""
```

- 默认 `priority=MEDIUM`、`source=MANUAL` 降低创建门槛
- `id` 在持久化层自动生成（UUID4）

---

## 4. 持久化层

### 4.1 DeadlineStore

文件：`persistence/deadline_store.py`

| 方法            | 描述                                    |
|-----------------|-----------------------------------------|
| `initialize()`  | 创建 `deadlines` 表（IF NOT EXISTS）      |
| `add(record)`   | 插入一条 DDL，自动生成 ID               |
| `list_all(course?, priority?)` | 带过滤的查询，按 `due_date ASC` 排序 |
| `get(id)`       | 按 ID 查询单条                          |
| `delete(id)`    | 按 ID 删除，返回是否成功                 |
| `close()`       | 关闭数据库连接                          |

### 4.2 模块级单例

`tools/deadline.py` 使用模块级 `_store` 变量实现懒初始化：

```python
_store: DeadlineStore | None = None

async def _get_store() -> DeadlineStore:
    global _store
    if _store is None:
        _store = DeadlineStore(":memory:")
        await _store.initialize()
    return _store
```

- 提供 `set_deadline_store()` 用于测试依赖注入
- 默认使用 `:memory:` 数据库（可配置为文件路径）

---

## 5. 工具函数

### 5.1 数据采集工具（Mock）

| 工具                 | 敏感度 | 描述                           |
|----------------------|--------|--------------------------------|
| `get_announcements`  | SAFE   | 返回 Blackboard 公告的 JSON 数组 |
| `query_email`        | SAFE   | 按天数查询邮件，返回 JSON 数组   |
| `get_exams`          | SAFE   | 返回 TAS 考试安排的 JSON 数组    |

每个工具返回 3 条左右的 mock 数据，包含课程名、标题、日期等字段，
为 LLM 提供真实的数据提取场景。

### 5.2 DDL 管理工具

| 工具                       | 敏感度     | 描述                                    |
|---------------------------|-----------|----------------------------------------|
| `save_deadlines`          | SENSITIVE | 批量保存 DDL（触发 HITL 确认流程）         |
| `list_deadlines`          | SAFE      | 按课程/优先级过滤查询                     |
| `add_deadline`            | SAFE      | 单条添加 DDL（自然语言场景）              |
| `show_deadline_dashboard` | SAFE      | 返回 CalendarWidgetData 触发前端展示       |

### 5.3 注册机制

```python
def register_deadline_tools(registry: ToolRegistry) -> None:
    for func, desc, sensitivity in _TOOL_DESCRIPTIONS:
        registry.add_tool(func, description=desc, sensitivity=sensitivity)
```

- 使用 `_TOOL_DESCRIPTIONS` 列表集中管理工具元数据
- 遵循 `register_*_tools` 命名约定，被 `auto_discover_and_register()` 自动发现

---

## 6. 技能提示词

文件：`skills/deadline_manager.py`

系统提示词划分为 4 个工作流指导：

1. **Sync Deadlines** — 调用 3 个采集工具 → LLM 提取 → `save_deadlines`（HITL）
2. **Add Single Deadline** — 从自然语言提取 → `add_deadline`
3. **Show Dashboard** — `show_deadline_dashboard` → CalendarWidget
4. **Filter & Query** — `list_deadlines(course?, priority?)`

关键规则：
- 日期统一使用 ISO-8601 格式
- 默认优先级为 `medium`
- 保存后主动提供展示看板选项

---

## 7. REST API

### 7.1 端点

文件：`api/routes/deadlines.py`

| 方法     | 路径                        | 描述               |
|----------|-----------------------------|--------------------|
| `GET`    | `/api/deadlines`            | 列出所有 DDL        |
| `GET`    | `/api/deadlines?course=CS302` | 按课程过滤          |
| `GET`    | `/api/deadlines?priority=high` | 按优先级过滤       |
| `DELETE` | `/api/deadlines/{id}`       | 删除指定 DDL        |

### 7.2 响应模型

```python
class DeadlineListResponse(BaseModel):
    deadlines: list[DeadlineRecord]
```

---

## 8. 前端展示

### 8.1 CalendarWidget

现有 `CalendarWidget.vue` 已具备展示 DDL 所需的全部字段：

| 字段       | 展示方式                              |
|-----------|---------------------------------------|
| `title`   | 事件标题（粗体文本）                    |
| `date`    | 日期（Calendar 图标 + 日期文本）        |
| `priority` | 彩色圆点（red=high, yellow=medium, green=low）|
| `course`  | 蓝色圆角标签                          |
| `time`    | 时间（Clock 图标，可选）                |

高优先级事件额外显示 `AlertCircle` 警告图标。

### 8.2 数据流

```
show_deadline_dashboard()
  → DeadlineStore.list_all()
  → 构建 CalendarWidgetData(events=[...])
  → model_dump_json()
  → 前端渲染 CalendarWidget
```

---

## 9. 测试覆盖

### 9.1 单元测试 (`tests/test_deadline.py`)

| 测试类                      | 测试数 | 覆盖范围                              |
|----------------------------|--------|---------------------------------------|
| `TestDeadlineModels`       | 4      | 枚举值、序列化、默认值                  |
| `TestDeadlineStore`        | 8      | 增删查改、过滤、排序、不存在记录         |
| `TestMockDataTools`        | 3      | 3 个采集工具返回有效 JSON               |
| `TestDeadlineTools`        | 9      | 保存、列表、过滤、添加、看板             |
| `TestRegisterDeadlineTools`| 3      | 注册数量、敏感度、安全标记               |

### 9.2 API 集成测试 (`tests/test_deadline_api.py`)

| 测试方法                    | 覆盖范围                              |
|----------------------------|---------------------------------------|
| `test_list_empty`          | 空列表返回                            |
| `test_list_with_data`      | 带数据返回                            |
| `test_list_filter_course`  | 按课程过滤                            |
| `test_list_filter_priority`| 按优先级过滤                          |
| `test_delete_existing`     | 删除存在的记录                        |
| `test_delete_nonexistent`  | 删除不存在的记录返回 404               |

### 9.3 自动发现测试

`test_auto_discover.py` 中的 `test_discovers_deadline_tools` 验证 7 个工具
被正确发现和注册。

### 9.4 E2E 测试

手动启动服务器并验证：
- `GET /api/deadlines` — 返回空列表 ✅
- `GET /tools` — 包含 7 个 deadline 工具 ✅
- `GET /skills` — 包含 `deadline_manager` 技能 ✅
- `GET /health` — 服务健康检查 ✅

---

## 10. 代码质量保障

- **无 magic string**: 所有状态值使用 `DeadlinePriority` / `DeadlineSource` 枚举
- **Pydantic 建模**: `DeadlineRecord` 提供类型安全和自动序列化
- **KISS 原则**: 模块级单例 + 懒初始化，避免过度工程
- **自动发现**: 无需手动注册，`register_deadline_tools` 被 `auto_discover_and_register` 自动发现
- **测试完整**: 27+ 单元测试 + 6 API 测试 + E2E 验证
- **Pipeline 绿灯**: `check.sh` 全部通过（181 Python + 59 Vue）
