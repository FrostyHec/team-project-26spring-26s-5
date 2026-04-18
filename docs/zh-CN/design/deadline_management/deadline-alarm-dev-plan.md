# Deadline Alarm — Development Plan

## 1. 功能概述与用户故事

### 1.1 用户故事

> As a student, I want to receive reminders before upcoming deadlines so that I can prepare and submit my work on time.

| US | 描述 | 触发条件 |
|----|------|---------|
| US-A1 | 在设置中配置提醒规则（提前时间、渠道、等级） | 用户打开设置 → DDL 提醒 分区 |
| US-A2 | 在规定时间前通过站内弹窗收到聚合提醒 | 触发时间到达，app 打开中 |
| US-A3 | 在规定时间前通过邮件收到聚合提醒 | 触发时间到达，邮件凭据已配置 |
| US-A4 | 应用重启时立即补发已错过的提醒（restart-safe） | 启动时 scheduler 检查 |
| US-A5 | 只有用户设置等级（高/中/低）的任务会触发提醒 | 优先级过滤 |

### 1.2 边界情况

| 情况 | 预期行为 |
|------|---------|
| 任务设置为"日精度"（moment_day/period_day），用户设置了小时级提醒（如 3h 前） | 对该任务忽略小时级提醒，日级提醒正常触发 |
| 用户设置了"提前 1 天"+"提前 3 小时"，任务距截止仅剩 2 小时 | 1 天提醒已发（或补发），3 小时提醒正常触发 |
| 提醒时间已过但未发（例如后台关闭期间） | 启动时立即补发 |
| 任务已标记完成 | 跳过，不触发提醒 |
| 邮件凭据未配置，用户启用了邮件渠道 | 跳过邮件发送，不报错；仅站内通知 |
| 同一时刻多个任务到期 | 聚合为一条通知："您有 N 个 DDL 即将到期" + 任务列表 |
| 任务在创建/导入时就已经过期（due_date < created_at） | 永远不提醒，即使后续手动修改也不提醒 |
| 用户将所有 lead_time 取消勾选（空列表） | 若提醒总开关仍为开启，则该配置无效并应提示用户至少保留一项；若希望不触发任何提醒，应关闭提醒总开关 |
| no_date 类型任务 | 无 due_date，永远跳过 |
## 2. 架构与调用链

### 2.1 整体架构

```
┌──────────────────────────────────────────────────────────┐
│                        Frontend (Vue3)                    │
│  Settings → DeadlineAlarmSettings.vue  (配置提醒规则)     │
│  App.vue → useNotificationPoller (每 30s 轮询)            │
│  DeadlineAlarmModal.vue (显示聚合弹窗)                    │
└────────┬───────────────────────────┬──────────────────────┘
         │  REST: PUT /alarm-settings  │  REST: GET /notifications/pending
         │  GET /alarm-settings        │  POST /notifications/{id}/ack
┌────────▼─────────────────────────────▼──────────────────┐
│               Controller Layer (FastAPI)                  │
│  api/routes/alarm_settings.py                            │
│  api/routes/notifications.py                             │
└────────┬─────────────────────────────┬───────────────────┘
         │                             │
┌────────▼─────────────────────────────▼───────────────────┐
│               Service Layer                               │
│  services/alarm_service.py  ← 触发逻辑、聚合、发送        │
│  services/alarm_scheduler.py ← 后台 asyncio Task          │
└────────┬──────────────────────────────────────────────────┘
         │
┌────────▼──────────────────────────────────────────────────┐
│               Persistence Layer                            │
│  persistence/alarm_store.py                               │
│    - alarm_settings 表 (KV 存储)                          │
│    - alarm_log 表 (已发提醒记录，防重复)                   │
│    - pending_notifications 表 (站内待消费通知)             │
│  存储在 sessions.db（与 profile 共享同一 DB）              │
└────────────────────────────────────────────────────────────┘
         │                    │
  DeadlineStore         EmailService
  (列出 DDL)            (发送邮件)
```

### 2.2 调用链 — 配置提醒规则

