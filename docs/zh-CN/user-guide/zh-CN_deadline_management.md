# Deadline Management 用户指南

本文档介绍如何通过前端界面和 LLM 对话管理学术 Deadline（DDL）。

---

## 1. 功能概览

Deadline Management 支持以下操作：

| 功能           | 前端界面              | LLM 对话               |
|----------------|-----------------------|------------------------|
| 查看所有 DDL   | 面板自动加载          | `list_deadlines`       |
| 新增 DDL       | 表单创建              | `add_deadline` / 自然语言 |
| 删除 DDL       | 点击删除按钮          | `delete_deadline`      |
| 标记完成/未完成 | 勾选 checkbox         | —                      |
| 编辑 DDL       | 点击编辑后保存        | `update_deadline`      |
| 同步外部数据   | 同步面板预览 → 确认    | `save_deadlines`（批量）|
| 日历看板       | 日历 Widget           | `show_deadline_dashboard` |

---

## 2. 日期类型（DateType）

每个 DDL 都有一个 `date_type` 字段，决定了日期的展示方式：

| date_type     | 含义             | 举例                                 |
|---------------|------------------|--------------------------------------|
| `no_date`     | 无日期（待定）    | 只有标题，没有截止时间                |
| `moment_day`  | 某一天截止        | 2026-04-15                           |
| `moment_hm`   | 某一天某时刻截止  | 2026-04-15T14:30                     |
| `period_day`  | 跨天周期任务      | 2026-04-01 ~ 2026-04-15             |
| `period_hm`   | 精确到小时的周期  | 2026-04-15T09:00 ~ 2026-04-15T11:30 |

### 日期字段说明

- **`due_date`**：截止日期（所有非 `no_date` 类型必填）
- **`start_date`**：起始日期（仅 `period_day` / `period_hm` 使用）
- 如果 `due_date` 为空，系统自动将 `date_type` 降级为 `no_date`
- 如果 `start_date` 晚于 `due_date`，系统清除 `start_date` 并产生警告

---

## 3. 通过前端界面操作

### 3.1 查看 DDL 列表

打开前端面板后，系统自动调用 `GET /api/deadlines` 加载所有 DDL。

#### 筛选功能

工具栏包含两个筛选控件，均可与「Hide done」开关同时生效：

| 控件 | 位置 | 行为 |
|------|------|------|
| 课程下拉（Course） | 工具栏左侧，紧随视图 Tab 后 | 「All courses」= 不过滤；选择课程名后，仅显示该课程的 DDL |
| 优先级下拉（Priority） | 课程下拉右侧 | 「All」= 不过滤；可选 High / Medium / Low |

**筛选逻辑**：
- 筛选在**前端本地**执行，无需重新请求 API，切换即时生效
- 课程下拉的选项由当前已加载 DDL 的 `course` 字段动态生成（去重 + 排序）
- 两个筛选条件**同时叠加**：同时选择 `CS302` 和 `High`，只显示高优先级的 CS302 任务
- 如果筛选结果为空，各子视图显示空状态提示

**典型操作流程**：
1. 打开 DeadlinePanelWidget
2. 在 Course 下拉选择 `CS302`
3. 在 Priority 下拉选择 `High`
4. 列表立即只显示 High 优先级的 CS302 DDL
5. 将 Course 下拉重置为 `All courses` → 恢复显示所有 High 优先级 DDL

#### 边界情况

| 情况 | 预期行为 |
|------|---------|
| 某课程下无任何 DDL | 筛选后显示空状态提示 |
| DDL 的 `course` 字段为空 | 不出现在课程下拉选项中；"All courses" 时仍会显示 |
| 与「Hide done」同时使用 | 两个条件均生效（AND 逻辑） |
| 加载失败 | 筛选控件仍渲染，但数据列表为空 |

### 3.2 创建新 DDL

点击「新增」按钮打开创建表单，填写以下字段：

