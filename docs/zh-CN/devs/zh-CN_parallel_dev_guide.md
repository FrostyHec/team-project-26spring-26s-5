# 五大功能并行开发指南

本文档为 ReAct Agent 项目五大核心功能的**并行开发指南**。  
五个功能分别由五名开发者独立开发、独立提交，最终合并至主线。  
本指南旨在帮助每位开发者明确自己的开发范围、文件归属以及协作规范，确保并行开发过程中**零冲突或极低冲突**。

## 目录

1. [架构全景](#1-架构全景)
2. [五大功能开发范围](#2-五大功能开发范围)
3. [自动发现机制](#3-自动发现机制)
4. [标准开发流程](#4-标准开发流程)
5. [各功能详细开发指南](#5-各功能详细开发指南)
6. [Merge 策略与 CI 守护](#6-merge-策略与-ci-守护)
7. [注意事项与约定](#7-注意事项与约定)

---

## 1. 架构全景

### 1.1 Monorepo 结构

项目采用 monorepo 管理，共四个子包：

```
packages/
  core/          # Python — 后端引擎 + API + tools + models
  gui/           # TypeScript/Vue — 前端 SPA
  cli/           # Python — 命令行入口
  poc_frontend/  # Python — Chainlit 原型前端（保留但不活跃）
```

### 1.2 Core 后端模块

```
agent_core/
  api/
    routes/
      chat.py              # /chat, /chat/stream 路由
      health.py            # /health 路由
      sessions.py          # /sessions CRUD 路由
      skills.py            # /skills 列表路由
      tools.py             # /tools 列表路由
    dependencies.py        # DI：创建 agent，自动发现并注册所有 tools
    server.py              # FastAPI app factory
    approval.py            # HITL 审批机制
  engine/
    agent.py               # ReAct agent 主循环 + stream()
    state.py               # AgentState TypedDict
  models/
    __init__.py            # 公共导出（基类 + 枚举）
    events.py              # EventType, WidgetType, WidgetData 基类, Event models
    session.py             # MessageRole, MessageRecord, SessionRecord
    skills.py              # SkillType StrEnum, SkillDefinition model
  persistence/
    session_store.py       # SQLite session/message 存储
    converters.py          # LangChain ↔ MessageRecord 转换
  skills/
    __init__.py            # 自动发现 + registry 函数
    general.py             # General 通用技能
    deadline_manager.py    # F1 Deadline Management
    course_assistant.py    # F2 Course Assistant
    policy_search.py       # F3 Campus Policy Search
    course_recommend.py    # F4 Course Recommendation
    campus_news.py         # F5 Campus News Push
  tools/
    __init__.py            # auto_discover_and_register() 自动发现
    registry.py            # ToolRegistry + ToolDefinition
    calculator.py          # POC 计算器 tools
    weather.py             # POC 天气 tools (HITL demo)
    widgets.py             # Widget tools + WidgetData subclasses
  config.py                # AgentConfig
  logging_utils.py         # 日志配置
```

### 1.3 GUI 前端模块

```
gui/src/
  api/
    agent.ts               # API client
  stores/
    chat.ts                # Pinia store：session + message + stream handler
    chatConstants.ts       # EVENT_TYPES, WIDGET_TYPES, MESSAGE_ROLES 常量
    chatTypes.ts           # TypeScript interfaces
  components/
    ChatPanel.vue          # 聊天面板壳
    SessionSidebar.vue     # 会话列表侧栏
    WorkspacePanel.vue     # 右侧 widget 面板（使用 widgets/index.ts 注册表）
    chat/
      ChatHeader.vue
      ChatInputBox.vue
      ChatMessageBubble.vue
      ChatMessageList.vue
      ChatToolBadges.vue
      ChatTraceBlock.vue
      ChatApprovalBanner.vue
    widgets/
      index.ts             # Widget 组件注册表（append-only 映射）
      CalendarWidget.vue
      CourseCardsWidget.vue
      DocumentWidget.vue
      EmptyWidget.vue
      SourcesWidget.vue
      WebPreviewWidget.vue
  views/
    ChatView.vue           # 三栏布局壳
  router/
    index.ts               # 路由配置
```

### 1.4 关键设计概念

| 概念 | 说明 |
|------|------|
| **Skill** | 技能 / 人设 — 每个 skill 是一个 `system_prompt`，切换 skill 改变 agent 行为。不影响 tool 注册。 |
| **Tool** | 工具 — LangChain StructuredTool。agent 在推理时决定是否调用。每个 tool 模块提供 `register_*_tools(registry)` 函数。 |
| **WidgetData** | 前端组件数据载荷 — tool 返回的 JSON 被 agent 检测为 `WidgetData` 子类时，自动转发为 `WidgetDisplayEvent` 到前端。 |
| **WidgetType** | 前端组件类型 — `StrEnum`，前后端同步维护。值如 `calendar`, `document`, `sources` 等。 |
| **自动发现** | tools 和 skills 均通过 `pkgutil.iter_modules` 扫描自动注册，无需修改公共文件。 |

---

## 2. 五大功能开发范围

### 2.1 总览

每个功能的开发涉及 **四个层面**：

| 层面 | 说明 |
|------|------|
| **Backend Tools** | Python 工具函数 — 外部数据获取、处理、格式化 |
| **Backend Skill / Prompt** | 该功能对应的 system prompt 调优 |
| **Backend WidgetData** | 该功能的 widget 数据模型（如需新增） |
| **Frontend Widget** | Vue 组件 — 渲染该功能的 widget 内容 |

### 2.2 各功能范围矩阵

| Feature | 需要的 Tools | 复用/新增 Widget | 需要新增 WidgetData |
|---------|-------------|-----------------|-------------------|
| **F1: Deadline Management** | `fetch_deadlines`, `add_reminder`, `filter_deadlines` 等 | CalendarWidget（已有，可增强） | 无（复用 `CalendarWidgetData`） |
| **F2: Course Assistant** | `parse_slides`, `generate_notes`, `generate_quiz` 等 | DocumentWidget（已有，可增强） | 无（复用 `DocumentWidgetData`） |
| **F3: Campus Policy Search** | `search_policy`, `explain_policy` 等 | SourcesWidget + WebPreviewWidget（已有） | 无（复用现有） |
| **F4: Course Recommendation** | `search_courses`, `compare_courses`, `recommend` 等 | CourseCardsWidget（已有，可增强） | 无（复用 `CourseCardsWidgetData`） |
| **F5: Campus News Push** | `fetch_news`, `summarize_news`, `push_digest` 等 | **新增 NewsDigestWidget** | 新增 `NewsDigestWidgetData` |

> **注意**: `WidgetType.NEWS_DIGEST` 及对应的前端常量 `WIDGET_TYPES.NEWS_DIGEST` 已在框架准备 PR 中预留，F5 开发者可直接使用。

---

## 3. 自动发现机制

项目采用 **声明式自动发现** 替代集中式注册，使得每个功能自包含在独立文件中，**无需修改公共注册文件**。

### 3.1 Tool 自动发现

**位置**: `agent_core/tools/__init__.py` → `auto_discover_and_register()`

**原理**: 使用 `pkgutil.iter_modules` 扫描 `agent_core.tools` 包下所有模块，自动调用任何名称匹配 `register_*_tools()` 的函数。

**开发者要做的**:

1. 在 `packages/core/src/agent_core/tools/` 下创建新文件（如 `deadline.py`）
2. 在文件中定义工具函数
3. 提供 `register_<feature>_tools(registry: ToolRegistry)` 函数

```python
# agent_core/tools/deadline.py
from agent_core.tools.registry import ToolRegistry

def fetch_deadlines(course: str) -> str:
    """Fetch upcoming deadlines for a course."""
    # ... implementation
    return result

def register_deadline_tools(registry: ToolRegistry) -> None:
    registry.add_tool(func=fetch_deadlines, description="...")
```

**效果**: 无需修改 `dependencies.py` 或任何公共文件。新文件自动被发现并注册。

### 3.2 Skill 自动发现

**位置**: `agent_core/skills/__init__.py` → `_auto_discover_skills()`

**原理**: 扫描 `agent_core.skills` 包下所有模块，寻找模块级 `SKILL` 常量（类型为 `SkillDefinition`）。

**开发者要做的**:

1. 编辑 `packages/core/src/agent_core/skills/<feature>.py`（已存在）
2. 调整 `SKILL = SkillDefinition(...)` 中的 `system_prompt`

```python
# agent_core/skills/deadline_manager.py
from agent_core.models.skills import SkillDefinition, SkillType

SKILL = SkillDefinition(
    id=SkillType.DEADLINE_MANAGER,
    name="Deadline Manager",
    description="Track and manage academic deadlines and reminders.",
    system_prompt="...",    # ← 调优此处
    icon="Calendar",
    color="text-red-500",
)
```

**效果**: 无需修改 `skills/__init__.py`。新 skill 文件自动被发现。

### 3.3 WidgetData 动态联合

**位置**: `agent_core/engine/agent.py` → `_build_widget_adapter()`

**原理**: 在 `stream()` 方法中，通过 `WidgetData.__subclasses__()` 动态收集所有已导入的子类，构建 Pydantic `TypeAdapter`。当 tool 返回的 JSON 能够被解析为某个 `WidgetData` 子类时，自动生成 `WidgetDisplayEvent`。

**开发者要做的**:

1. 在自己的 tools 文件中定义 `WidgetData` 子类
2. 使用 `Literal[WidgetType.XXX]` 作为 discriminator

```python
# agent_core/tools/news.py
from typing import Any, Literal
from agent_core.models.events import WidgetData, WidgetType

class NewsDigestWidgetData(WidgetData):
    widget_type: Literal[WidgetType.NEWS_DIGEST] = WidgetType.NEWS_DIGEST
    articles: list[dict[str, Any]] = []
```

**效果**: 无需修改 `agent.py`、`events.py` 或 `widgets.py`。子类自动加入动态联合。

### 3.4 前端 Widget 注册表

**位置**: `gui/src/components/widgets/index.ts`

**原理**: `WIDGET_COMPONENTS` 和 `WIDGET_TITLES` 是静态映射表，使用 `defineAsyncComponent` 懒加载组件。`WorkspacePanel.vue` 通过注册表渲染组件，本身无需修改。

**开发者要做的**（仅在新增 widget 组件时）:

1. 在 `widgets/` 目录下创建新 `.vue` 组件
2. 在 `widgets/index.ts` 中追加一行映射

```typescript
// widgets/index.ts — 追加
[WIDGET_TYPES.NEWS_DIGEST]: defineAsyncComponent(() => import('./NewsDigestWidget.vue')),
```

**效果**: `WorkspacePanel.vue` **无需修改**。每个开发者只需追加映射行。

---

## 4. 标准开发流程

每个功能的开发遵循以下 **五步流程**：

### Step 1: 同步主线

```bash
git checkout develop
git pull origin develop
git checkout -b feature/f<N>-<feature-name>
```

确保分支基于最新的 `develop`，包含框架准备 PR 的所有改动。

### Step 2: 设计并实现后端 Tools

检查当前 tools 是否已有可复用的 API/工具：

- 如果**已有可复用工具** → 直接在 prompt 中引用
- 如果**需要新工具** → 在 `tools/<feature>.py` 中实现

**要点**:
- 每个 tool 函数签名清晰、参数有 docstring
- 复杂的外部 API 调用可以先 **mock 返回**，后续迭代替换
- tool 返回值如需触发 widget 展示，返回 `WidgetData` 子类的 `model_dump_json()`
- 提供 `register_<feature>_tools(registry)` 函数

### Step 3: 设计并调优 Skill Prompt

编辑 `skills/<feature>.py` 中的 `system_prompt`：

- 明确该 skill 的角色和行为边界
- 列出可用的 tool 名称，指导 agent 何时调用
- 本地测试 prompt 效果：

```bash
# 启动本地 API 服务
cd packages/core && uv run uvicorn agent_core.api.server:create_app --factory --reload

# 测试 stream API
curl -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "...", "skill_id": "<feature>"}'
```

### Step 4: 开发前端 Widget（如需要）

- 如果复用已有 widget → 增强现有 `.vue` 组件即可
- 如果需要新 widget → 创建 `.vue` 组件 + 在 `widgets/index.ts` 追加映射
- 确保组件接收 `data` prop 并正确渲染

### Step 5: 编写测试并验证

1. **单元测试**: `packages/core/tests/test_<feature>.py`
   - 工具函数测试
   - WidgetData 序列化 / 反序列化测试
   - Skill 定义验证
2. **集成验证**: 运行完整检查

```bash
bash scripts/check.sh
```

确保 ruff + prettier 格式化、lint、language check、pytest、vitest、vue-tsc、vite build 全部通过。

---

## 5. 各功能详细开发指南

### 5.1 F1: Deadline Management

**负责人**: Dev-A

**功能描述**: 帮助学生追踪作业截止日期、考试安排、项目交付时间，提供提醒和优先级排序。

**需要创建的文件（独占）**:

| 文件 | 说明 |
|------|------|
| `core/src/agent_core/tools/deadline.py` | deadline tools + `register_deadline_tools()` |
| `core/tests/test_deadline.py` | 单元测试 |
| `gui/src/components/widgets/CalendarWidget.vue` | 增强日历组件（**独占**） |

**需要编辑的已有文件（独占）**:

| 文件 | 说明 |
|------|------|
| `core/src/agent_core/skills/deadline_manager.py` | 调优 system prompt |

**Tool 设计建议**:
- `fetch_deadlines(course?: str)` — 获取截止日期列表
- `add_reminder(title, date, priority)` — 添加提醒
- `filter_deadlines(urgency_level)` — 按紧急程度过滤
- 返回 `CalendarWidgetData(events=[...]).model_dump_json()`

**开发 Checklist**:
```markdown
- [ ] `tools/deadline.py` — 工具函数 + register_deadline_tools()
- [ ] `skills/deadline_manager.py` — 调优 prompt
- [ ] `tests/test_deadline.py` — 工具单元测试
- [ ] `CalendarWidget.vue` — 增强（如需要）
- [ ] `bash scripts/check.sh` 全量通过
```

---

### 5.2 F2: Course Assistant

**负责人**: Dev-B

**功能描述**: 解读课件、生成复习笔记、辅助考试准备、生成练习题。

**需要创建的文件（独占）**:

| 文件 | 说明 |
|------|------|
| `core/src/agent_core/tools/course_assist.py` | course assistant tools |
| `core/tests/test_course_assist.py` | 单元测试 |
| `gui/src/components/widgets/DocumentWidget.vue` | 增强文档组件（**独占**） |

**需要编辑的已有文件（独占）**:

| 文件 | 说明 |
|------|------|
| `core/src/agent_core/skills/course_assistant.py` | 调优 system prompt |

**Tool 设计建议**:
- `parse_slides(file_path)` — 解析课件
- `generate_notes(topic, content)` — 生成复习笔记
- `generate_quiz(topic, difficulty)` — 生成练习题
- 返回 `DocumentWidgetData(title=..., content=...).model_dump_json()`

**开发 Checklist**:
```markdown
- [ ] `tools/course_assist.py` — 工具函数 + register_course_assist_tools()
- [ ] `skills/course_assistant.py` — 调优 prompt
- [ ] `tests/test_course_assist.py` — 工具单元测试
- [ ] `DocumentWidget.vue` — 增强（如需要）
- [ ] `bash scripts/check.sh` 全量通过
```

---

### 5.3 F3: Campus Policy Search

**负责人**: Dev-C

**功能描述**: 搜索并解释校园政策法规，回答关于注册、住宿、出勤等政策问题。

**需要创建的文件（独占）**:

| 文件 | 说明 |
|------|------|
| `core/src/agent_core/tools/policy.py` | policy search tools |
| `core/tests/test_policy.py` | 单元测试 |
| `gui/src/components/widgets/SourcesWidget.vue` | 增强来源组件（**独占**） |
| `gui/src/components/widgets/WebPreviewWidget.vue` | 增强网页预览（**独占**） |

**需要编辑的已有文件（独占）**:

| 文件 | 说明 |
|------|------|
| `core/src/agent_core/skills/policy_search.py` | 调优 system prompt |

**Tool 设计建议**:
- `search_policy(query)` — 搜索相关政策
- `explain_policy(policy_id)` — 解读政策内容
- 返回 `SourcesWidgetData(sources=[...]).model_dump_json()` 或 `WebPreviewWidgetData(url=...).model_dump_json()`

**开发 Checklist**:
```markdown
- [ ] `tools/policy.py` — 工具函数 + register_policy_tools()
- [ ] `skills/policy_search.py` — 调优 prompt
- [ ] `tests/test_policy.py` — 工具单元测试
- [ ] `SourcesWidget.vue` / `WebPreviewWidget.vue` — 增强（如需要）
- [ ] `bash scripts/check.sh` 全量通过
```

---

### 5.4 F4: Course Recommendation

**负责人**: Dev-D

**功能描述**: 基于学生兴趣推荐课程、比较课程信息、展示课程卡片。

**需要创建的文件（独占）**:

| 文件 | 说明 |
|------|------|
| `core/src/agent_core/tools/course_recommend.py` | recommendation tools |
| `core/tests/test_course_recommend.py` | 单元测试 |
| `gui/src/components/widgets/CourseCardsWidget.vue` | 增强课程卡片（**独占**） |

**需要编辑的已有文件（独占）**:

| 文件 | 说明 |
|------|------|
| `core/src/agent_core/skills/course_recommend.py` | 调优 system prompt |

**Tool 设计建议**:
- `search_courses(keyword, department?)` — 搜索课程
- `compare_courses(course_ids)` — 对比多门课程
- `recommend(interests, background)` — 个性化推荐
- 返回 `CourseCardsWidgetData(courses=[...]).model_dump_json()`

**开发 Checklist**:
```markdown
- [ ] `tools/course_recommend.py` — 工具函数 + register_course_recommend_tools()
- [ ] `skills/course_recommend.py` — 调优 prompt
- [ ] `tests/test_course_recommend.py` — 工具单元测试
- [ ] `CourseCardsWidget.vue` — 增强（如需要）
- [ ] `bash scripts/check.sh` 全量通过
```

---

### 5.5 F5: Daily Campus News Push

**负责人**: Dev-E

**功能描述**: 汇总每日校园新闻、活动公告，生成个性化新闻摘要。

**需要创建的文件（独占）**:

| 文件 | 说明 |
|------|------|
| `core/src/agent_core/tools/news.py` | news tools + `NewsDigestWidgetData` |
| `core/tests/test_news.py` | 单元测试 |
| `gui/src/components/widgets/NewsDigestWidget.vue` | **新建** — 新闻摘要组件 |

**需要编辑的已有文件（独占）**:

| 文件 | 说明 |
|------|------|
| `core/src/agent_core/skills/campus_news.py` | 调优 system prompt |

**需要追加一行的共享文件**:

| 文件 | 要做的事 |
|------|---------|
| `gui/src/components/widgets/index.ts` | 追加 `NEWS_DIGEST` → `NewsDigestWidget.vue` 映射 |

**Tool 设计建议**:
- `fetch_news(category?)` — 获取校园新闻
- `summarize_news(article_ids)` — 生成新闻摘要
- `push_digest(interests)` — 个性化推送
- 在 `tools/news.py` 中定义 `NewsDigestWidgetData`：

```python
class NewsDigestWidgetData(WidgetData):
    widget_type: Literal[WidgetType.NEWS_DIGEST] = WidgetType.NEWS_DIGEST
    articles: list[dict[str, Any]] = []
```

- 返回 `NewsDigestWidgetData(articles=[...]).model_dump_json()`

**开发 Checklist**:
```markdown
- [ ] `tools/news.py` — 工具函数 + NewsDigestWidgetData + register_news_tools()
- [ ] `skills/campus_news.py` — 调优 prompt
- [ ] `tests/test_news.py` — 工具单元测试 + WidgetData 序列化测试
- [ ] `NewsDigestWidget.vue` — 新建组件
- [ ] `widgets/index.ts` — 追加映射行
- [ ] `bash scripts/check.sh` 全量通过
```

---

### 5.6 文件归属矩阵

| 文件 | F1 | F2 | F3 | F4 | F5 | 冲突？ |
|------|:--:|:--:|:--:|:--:|:--:|:------:|
| `tools/deadline.py` | ✏️ | | | | | ✅ 独占 |
| `tools/course_assist.py` | | ✏️ | | | | ✅ 独占 |
| `tools/policy.py` | | | ✏️ | | | ✅ 独占 |
| `tools/course_recommend.py` | | | | ✏️ | | ✅ 独占 |
| `tools/news.py` | | | | | ✏️ | ✅ 独占 |
| `skills/deadline_manager.py` | ✏️ | | | | | ✅ 独占 |
| `skills/course_assistant.py` | | ✏️ | | | | ✅ 独占 |
| `skills/policy_search.py` | | | ✏️ | | | ✅ 独占 |
| `skills/course_recommend.py` | | | | ✏️ | | ✅ 独占 |
| `skills/campus_news.py` | | | | | ✏️ | ✅ 独占 |
| `tests/test_<feature>.py` | ✏️ | ✏️ | ✏️ | ✏️ | ✏️ | ✅ 各自独占 |
| `CalendarWidget.vue` | ✏️ | | | | | ✅ 独占 |
| `DocumentWidget.vue` | | ✏️ | | | | ✅ 独占 |
| `SourcesWidget.vue` | | | ✏️ | | | ✅ 独占 |
| `CourseCardsWidget.vue` | | | | ✏️ | | ✅ 独占 |
| `NewsDigestWidget.vue` | | | | | ✏️ | ✅ 独占 |
| `widgets/index.ts` | | | | | 📌 | ⚠️ append-only |
| `dependencies.py` | | | | | | ✅ **无人需改** |
| `skills/__init__.py` | | | | | | ✅ **无人需改** |
| `events.py` | | | | | | ✅ **无人需改** |
| `agent.py` | | | | | | ✅ **无人需改** |
| `WorkspacePanel.vue` | | | | | | ✅ **无人需改** |
| `chatConstants.ts` | | | | | | ✅ **无人需改** |

📌 = 仅追加一行 &emsp; ✏️ = 主要编辑（独占）

---

## 6. Merge 策略与 CI 守护

### 6.1 分支策略

```
main (protected)
  └── develop (integration)
        ├── feature/f1-deadline      ← Dev-A
        ├── feature/f2-course-assist ← Dev-B
        ├── feature/f3-policy-search ← Dev-C
        ├── feature/f4-course-rec    ← Dev-D
        └── feature/f5-campus-news   ← Dev-E
```

- 每个 feature 分支从 `develop` 创建
- PR 合入 `develop` 前**必须通过 CI**
- `develop` 稳定后 merge 到 `main`

### 6.2 CI 检查项（`bash scripts/check.sh`）

| 步骤 | 检查内容 |
|------|---------|
| Step 1 | `ruff format` + `prettier` — 代码格式化 |
| Step 2 | `ruff check` + `prettier --check` — Lint 检查 |
| Step 3 | Language check — 源代码中无中文硬编码 |
| Step 4 | `pytest` — Python 单元测试（core + cli + poc_frontend） |
| Step 5 | `vitest` — Vue 单元测试 |
| Step 6 | `vue-tsc --build` + `vite build` — 类型检查 + 构建 |

> 所有步骤全部通过后，代码方可提交 PR。

### 6.3 Merge 顺序

- 各功能 PR **没有依赖关系**，可以任意顺序 merge
- **唯一约束**: 框架准备 PR 必须最先 merge，所有 feature 分支必须基于它
- 如果长期开发，建议定期 rebase `develop` 以减少后期冲突

### 6.4 PR 规范

- PR 标题遵循 Conventional Commits（如 `feat(f1): add deadline management tools`）
- PR 描述中声明修改了哪些文件
- 如果 diff 涉及公共文件（`dependencies.py`、`agent.py`、`events.py` 等），**必须说明原因**

---

## 7. 注意事项与约定

### 7.1 代码质量

- 遵循 **KISS 原则**: 简洁清晰、模块化
- 状态类字符串 → 使用 `StrEnum`（如 `WidgetType`、`SkillType`、`EventType`）
- 结构化数据 → 使用 `pydantic.BaseModel`（如 `WidgetData`、`SkillDefinition`）
- 字符串常量 → 提取为具名常量或枚举，**禁止 magic string 散落代码中**
- 详见 [Python 代码规范](zh-CN_code_conventions_python.md) 和 [Vue 代码规范](zh-CN_code_conventions_vue.md)

### 7.2 Tool 开发注意

- 每个 tool 函数必须有完整 docstring（LangChain 用它生成 tool description）
- tool 的参数类型要清晰（`str`、`int` 等简单类型，不要用复杂嵌套对象）
- 需要触发 widget 展示时，返回 `WidgetData` 子类的 `model_dump_json()`
- 如需访问外部 API，可以先 mock 返回值，后续迭代替换
- tool 函数可以是同步或异步，`ToolRegistry.execute()` 都支持

### 7.3 WidgetData 开发注意

- 所有 `WidgetData` 子类必须声明 `widget_type` 字段，使用 `Literal[WidgetType.XXX]`
- 子类定义在对应的 `tools/<feature>.py` 中（co-located 原则）
- 无需修改 `events.py` 或 `widgets.py`，动态联合自动发现

### 7.4 前端 Widget 开发注意

- 每个 widget 组件接收 `data` prop（类型为 `Record<string, any>`）
- 确保组件在 `data` 为空时有合理的空状态展示
- 使用 `WIDGET_TYPES` 常量引用 widget type，不要硬编码字符串
- 新组件在 `widgets/index.ts` 中使用 `defineAsyncComponent` 注册，实现懒加载

### 7.5 测试注意

- 每个 feature 创建独立的测试文件 `test_<feature>.py`
- 测试覆盖：tool 函数、WidgetData 序列化/反序列化、edge cases
- **不得删除已有测试**
- 运行 `bash scripts/check.sh` 确保全量通过

### 7.6 禁止修改的公共文件

以下文件已通过自动发现机制解耦，**五个功能开发期间不应修改**：

| 文件 | 原因 |
|------|------|
| `api/dependencies.py` | Tool 自动发现，无需手动注册 |
| `skills/__init__.py` | Skill 自动发现，无需手动注册 |
| `engine/agent.py` | WidgetData 动态联合，无需手动导入 |
| `models/events.py` | WidgetType 已预留所有值 |
| `models/__init__.py` | 公共导出已固定 |
| `WorkspacePanel.vue` | 使用注册表，无需 switch-case |
| `chatConstants.ts` | WIDGET_TYPES 已预留所有值 |

如果确实需要修改上述文件，**必须在 PR 中说明原因并经 tech lead 审批**。