```
用户打开 Settings → DDL 提醒 分区
  → GET /alarm-settings
    → AlarmSettingsRoute → AlarmStore.get_settings()
    → 返回 AlarmSettings JSON
  → 用户修改配置 → 点击"保存"
  → PUT /alarm-settings { lead_times, channels, enabled_priorities }
    → AlarmSettingsRoute → AlarmStore.save_settings(settings)
    → 返回更新后 AlarmSettings
```

### 2.3 调用链 — 后台定时触发

```
应用启动
  → init_dependencies() → AlarmScheduler.start()
      → 立即调用 AlarmService.check_and_dispatch(now)
      → 每 60s 循环 AlarmService.check_and_dispatch(now)

AlarmService.check_and_dispatch(now):
  1. 读取 AlarmStore.get_settings() → AlarmSettings
  2. 读取 DeadlineStore.list_all() → 所有 DDL
  3. 过滤：completed=True / priority not in enabled_priorities / no_date → 跳过
  4. 对每个 DDL，对每个 lead_time：
     a. 若 lead_time 为小时级且 DDL 不是 moment_hm/period_hm → 跳过
     b. trigger_time = compute_trigger(ddl.due_date, lead_time)
     c. 若 now >= trigger_time:
        → AlarmStore.is_alarm_sent(ddl.id, lead_time) == False？
        → 收集 (ddl, lead_time) 到 pending_batch
  5. 若 pending_batch 非空:
     → 按渠道聚合发送:
       - IN_APP channel: AlarmStore.add_pending_notification(message)
       - EMAIL channel: EmailService.send_email(subject, body)
     → AlarmStore.mark_alarm_sent(ddl.id, lead_time) for each item
```

### 2.4 调用链 — 站内弹窗

```
前端 useNotificationPoller (每 30s):
  → GET /notifications/pending
    → NotificationsRoute → AlarmStore.get_pending_notifications()
    → 返回 [{id, message, details, created_at}]
  → 若非空:
    → 显示 DeadlineAlarmModal.vue（聚合消息）
    → 用户点击"知道了"
    → POST /notifications/{id}/ack for each id
      → AlarmStore.ack_notification(id)
```
## 3. 后端实现计划

### 3.1 数据模型 `models/alarm.py`（新建）

```python
class AlarmLeadTime(StrEnum):
    HOUR_1  = "hour_1"    # 1小时前（仅 moment_hm/period_hm）
    HOUR_3  = "hour_3"
    HOUR_6  = "hour_6"
    HOUR_12 = "hour_12"
    DAY_1   = "day_1"     # 1天前（所有日期类型）
    DAY_3   = "day_3"
    WEEK_1  = "week_1"

LEAD_TIME_DELTAS: dict[AlarmLeadTime, timedelta] = {
    AlarmLeadTime.HOUR_1:  timedelta(hours=1),
    AlarmLeadTime.HOUR_3:  timedelta(hours=3),
    ...
}

HOUR_BASED_LEAD_TIMES = {AlarmLeadTime.HOUR_1, AlarmLeadTime.HOUR_3,
                          AlarmLeadTime.HOUR_6, AlarmLeadTime.HOUR_12}

class AlarmChannel(StrEnum):
    IN_APP = "in_app"
    EMAIL  = "email"

class AlarmSettings(BaseModel):
    enabled: bool = True
    # enabled=True 时 lead_times 和 channels 各至少选 1 个（model_validator 强制）
    lead_times: list[AlarmLeadTime] = [AlarmLeadTime.DAY_1]
    channels: list[AlarmChannel] = [AlarmChannel.IN_APP]
    enabled_priorities: list[DeadlinePriority] = [
        DeadlinePriority.HIGH, DeadlinePriority.MEDIUM
    ]

    @model_validator(mode="after")
    def validate_enabled_requires_selections(self) -> "AlarmSettings":
        if self.enabled:
            if not self.lead_times:
                raise ValueError("At least one lead_time is required when alarm is enabled.")
            if not self.channels:
                raise ValueError("At least one channel is required when alarm is enabled.")
            if not self.enabled_priorities:
                raise ValueError("At least one priority is required when alarm is enabled.")
        return self
```

### 3.1b `models/deadline.py` 修改 — 增加 `created_at` 字段

