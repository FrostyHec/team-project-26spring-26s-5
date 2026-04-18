# Deadline Alarm — Test Plan

## 1. 测试矩阵

### 1.1 单元测试 — `test_alarm_service.py`

| # | 测试场景 | 输入 | 预期结果 |
|---|---------|------|---------|
| S1 | moment_hm 任务 + 3h lead_time，now = trigger_time | due_date=T+3h，lead_time=HOUR_3，now=T | trigger 计算 = T，should_send = True |
| S2 | moment_day 任务 + 3h lead_time（小时级跳过） | date_type=moment_day，lead_time=HOUR_3 | compute_trigger_time 返回 None |
| S3 | moment_day 任务 + DAY_1 lead_time | date_type=moment_day，due=明天 00:00，now=今天 00:00 | trigger=今天00:00，now>=trigger → should_send=True |
| S4 | 已标记完成的任务跳过 | completed=True | 不入 batch |
| S5 | 等级未启用的任务跳过 | priority=LOW，enabled_priorities=[HIGH,MEDIUM] | 不入 batch |
| S6 | 已发过该 lead_time 的任务不重复发送 | alarm_log 有记录 | skip |
| S7 | 多个不同任务同时触发 → 聚合为一条 in-app 通知 | 3个DDL均触发，channel=IN_APP | 1次 add_pending_notification，details 长度=3，消息="您有3个任务即将到期" |
| S8 | 同一任务两个 lead_time 同时触发（补发场景）→ 聚合为一条 | task 剩余 2h，设置 [3h,1d]，now > T-3h，alarm_log 无记录 | 1条通知（"您有1个任务"），alarm_log 写入2条：(id,HOUR_3) + (id,DAY_1) |
| S9 | 重启补发：多个任务的不同 lead_time 均过期未发 | 2个task，各有2个lead_time过期，共4条 pending | 1条聚合通知（2个任务），4条 alarm_log 记录 |
| S10 | 已完全过期但未发 → 发送过期提醒 | now > due_date，created_at < due_date，无log | 发送，消息注明"已过期" |
| S11 | AlarmSettings.enabled=False | enabled=False | check_and_dispatch 立即返回，不发送 |
| S12 | no_date 任务跳过 | date_type=NO_DATE, due_date=None | 跳过 |
| S13 | period_hm 任务使用 due_date（结束时间）触发 | period_hm，due_date=T+1h，start_date=T | 只用 due_date 计算 trigger |
| S14 | **创建/导入时已过期** → 永远不提醒 | created_at=T，due_date=T-1d（导入时已过期） | 跳过，不触发任何提醒 |
| S15 | **旧数据迁移后** due_date 在迁移前已过期 → 不提醒 | 迁移时设 created_at=T_migration，due_date < T_migration | 跳过 |
| S16 | **旧数据迁移后** due_date 在迁移后还未到 → 正常提醒 | 迁移时设 created_at=T_migration，due_date = T_migration+3d | 正常触发 |
| S17 | **lead_times 为空 + enabled=True** → AlarmSettings 校验失败 | lead_times=[] | Pydantic ValueError / API 422 |
| S18 | **channels 为空 + enabled=True** → 同上 | channels=[] | Pydantic ValueError / API 422 |
| S19 | **enabled_priorities 为空 + enabled=True** → 同上 | enabled_priorities=[] | Pydantic ValueError / API 422 |
| S20 | **enabled=False** → 后端不发送任何提醒 | enabled=False | check_and_dispatch 立即返回 |
| S21 | **PUT enabled: False→True** → 立即触发 check_and_dispatch | 有 2 个符合条件的 DDL | mock check_and_dispatch 被调用一次，发送通知 |

### 1.2 单元测试 — `test_alarm_store.py`

