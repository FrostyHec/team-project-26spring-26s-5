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
│  REST Client        ◄── GET/PATCH/POST/DELETE         │
└──────────────┬───────────────────────┬───────────────┘
               │  Chat SSE            │  REST
┌──────────────▼───────────────────────▼───────────────┐
│             Controller Layer (FastAPI)                 │
│  deadlines_router (Pydantic DTOs: datetime|None)      │
│  tools/deadline.py (7 tools)                          │
└──────────────┬───────────────────────┬───────────────┘
               │                      │
┌──────────────▼──────────────────────▼────────────────┐
│              Service Layer                            │
│  DeadlineService: business logic, date range          │
│  validation, sanitisation, build_record_from_dict     │
└──────────────────────────┬───────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────┐
│              Store Layer (SQLModel async ORM)          │
│  DeadlineStore: CRUD via SQLModel + aiosqlite         │
│  DeadlineRecord(SQLModel, table=True)                 │
└──────────────────────────────────────────────────────┘
```

---

## 3. Data Model

### 3.1 Enum Definitions

File: `models/deadline.py`

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

class DateType(StrEnum):
    NO_DATE = "no_date"
    MOMENT_DAY = "moment_day"
    MOMENT_HM = "moment_hm"
    PERIOD_DAY = "period_day"
    PERIOD_HM = "period_hm"
```

- `StrEnum` ensures serialised values are lowercase strings
- Eliminates all magic strings

### 3.2 DeadlineRecord (SQLModel table)

```python
class DeadlineRecord(SQLModel, table=True):
    __tablename__ = "deadlines"
    id: str = Field(default="", primary_key=True)
    title: str
    course: str = Field(default="")
    due_date: datetime | None = Field(default=None)
    priority: DeadlinePriority = Field(default=DeadlinePriority.MEDIUM)
    source: DeadlineSource = Field(default=DeadlineSource.MANUAL)
    description: str = Field(default="")
    date_type: DateType = Field(default=DateType.MOMENT_DAY)
    start_date: datetime | None = Field(default=None)
    completed: bool = Field(default=False)
```

- **SQLModel table=True**: serves as both ORM table and Pydantic schema
- **`datetime | None`** for date/time fields: supports both day precision (MOMENT_DAY/PERIOD_DAY, time=00:00) and hour:minute precision (MOMENT_HM/PERIOD_HM)
- `date_type` acts as a *type discriminator* — determines how to interpret the stored `datetime` value
- `id` is auto-generated (UUID4) by the Store layer if empty

### 3.3 DeadlineRecordCreate (non-table DTO)

```python
class DeadlineRecordCreate(SQLModel):
    title: str
    course: str = ""
    due_date: datetime | None = None
    ...
```

- Used for API request bodies where `id` is not needed
- Non-table SQLModel ensures proper Pydantic validation when nested

### 3.4 parse_datetime_field helper

```python
def parse_datetime_field(value: str | date | datetime | None) -> datetime | None
```

- Converts string / date / datetime / None to `datetime | None`
- Empty string and None map to None
- ISO-8601 date string `"YYYY-MM-DD"` → `datetime` at midnight
- ISO-8601 datetime string `"YYYY-MM-DDTHH:MM"` → `datetime` with time
- `date` object → `datetime` at midnight

> **Backward compatibility**: `parse_date_field` is kept as a thin wrapper
> that calls `parse_datetime_field` and returns `date | None` (day precision only).

---

## 4. Three-Layer Architecture

### 4.1 Layer Responsibilities

| Layer | File | Responsibility |
|-------|------|----------------|
| **Controller** (Routes/Tools) | `api/routes/deadlines.py`, `tools/deadline.py` | Format validation via Pydantic typed DTOs |
| **Service** | `services/deadline_service.py` | Business logic, date range validation, sanitisation |
| **Store** | `persistence/deadline_store.py` | Pure data executor, SQLModel async ORM |

### 4.2 DeadlineStore (Store Layer)

File: `persistence/deadline_store.py`

Uses **SQLModel + SQLAlchemy async engine** (no hand-written SQL):