**目的**：区分"创建时已过期的历史数据"（永远不提醒）与"创建时未过期的正常任务"。

```python
class DeadlineRecord(SQLModel, table=True):
    ...
    # 新增字段：记录任务创建时间
    # NULL = 旧数据（迁移前已存在），视为"不确定来源，不提醒"
    # 非 NULL = 新建记录，若 due_date <= created_at 则视为导入时已过期
    created_at: datetime | None = Field(default=None, sa_type=LenientDateTime())
```

**DB 迁移**：在 `DeadlineStore.initialize()` 中添加 ALTER TABLE（与现有 start_date 迁移模式一致）：
```sql
ALTER TABLE deadlines ADD COLUMN created_at TEXT;
```

**迁移后的旧数据填充**：在 `initialize()` 中，迁移完成后立即将所有 `created_at IS NULL` 的记录填充为 **迁移执行时的时间戳**：
```python
migration_now = datetime.now(UTC).isoformat()
await db.execute(
    "UPDATE deadlines SET created_at = ? WHERE created_at IS NULL",
    (migration_now,)
)
```
效果：
- 已过期的历史数据：`due_date < migration_now` → `due_date <= created_at` → 永远不提醒 ✅
- 未来有效任务：`due_date > migration_now` → 正常提醒 ✅

**创建新记录时**：`DeadlineService.create()` 和 `build_record_from_dict()` 需设置 `created_at = datetime.now(UTC)` （仅在字段为 None 时填充）。

**提醒过滤规则**（在 AlarmService 中）：
```python
# 迁移前已过期的历史任务 → 跳过（due_date <= created_at = migration_time）
# 创建/导入时就已过期 → 跳过（due_date <= created_at = import_time）
if ddl.created_at is not None and ddl.due_date <= ddl.created_at:
    continue
```

### 3.2 持久化层 `persistence/alarm_store.py`（新建）

**数据库表（共享 sessions.db）：**

```sql
-- 设置（KV 存储，JSON 序列化整个 AlarmSettings）
CREATE TABLE IF NOT EXISTS alarm_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

-- 已发送提醒日志（防重复）
CREATE TABLE IF NOT EXISTS alarm_log (
    deadline_id TEXT NOT NULL,
    lead_time   TEXT NOT NULL,
    sent_at     TEXT NOT NULL,
    PRIMARY KEY (deadline_id, lead_time)
);

-- 站内待消费通知
CREATE TABLE IF NOT EXISTS pending_notifications (
    id         TEXT PRIMARY KEY,
    message    TEXT NOT NULL,
    details    TEXT NOT NULL DEFAULT '[]',   -- JSON list of deadline titles
    created_at TEXT NOT NULL
);
```

**方法：**
- `get_settings() → AlarmSettings`
- `save_settings(settings: AlarmSettings) → None`
- `is_alarm_sent(deadline_id: str, lead_time: AlarmLeadTime) → bool`
- `mark_alarm_sent(deadline_id: str, lead_time: AlarmLeadTime) → None`
- `add_pending_notification(message: str, details: list[str]) → str`（返回 id）
- `get_pending_notifications() → list[PendingNotification]`
- `ack_notification(notification_id: str) → None`
- `cleanup_old_logs(cutoff: datetime) → None`（可选，定期清理过期日志）

### 3.3 服务层 `services/alarm_service.py`（新建）

**核心方法：**