| # | 测试场景 | 预期结果 |
|---|---------|---------|
| A1 | 默认 settings：get_settings() 返回默认值 | enabled=True, lead_times=[DAY_1], channels=[IN_APP] |
| A2 | save_settings + get_settings 往返 | 存取一致 |
| A3 | is_alarm_sent：首次 False，mark_alarm_sent 后 True | 正确 |
| A4 | add_pending_notification + get_pending_notifications | 返回正确条目 |
| A5 | ack_notification：ack 后 get_pending_notifications 不含该 id | 正确 |
| A6 | :memory: DB 测试隔离（无磁盘遗留） | 无副作用 |

### 1.3 API 集成测试 — `test_alarm_api.py`

| # | 端点 | 测试场景 | 预期 |
|---|------|---------|------|
| API1 | GET /alarm-settings | 初始状态 | 200 + 默认 AlarmSettings JSON |
| API2 | PUT /alarm-settings | 更新 lead_times=["hour_3","day_1"] | 200 + 返回更新后设置 |
| API3 | PUT /alarm-settings | 非法 lead_time 值 | 422 Unprocessable Entity |
| API4 | GET /notifications/pending | 无通知 | 200 + [] |
| API5 | GET /notifications/pending | 有2条通知 | 200 + list len=2 |
| API6 | POST /notifications/{id}/ack | 有效 id | 200 + {"status":"ok"} |
| API7 | POST /notifications/{id}/ack | 不存在 id | 404 |

### 1.4 前端单元测试 — `stores/__tests__/alarm.spec.ts`

| # | 场景 | 预期 |
|---|------|------|
| F1 | fetchAlarmSettings 调用 getAlarmSettings API 并更新 store | settings.enabled = true |
| F2 | saveAlarmSettings 调用 updateAlarmSettings | isSaving 变化，settings 更新 |
| F3 | fetchPendingNotifications 有通知 → showModal = true | modal 可见 |
| F4 | ackAll 调用 ack API → pendingNotifications 清空，showModal = false | 正确 |

### 1.5 安全测试

| # | 攻击向量 | 测试方法 | 预期 |
|---|---------|---------|------|
| SEC1 | PUT /alarm-settings 注入非法 lead_time 字符串 `"'; DROP TABLE alarm_log;--"` | 发送恶意 payload | 422，AlarmLog 表完整 |
| SEC2 | PUT /alarm-settings channels 超大数组（DoS） | 100个重复值 | Pydantic 截断或422 |
| SEC3 | 邮件正文中 DDL 标题含 SMTP 头注入字符（\r\n） | title="evil\r\nBcc: attacker" | 邮件仅写入 body，不影响 Header |

### 1.6 Scheduler 集成测试（`test_alarm_scheduler.py`）

| # | 场景 | 预期 |
|---|------|------|
| SCH1 | 启动时立即触发一次 check_and_dispatch | mock AlarmService.check_and_dispatch 被调用一次 |
| SCH2 | stop() 取消 asyncio Task，不 raise | Task 正常 cancel |
## 2. 外部服务 Mock 策略

### 2.1 EmailService（已有 Mock 模式）

邮件发送测试使用 `unittest.mock.AsyncMock` 替代真实 `EmailService.send_email`：
- 验证调用次数（聚合后仅1次）
- 验证 subject / body 包含预期任务标题
- 无需真实 SMTP 凭据

### 2.2 DeadlineStore / AlarmStore（内存 SQLite）

所有持久化测试使用 `:memory:` SQLite — 无磁盘遗留，无跨测试污染。

### 2.3 时间 Mock

使用 `unittest.mock.patch('agent_core.services.alarm_service.datetime')` 控制 `now`，
确保时间敏感测试可重现。
## 3. CI 集成

- 新测试文件加入 `packages/core/tests/`，`scripts/check.sh` 自动覆盖
- 前端测试加入 `packages/gui/src/stores/__tests__/alarm.spec.ts`，vitest 自动覆盖
- 无需真实邮件凭据或外部服务

---
*Test Plan 独立于 Development Plan，仅在测试阶段查阅。*