| Method | Description |
|--------|-------------|
| `initialize()` | Create async engine, ensure schema exists |
| `add(record)` | Insert record, auto-generate UUID if id is empty |
| `list_all(course?, priority?)` | Filtered query, ordered by `due_date ASC` (nulls last) |
| `get(id)` | Get single record by ID |
| `delete(id)` | Delete by ID, return success boolean |
| `find_duplicate(title, due_date)` | Check for existing record with same title+date |
| `toggle_completed(id, completed)` | Toggle completion status |
| `update(id, fields)` | Partial update with whitelisted fields |
| `close()` | Dispose engine and release connections |

### 4.3 DeadlineService (Service Layer)

File: `services/deadline_service.py`

Business logic layer between Controller and Store:

| Method | Description |
|--------|-------------|
| `create(title, due_date, ...)` | Validate + build record + persist |
| `create_from_dict(data)` | Parse loose dict (from LLM) into record |
| `update(id, fields)` | Typed field update with date range validation |
| `update_from_tool(id, ...)` | String-based update from LLM tools |
| `delete(id)` | Delete with not-found check |
| `list_deadlines(course?, priority?)` | Delegate to store |
| `get_deadline(id)` | Get with not-found check |
| `toggle_completed(id, flag)` | Toggle with not-found check |
| `sync_preview(candidates)` | Preview new vs duplicate detection |
| `sync_commit(tasks)` | Batch persist confirmed tasks |
| `save_batch(items)` | Parse + persist loose dicts |

### 4.4 Provider (Singleton)

File: `persistence/deadline_provider.py`

```python
async def get_deadline_store() -> DeadlineStore:
    ...
async def set_deadline_store(store: DeadlineStore | None) -> None:
    ...
```

- Module-level singleton with lazy initialisation
- `set_deadline_store()` for test dependency injection

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

### 7.1 Endpoints

File: `api/routes/deadlines.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/deadlines` | List all deadlines |
| `GET` | `/api/deadlines?course=CS302` | Filter by course |
| `GET` | `/api/deadlines?priority=high` | Filter by priority |
| `POST` | `/api/deadlines` | Create a new deadline |
| `PATCH` | `/api/deadlines/{id}` | Partial update |
| `DELETE` | `/api/deadlines/{id}` | Delete deadline |
| `PATCH` | `/api/deadlines/{id}/complete` | Toggle completed |
| `POST` | `/api/deadlines/sync-preview` | Preview new vs duplicates |
| `POST` | `/api/deadlines/sync-commit` | Persist confirmed tasks |

### 7.2 Request/Response DTOs

```python
class CreateDeadlineRequest(BaseModel):
    title: str
    course: str = ""
    due_date: datetime | None = None     # Pydantic validates ISO format
    priority: DeadlinePriority = DeadlinePriority.MEDIUM
    ...

class UpdateDeadlineRequest(BaseModel):
    title: str | None = None
    due_date: datetime | None = None     # Only set fields are updated
    ...

class DeadlineListResponse(BaseModel):
    deadlines: list[DeadlineRecord]
```

- Request DTOs use `datetime | None` for automatic format validation (422 for bad dates)
- Accepts both `"YYYY-MM-DD"` (→ midnight) and `"YYYY-MM-DDTHH:MM"` (→ datetime with time)
- `SyncPreviewRequest` / `SyncCommitRequest` use `DeadlineRecordCreate` (non-table DTO) to ensure proper datetime coercion

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

## 10. Code Quality

- **No magic strings**: all values use `DeadlinePriority` / `DeadlineSource` / `DateType` enums
- **SQLModel ORM**: `DeadlineRecord(SQLModel, table=True)` replaces raw SQL, serves as both DB table and Pydantic schema
- **Typed datetime**: `datetime | None` fields with `date_type` discriminator for day/HM precision (no hand-written regex)
- **Layered validation**: Controller (format) + Service (business) + Store (executor)
- **Auto-discovery**: `register_deadline_tools` found by `auto_discover_and_register`
- **Test coverage**: 88 unit + 67 service + 33 API tests = 188 deadline tests
- **Pipeline green**: `check.sh --check-only` passes