```python
def compute_trigger_time(due_date: datetime, lead_time: AlarmLeadTime,
                         date_type: DateType) -> datetime | None:
    """计算触发时间。小时级 lead_time 对日精度任务返回 None。"""
    if lead_time in HOUR_BASED_LEAD_TIMES:
        if date_type not in (DateType.MOMENT_HM, DateType.PERIOD_HM):
            return None
    return due_date - LEAD_TIME_DELTAS[lead_time]

async def check_and_dispatch(now: datetime) -> None:
    """检查所有 DDL，对触发时间已到且未发送的 alarm 批量派发。

    聚合策略：
      - 收集所有 (ddl, lead_time) 对，其中 trigger_time <= now 且尚未发送
      - 按 deadline_id 去重，得到本次需要通知的唯一任务集合
      - 对每个启用的 channel，发送**一条**聚合通知（所有任务合并）
      - 再逐条记录 alarm_log(deadline_id, lead_time) 防重

    举例：
      用户设置 [3h, 1d]，应用重启时距某任务 DDL 剩余 2h（均已触发未发）：
        → pending = [(task, HOUR_3), (task, DAY_1)]
        → unique_ddls = {task}  （去重后 1 个任务）
        → 发送 1 条通知："您有 1 个任务即将到期"
        → alarm_log 记录两条：(task.id, HOUR_3) + (task.id, DAY_1)
    """
    settings = await self._alarm_store.get_settings()
    if not settings.enabled:
        return
    deadlines = await self._deadline_store.list_all()

    # Step 1: 收集需要发送的 (ddl, lead_time) 对
    pending: list[tuple[DeadlineRecord, AlarmLeadTime]] = []
    for ddl in deadlines:
        if ddl.completed or ddl.due_date is None:
            continue
        if ddl.priority not in settings.enabled_priorities:
            continue
        # 创建时已过期或来源不明（旧数据） → 永远不提醒
        if ddl.created_at is None or ddl.due_date <= ddl.created_at:
            continue
        for lead_time in settings.lead_times:
            trigger = compute_trigger_time(ddl.due_date, lead_time, ddl.date_type)
            if trigger is None:
                continue
            if now >= trigger:
                already_sent = await self._alarm_store.is_alarm_sent(ddl.id, lead_time)
                if not already_sent:
                    pending.append((ddl, lead_time))

    if not pending:
        return

    # Step 2: 按 deadline_id 去重 → 唯一任务集合（用于通知内容）
    unique_ddls: dict[str, DeadlineRecord] = {ddl.id: ddl for ddl, _ in pending}

    # Step 3: 每个启用的 channel 发送一条聚合通知
    for channel in settings.channels:
        await self._dispatch(list(unique_ddls.values()), channel, now)

    # Step 4: 逐条记录已发（防重复），按实际 (ddl_id, lead_time) 记录
    for ddl, lead_time in pending:
        await self._alarm_store.mark_alarm_sent(ddl.id, lead_time)
```

### 3.4 调度器 `services/alarm_scheduler.py`（新建）

```python
class AlarmScheduler:
    """后台 asyncio Task，负责定时触发 AlarmService.check_and_dispatch。
    
    - 启动时立即执行一次（处理重启期间错过的提醒）
    - 之后每 POLL_INTERVAL_SECONDS 执行一次
    """
    POLL_INTERVAL_SECONDS = 60

    async def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
```

### 3.5 API 路由

**`api/routes/alarm_settings.py`（新建）：**
- `GET  /alarm-settings` → `AlarmSettings`
- `PUT  /alarm-settings` (body: `AlarmSettings`) → `AlarmSettings`
  - **特殊行为**：若本次请求将 `enabled` 从 False → True，则在保存设置后，
    立即调用 `AlarmService.check_and_dispatch(now)` 一次（恢复效果）
  - 若 `enabled=True` 但 `lead_times=[]` 或 `channels=[]`，Pydantic 校验失败 → 422

**`api/routes/notifications.py`（新建）：**
- `GET  /notifications/pending` → `list[PendingNotification]`
- `POST /notifications/{notification_id}/ack` → `{"status": "ok"}`

### 3.6 依赖注入 `api/dependencies.py` 修改

在 `init_dependencies()` 中：
1. 初始化 `AlarmStore` (同 sessions.db)
2. 初始化 `AlarmService` (注入 DeadlineStore + AlarmStore + EmailService)
3. 启动 `AlarmScheduler`

在 `shutdown_dependencies()` 中：
4. 停止 `AlarmScheduler`
5. 关闭 `AlarmStore`

### 3.7 邮件模板（聚合）

邮件主题：`[DDL 提醒] 您有 {N} 个任务即将到期`
邮件正文（纯文本）：
```
您有以下 {N} 个任务即将到期：

- {title} ({course}) — 截止：{due_date}  [提前 {lead_time_label} 提醒]
...

请及时完成。
```
## 4. 前端实现计划

