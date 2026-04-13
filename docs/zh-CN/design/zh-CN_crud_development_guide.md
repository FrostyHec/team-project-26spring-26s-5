# CRUD 开发指南

本文档定义了 ReAct Agent 项目后端使用 SQLModel 进行 CRUD 开发的标准模式，以及 Controller–Service–Store 三层架构下的数据校验和传输规范。

## 技术栈

| 组件 | 版本 | 用途 |
|------|------|------|
| [SQLModel](https://sqlmodel.tiangolo.com/) | 0.0.38+ | ORM 模型 + Pydantic schema |
| SQLAlchemy (async) | 2.0+ | 底层异步引擎 |
| aiosqlite | — | SQLite 异步驱动 |
| Pydantic v2 | 2.0+ | 请求/响应 DTO、自动格式校验 |

## 三层架构概览

```
User / LLM
  │
  ├── REST API (Controller) ── Pydantic DTO → 自动 422
  ├── Tool Function ────────── 字符串 → 强类型转换
  │
  ▼
Service 层（业务逻辑唯一归属）
  │  ✓ 日期范围校验、状态机、权限
  │  ✓ date_type 自动降级
  │  ✓ 构建 DeadlineRecord
  ▼
Store 层（纯执行者）
  │  ✓ SQLModel async ORM
  │  ✗ 不做格式校验
  ▼
SQLite (aiosqlite)
```

**关键原则：数据到达 Store 层时，必须已经是强类型对象（`datetime`、`Enum`），Store 绝不接收原始字符串。**

## 模型定义

### Table Model（ORM 持久化模型）

```python
from datetime import datetime
from enum import StrEnum
from sqlmodel import Field, SQLModel


class DeadlinePriority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DeadlineRecord(SQLModel, table=True):
    """ORM table model — 同时也是 Pydantic response schema。"""
    __tablename__ = "deadlines"

    id: str = Field(default="", primary_key=True)
    title: str
    course: str = Field(default="")
    due_date: datetime | None = Field(default=None)
    priority: DeadlinePriority = Field(default=DeadlinePriority.MEDIUM)
    completed: bool = Field(default=False)
```

### Create DTO（非 table 模型）

当 Table Model 嵌套在 Pydantic `BaseModel` 的请求体中时，SQLAlchemy 内部元数据会导致类型转换异常。因此请求体中使用**非 table DTO**：

```python
class DeadlineRecordCreate(SQLModel):
    """不带 table=True——用于 API 请求体嵌套。"""
    title: str
    course: str = ""
    due_date: datetime | None = None
    priority: DeadlinePriority = DeadlinePriority.MEDIUM
```

在路由层将 DTO 转换为 Table Model：

```python
records = [
    DeadlineRecord.model_validate(dto.model_dump())
    for dto in body.deadlines  # list[DeadlineRecordCreate]
]
```

## Store 层模式

### 初始化

```python
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession


class DeadlineStore:
    def __init__(self, db_path: str = "deadlines.db") -> None:
        self._engine = None

    async def initialize(self) -> None:
        url = f"sqlite+aiosqlite:///{self.db_path}"
        self._engine = create_async_engine(url, echo=False)
        async with self._engine.begin() as conn:
            await conn.run_sync(DeadlineRecord.metadata.create_all)

    def _session(self) -> AsyncSession:
        return AsyncSession(self._engine)
```

### Create

```python
async def add(self, record: DeadlineRecord) -> DeadlineRecord:
    if not record.id:
        record.id = str(uuid.uuid4())  # 直接赋值，不用 model_copy
    async with self._session() as session:
        session.add(record)
        await session.commit()
        await session.refresh(record)
    return record
```

> **注意**：SQLAlchemy 追踪实例身份，`model_copy()` 创建的新对象会脱离 Session 导致 `refresh` 失败。应直接修改属性。

### Read

```python
from sqlmodel import col, select

async def list_all(self, course: str | None = None) -> list[DeadlineRecord]:
    statement = select(DeadlineRecord)
    if course:
        statement = statement.where(
            func.lower(DeadlineRecord.course) == course.lower()
        )
    statement = statement.order_by(
        col(DeadlineRecord.due_date).is_(None),  # NULL last
        col(DeadlineRecord.due_date).asc(),
    )
    async with self._session() as session:
        results = await session.exec(statement)
        return list(results.all())
```

### Update

```python
async def update(self, deadline_id: str, fields: dict[str, object]) -> DeadlineRecord | None:
    async with self._session() as session:
        record = await session.get(DeadlineRecord, deadline_id)
        if record is None:
            return None
        for key, value in fields.items():
            setattr(record, key, value)
        session.add(record)
        await session.commit()
        await session.refresh(record)
    return record
```

### Delete

```python
async def delete(self, deadline_id: str) -> bool:
    async with self._session() as session:
        record = await session.get(DeadlineRecord, deadline_id)
        if record is None:
            return False
        await session.delete(record)
        await session.commit()
    return True
```

## Service 层模式

Service 是**唯一的业务逻辑层**。REST Controller 和 Tool 函数都委托给同一个 Service 实例。

### 类型化入口（API 调用）

```python
async def create(
    self,
    *,
    title: str,
    due_date: datetime | None = None,
    priority: DeadlinePriority = DeadlinePriority.MEDIUM,
) -> tuple[DeadlineRecord, list[str]]:
    # 业务校验（Service 职责）
    _validate_date_range(start_date, due_date)
    # 构建强类型 Record
    record = DeadlineRecord(id=str(uuid.uuid4()), title=title, ...)
    saved = await self._store.add(record)
    return saved, warnings
```

### 字典入口（Tool / LLM 调用）

```python
async def create_from_dict(self, data: dict[str, Any]) -> tuple[DeadlineRecord, list[str]]:
    record, warnings = build_record_from_dict(data)
    saved = await self._store.add(record)
    return saved, warnings
```

`build_record_from_dict` 负责：
1. 枚举解析（`str → Enum`），无效值用安全默认
2. 日期解析（`str → datetime | None`），无效值产生 warning
3. 业务矫正（`sanitise_date_fields`）

## Controller / DTO 层

### Pydantic 自动格式校验

```python
class CreateDeadlineRequest(BaseModel):
    title: str
    due_date: datetime | None = None       # 自动 422 如果格式不对
    priority: DeadlinePriority = ...      # 自动 422 如果不在枚举范围
```

非法输入直接返回 HTTP 422，不进入 Service 层。

### enum 查询参数手动解析

对于 `GET` query parameter（字符串），需手动转换：

```python
@router.get("")
async def list_deadlines(priority: str | None = None):
    normalized: DeadlinePriority | None = None
    if priority is not None:
        try:
            normalized = DeadlinePriority(priority.strip().lower())
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid priority")
    ...
```

## JSON 序列化

`datetime` 对象默认不可 JSON 序列化。使用 `model_dump(mode="json")` 确保 `datetime → "YYYY-MM-DDTHH:MM:SS"`、`None → null`：

```python
# ✅ 正确
result = record.model_dump(mode="json")

# ❌ 错误——datetime 对象无法 json.dumps
result = record.model_dump()
json.dumps(result)  # TypeError: Object of type datetime is not JSON serializable
```

## 常见陷阱

| 陷阱 | 原因 | 解决方案 |
|------|------|---------|
| `model_copy()` 后 `session.refresh()` 失败 | SQLAlchemy 追踪实例身份，copy 出的对象脱离 Session | 直接修改属性：`record.id = str(uuid.uuid4())` |
| Table model 嵌套在 BaseModel 时字符串不转 date | SQLAlchemy 元数据干扰 Pydantic 类型强制 | 请求体用非 table DTO（`DeadlineRecordCreate`），在路由层转换 |
| `model_dump()` 中 `datetime` 对象不可 JSON 序列化 | `json.dumps` 不识别 `datetime` | 使用 `model_dump(mode="json")` |
| Store 层做格式校验 | 违反分层职责 | 格式校验放在 Controller/DTO（Pydantic） |
| 层间传递 `dict` | 丢失类型安全 | 始终传递 `DeadlineRecord` 等强类型对象 |
| Magic string 散落 | 硬编码维护困难 | 使用 `StrEnum` + 常量 |

## 检查清单

新增 CRUD 功能时，请逐项确认：

- [ ] Table Model 使用 `SQLModel, table=True`
- [ ] 日期/时间字段类型为 `datetime | None`（不是 `str`；`date_type` 决定精度）
- [ ] 状态字符串使用 `StrEnum`
- [ ] Store 层无手写 SQL、无格式校验
- [ ] Service 层包含所有业务逻辑
- [ ] Controller DTO 使用 Pydantic 类型自动校验
- [ ] 层间传递强类型对象（非 dict）
- [ ] `model_dump(mode="json")` 用于 JSON 序列化
- [ ] 请求体嵌套使用非 table DTO
- [ ] 测试覆盖 Store / Service / API 各层