| 字段          | 必填 | 类型               | 说明                         |
|---------------|------|--------------------|------------------------------|
| `title`       | ✅   | 文本               | DDL 标题                     |
| `course`      |      | 文本               | 课程名称（如 CS302）         |
| `due_date`    |      | ISO-8601 日期/时间  | 截止日期                     |
| `start_date`  |      | ISO-8601 日期/时间  | 起始日期（仅周期任务）       |
| `priority`    |      | `high/medium/low`  | 优先级，默认 `medium`        |
| `date_type`   |      | 见上方枚举          | 日期类型，默认 `moment_day`  |
| `description` |      | 文本               | 备注说明                     |

**日期格式要求**：
- 日期：`2026-04-15`（YYYY-MM-DD）
- 日期时间：`2026-04-15T14:30`（YYYY-MM-DDTHH:MM）
- 不需要设置日期时，**留空即可**（空字符串 `""` 会被自动处理为空值）

**请求示例**：
```json
{
  "title": "操作系统期中考试",
  "course": "CS302",
  "due_date": "2026-04-15T14:00",
  "priority": "high",
  "date_type": "moment_hm",
  "start_date": "",
  "description": "教3-102"
}
```

### 3.3 编辑 DDL

点击 DDL 进入编辑模式，修改需要更新的字段后保存。

- 只有实际修改的字段会被发送到后端（PATCH 语义）
- 清空日期字段时发送 `""` 即可

### 3.4 标记完成

勾选 DDL 前的 checkbox 即可标记完成/未完成。

### 3.5 删除 DDL

点击删除按钮，确认后删除。

### 3.6 同步外部数据

1. 点击「同步」按钮
2. 系统调用 `POST /deadlines/sync-preview` 预览新增/重复条目
3. 用户确认后，调用 `POST /deadlines/sync-commit` 写入数据库

---

## 4. 通过 LLM 对话操作

### 4.1 自然语言添加

直接对 Agent 说自然语言，Agent 会自动提取结构化信息并调用
`add_deadline` 工具：

> "帮我添加一个 CS302 的作业，4 月 15 号截止"

Agent 会提取 `title`、`course`、`due_date` 并自动创建。

### 4.2 批量导入

Agent 可以从 Blackboard 公告、Email、TAS 系统获取候选 DDL，
经 HITL（Human-in-the-loop）确认后批量存储：

1. Agent 调用 `get_announcements` / `query_email` / `get_exams` 获取数据
2. Agent 整理并展示候选列表
3. 用户确认后 Agent 调用 `save_deadlines` 批量写入

### 4.3 查询

> "我有哪些高优先级的作业？"

Agent 调用 `list_deadlines(priority="high")`。

### 4.4 修改和删除

> "把 CS302 作业的截止日期改到 4 月 20 号"
> "删掉已经完成的 MATH201 作业"

Agent 自动调用 `update_deadline` 或 `delete_deadline`。

---

## 5. 优先级（Priority）

| 值       | 含义                 |
|----------|----------------------|
| `high`   | 高优先级（紧急任务） |
| `medium` | 中优先级（默认值）   |
| `low`    | 低优先级             |

---

## 6. 数据来源（Source）

| 值           | 含义                     |
|--------------|--------------------------|
| `blackboard` | 从 Blackboard 系统同步   |
| `email`      | 从邮件中提取             |
| `tas`        | 从 TAS 系统同步          |
| `manual`     | 用户手动创建（默认值）   |

---

## 7. 常见问题

### Q: 日期不填会怎样？

系统会自动将 `date_type` 设为 `no_date`。DDL 仍会保存，
但在日历视图中显示在「待安排」区域。

### Q: 前端发送空字符串 `""` 作为日期值会报错吗？

不会。系统会自动将 `""` 转换为空值（`None`），正常处理。

### Q: start_date 晚于 due_date 会怎样？

- **API 创建/更新**（强验证）：返回 422 错误
- **LLM 工具**（宽松模式）：自动清除 `start_date` 并在响应中包含警告

### Q: 日期格式错误会怎样？

- **API 路由**：Pydantic 自动校验格式，非 ISO-8601 返回 422
- **LLM 工具**：将无法解析的日期设为空，产生警告，不中断操作