### 4.1 新文件清单

| 文件 | 说明 |
|------|------|
| `src/api/alarm.ts` | API 客户端（alarm-settings + notifications） |
| `src/stores/alarm.ts` | Pinia store（settings + pending notifications） |
| `src/stores/alarmConstants.ts` | 常量（lead time labels, channel keys） |
| `src/components/settings/DeadlineAlarmSettings.vue` | 设置面板组件 |
| `src/components/DeadlineAlarmModal.vue` | 站内弹窗提醒组件 |
| `src/composables/useNotificationPoller.ts` | 30s 轮询逻辑 |

### 4.2 设置常量 `alarmConstants.ts`

```typescript
export const ALARM_LEAD_TIMES = {
  HOUR_1:  'hour_1',
  HOUR_3:  'hour_3',
  HOUR_6:  'hour_6',
  HOUR_12: 'hour_12',
  DAY_1:   'day_1',
  DAY_3:   'day_3',
  WEEK_1:  'week_1',
} as const

export const ALARM_CHANNELS = {
  IN_APP: 'in_app',
  EMAIL:  'email',
} as const
```

### 4.3 Settings 集成

在 `settingsConstants.ts` 增加 `DEADLINE_MANAGEMENT: 'deadline_management'` 分区（section 名称为"DDL 管理"）。
在 `SETTINGS_SECTION_LIST` 末尾追加。

`DeadlineAlarmSettings.vue` 包含：
- **主开关**：`[ 开关 ] 开启 DDL 提醒`
  - 关闭时：下方所有设置变灰（`disabled` 属性），后端 `enabled=false`，不触发任何提醒
  - 开启时：下方设置可交互；保存时触发后端立即执行一次 check_and_dispatch
- **提前时间（多选复选框）**（开关关闭时灰显）：
  - `[ ] 提前 1 小时` (仅对时分精度有效，带灰色说明)
  - `[ ] 提前 3 小时`
  - `[ ] 提前 6 小时`
  - `[ ] 提前 12 小时`
  - `[x] 提前 1 天`（默认勾选）
  - `[ ] 提前 3 天`
  - `[ ] 提前 1 周`
- **提醒渠道（多选）**（开关关闭时灰显）：
  - `[x] 站内弹窗`（默认勾选）
  - `[ ] 邮件提醒（需配置邮箱）`
- **提醒等级（多选）**（开关关闭时灰显）：`[x] 高` `[x] 中` `[ ] 低`
- **保存按钮**（同其他设置分区样式）：
  - 若 `enabled=true` 且 `lead_times.length==0` 或 `channels.length==0` 或 `enabled_priorities.length==0` → 按钮禁用，显示提示"请至少选择一个提醒时间、渠道和任务等级"

### 4.4 通知轮询 `useNotificationPoller.ts`

```typescript
export function useNotificationPoller() {
  const alarmStore = useAlarmStore()
  let timer: ReturnType<typeof setInterval> | null = null

  function start() {
    poll()   // 立即执行一次
    timer = setInterval(poll, 30_000)
  }

  async function poll() {
    await alarmStore.fetchPendingNotifications()
  }

  function stop() { if (timer) clearInterval(timer) }

  return { start, stop }
}
```

在 `App.vue` 的 `onMounted` 中调用 `start()`，`onUnmounted` 中调用 `stop()`。

### 4.5 DeadlineAlarmModal.vue

- 当 `alarmStore.pendingNotifications.length > 0` 时显示
- 内容：聚合标题（"您有 N 个 DDL 即将到期"）+ 任务列表详情
- "知道了" 按钮 → `alarmStore.ackAll()`

### 4.6 i18n 新增 Key（`zh.json` / `en.json`）

