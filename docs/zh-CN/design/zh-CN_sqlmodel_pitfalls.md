# SQLModel 与 SQLite 开发陷阱备忘录

本文档记录在本项目中使用 SQLModel + SQLAlchemy async + aiosqlite
开发过程中遇到的陷阱和解决方案，供后续开发者参考。

---

## 陷阱 1：`create_all()` 不会迁移已有表

### 问题

`SQLModel.metadata.create_all()` 只会 **创建不存在的表**。
如果表已存在于磁盘数据库中，即使 Python 模型定义已更改，
`create_all()` 也 **不会修改**已有表的 schema。

### 影响场景

Python 模型修改了列约束（如 `nullable=True`），但旧数据库
仍保留原始 schema（`NOT NULL DEFAULT ''`），导致：

```
sqlite3.IntegrityError: NOT NULL constraint failed: deadlines.start_date
```

### 解决方案

在 `DeadlineStore.initialize()` 中，`create_all()` 之后
执行 schema 检查与迁移：

```python
async def initialize(self) -> None:
    self._engine = create_async_engine(url, echo=False)
    async with self._engine.begin() as conn:
        await conn.run_sync(DeadlineRecord.metadata.create_all)
        # 迁移旧 schema 中 NOT NULL 的日期列
        await conn.run_sync(self._migrate_nullable_dates)
```

SQLite 不支持 `ALTER COLUMN`，需要通过重建表实现：
1. 创建临时表（新 schema）
2. 复制数据
3. 删除旧表
4. 重命名临时表

---

## 陷阱 2：`from __future__ import annotations` 与 SQLModel 字段解析

### 问题

使用 `from __future__ import annotations` 时，所有类型注解变为
字符串（延迟求值）。SQLModel 的字段元数据解析依赖运行时类型信息，
某些场景下可能影响 `nullable` 推断。

### 建议

- 始终在 `Field()` 中显式指定 `sa_type=...`
- 对需要 nullable 的列，确保 `default=None` + `sa_type` 搭配正确
- 写测试验证列属性：
  ```python
  col = DeadlineRecord.__table__.columns["start_date"]
  assert col.nullable is True
  ```

---

## 陷阱 3：`LenientDateTime` — 容错性 TypeDecorator

### 问题

SQLite 的 `DATETIME` 实际存储为 `TEXT`。历史数据可能包含空字符串
`''`、`'TBD'` 或其他非 ISO-8601 文本。SQLAlchemy 默认的
`DateTime` 类型在读取时调用 `datetime.fromisoformat()`，遇到
非法值直接崩溃。

### 解决方案

自定义 `LenientDateTime(sa.TypeDecorator)`:
- **写入（bind）**: `datetime` → ISO-8601 字符串；`None` → `NULL`
- **读取（result）**: 合法 ISO-8601 → `datetime`；空/非法 → `None`

### 注意事项

`LenientDateTime.process_bind_param()` 在 `value=None` 时
需要确保输出兼容数据库列的约束。如果旧 schema 有 `NOT NULL`，
返回 `None` 会导致 `IntegrityError`。因此需要配合 schema 迁移。

---

## 陷阱 4：StrEnum 与 ORM 加载后的类型丢失

### 问题

当 `DeadlineRecord` 的 `priority`、`source`、`date_type` 字段
使用 `sa_type=String()` 时，ORM 从数据库加载的值是 `str` 类型，
不是 `StrEnum` 成员。下游代码如果用 `isinstance()` 或 `is`
比较会失败。

### 解决方案

使用 SQLAlchemy 事件监听器，在 `load` 和 `refresh` 事件后
将字符串转回 StrEnum：

```python
@event.listens_for(DeadlineRecord, "load")
def _coerce_enums(target, context):
    if isinstance(target.priority, str):
        target.priority = DeadlinePriority(target.priority)
    ...
```

---

## 陷阱 5：前端空字符串 `""` 与 Pydantic `datetime` 验证

### 问题

前端在日期字段未填写时可能发送 `""` 而非 `null`。Pydantic 的
`datetime` 类型无法解析空字符串，导致 422 错误。

### 解决方案

在所有日期字段上添加 `field_validator(mode="before")`：

```python
@field_validator("due_date", "start_date", mode="before")
@classmethod
def coerce_empty_string_to_none(cls, v):
    if v == "":
        return None
    return v
```

需要在以下所有模型中应用：
- `CreateDeadlineRequest`（API 创建）
- `UpdateDeadlineRequest`（API 更新）
- `DeadlineRecordCreate`（同步/批量导入）

---

## 陷阱 6：内存数据库测试通过但磁盘数据库失败

### 问题

所有测试使用 `:memory:` 数据库，每次 `create_all()` 都创建全新
schema，因此 `nullable=True` 的列正常工作。但生产环境使用磁盘
数据库，表可能是用旧 schema 创建的，`create_all()` 不修改已有表。

### 教训

- 增加使用磁盘临时文件 + 旧 schema 的集成测试
- 在 `initialize()` 中加入 schema 检查/迁移逻辑
- 永远不要假设磁盘上的 schema 与当前模型一致

---

## 最佳实践总结

1. **Schema 变更必须配迁移逻辑**  — 不能只改模型，必须确保 `initialize()` 能处理旧 schema
2. **测试要覆盖旧 schema 场景** — 用 `tmp_path` + 手动建旧表的 fixture
3. **日期字段的 3 层防御**：
   - Controller: `field_validator` 转 `""` → `None`
   - Service: `sanitise_date_fields` 业务规则
   - Store: `LenientDateTime` 容错读写 + schema 迁移
4. **枚举字段必须加事件监听** — ORM 加载后立即转型
5. **显式声明 sa_type** — 不依赖 SQLModel 的自动推断