```json
"deadlineAlarm": {
  "title": "DDL 提醒",
  "description": "设置截止日期提醒规则。",
  "enabled": "启用 DDL 提醒",
  "leadTimes": "提前提醒时间（可多选）",
  "hourOnlyHint": "小时级提醒仅对"时分精度"任务生效",
  "channels": "提醒渠道",
  "enabledPriorities": "提醒的任务等级",
  "hour1": "提前 1 小时",
  "hour3": "提前 3 小时",
  "hour6": "提前 6 小时",
  "hour12": "提前 12 小时",
  "day1": "提前 1 天",
  "day3": "提前 3 天",
  "week1": "提前 1 周",
  "inApp": "站内弹窗",
  "emailChannel": "邮件提醒",
  "emailRequiresConfig": "（需先配置邮箱凭据）",
  "settingsSaved": "DDL 提醒设置已保存",
  "notificationTitle": "DDL 即将到期提醒",
  "notificationBody": "您有 {n} 个任务即将到期：",
  "dismiss": "知道了"
}
```
## 5. 技术安全 Checklist

| 类别 | 检查项 | 本功能是否涉及 | 方案 |
|------|--------|--------------|------|
| 输入验证 | `lead_times` / `channels` / `enabled_priorities` 用户输入 | ✅ | Pydantic enum 自动校验，非法值 422 |
| SQL 注入 | alarm_log / pending_notifications 写入 | ✅ | aiosqlite 参数化查询 |
| 邮件内容 | DDL 标题含特殊字符注入邮件头 | ✅ | 仅写入邮件正文，不插入 Header 字段 |
| 异步安全 | EmailService.send_email 在 asyncio 中调用同步 SMTP | ✅ | EmailClient 已使用 `asyncio.to_thread` |
| 重启安全 | AlarmLog 必须持久化 | ✅ | 写入 SQLite，不用内存 |
| 调度任务泄漏 | AlarmScheduler Task 在 shutdown 时必须 cancel | ✅ | `shutdown_dependencies` 调用 `scheduler.stop()` |
| i18n 字符 | 邮件内容中若含 `@`/`{` | ✅ | Python 格式字符串，不经 vue-i18n |

## 6. 实现顺序

```
Phase 1: Backend Foundation
  Step 1: models/alarm.py (AlarmLeadTime, AlarmChannel, AlarmSettings)
  Step 2: persistence/alarm_store.py (3 tables + CRUD methods)
  Step 3: services/alarm_service.py (compute_trigger_time + check_and_dispatch)
  Step 4: services/alarm_scheduler.py (asyncio background task)
  Step 5: api/routes/alarm_settings.py + api/routes/notifications.py
  Step 6: api/dependencies.py 集成（init + shutdown）
  Step 7: api/server.py 注册路由

Phase 2: Frontend
  Step 8:  src/api/alarm.ts
  Step 9:  src/stores/alarmConstants.ts + src/stores/alarm.ts
  Step 10: src/components/settings/DeadlineAlarmSettings.vue
  Step 11: settingsConstants.ts 增加 DEADLINE_ALARM 分区
  Step 12: SettingsSidebar.vue + SettingsPanel.vue 集成新分区
  Step 13: src/components/DeadlineAlarmModal.vue
  Step 14: src/composables/useNotificationPoller.ts
  Step 15: App.vue 挂载 poller + modal
  Step 16: i18n (zh.json + en.json)

Phase 3: Tests + Docs
  Step 17: tests/test_alarm_service.py
  Step 18: tests/test_alarm_store.py
  Step 19: tests/test_alarm_api.py
  Step 20: 更新 docs/zh-CN/user-guide/zh-CN_deadline_management.md
  Step 21: 更新 CHANGELOG.md
```
## 7. 待确认设计决策

1. **数据库位置**：AlarmStore 表与 sessions.db 共享（复用已有 `ProfileStore` 模式），还是单独 `alarm.db`？ → 初步方案：共享 sessions.db
2. **轮询间隔**：
   - 后端 scheduler: 60s（可满足分钟级精度）
   - 前端 polling: 30s（足够快速呈现）
3. **"已过期"任务的补发策略**：如果 due_date 已过，且 alarm 从未发送 → 仍然发送（提醒已过期），消息措辞为"已到期"
4. **period_* 类型任务**：使用 `due_date`（即结束日期）作为提醒基准，不对 `start_date` 触发提醒
5. **InApp 通知持久化**：pending_notifications 写入 SQLite，确保重启后未消费的通知不丢失
---
*Development Plan 不包含 Test Plan — 请参考 `deadline-alarm-test-plan.md`*
