# Deadline 展示过滤机制设计计划

## 1. 需求概述

**需求来源**：`.nonpublic/developing_prompt/20260416_deadline过滤/A001_基本需求.md`

> Allow users to filter deadlines by course name and urgency level for easier browsing.

该需求扩展现有的 US2（统一看板），补全其中"支持按课程/紧急度过滤"的前端 UI 实现。
后端过滤接口（`GET /api/deadlines?course=...&priority=...`）和前端 API 封装
（`fetchDeadlines(course?, priority?)`）均已存在，本次仅补全前端面板的视觉控件和交互。

### 1.1 当前状态对比

| 层 | 已有 | 缺少 |
|----|------|------|
| 后端路由 | `GET /deadlines?course&priority` ✅ | — |
| 后端 Store | `list_all(course?, priority?)` ✅ | — |
| 前端 API | `fetchDeadlines(course?, priority?)` ✅ | — |
| 前端 UI | — | 课程下拉 + 优先级下拉控件 |
| 前端状态 | — | `filterCourse` / `filterPriority` refs |
| i18n | — | 过滤控件相关字符串 |
| 测试 | — | 过滤交互的组件测试 |
---

## 2. 用户故事与边界情况

### 2.1 用户故事 US2-F（Filter）

| 路径 | 描述 |
|------|------|
| **Happy path** | 用户在 DeadlinePanelWidget 工具栏看到 Course 下拉和 Priority 下拉；选择某课程/优先级后，三个子视图（Tasks / Week / Month）立即只显示匹配项；重置为"All"后恢复全部 |
| **组合筛选** | 同时选择 `CS302` + `High` → 仅显示满足两个条件的任务 |
| **与 Hide done 叠加** | 三者同时生效（AND 语义） |
| **结果为空** | 子视图显示 "No deadlines match current filters." |
| **DDL 无课程** | `course=""` 的任务不出现在下拉选项里；"All courses" 时仍正常显示 |
| **Error UX** | 加载失败时控件仍渲染，列表区域显示错误信息（已有逻辑，无需修改） |

### 2.2 边界情况一览

| 情况 | 预期行为 |
|------|---------|
| 所有 DDL 无 course 字段 | Course 下拉只有"All courses"，无其他选项 |
| 只有一种优先级 | Priority 下拉仍显示全部4选项 |
| 筛选途中数据刷新 | 刷新后 `uniqueCourses` computed 重算，已选 course 若不再存在则重置为"All" |
| 快速切换 | 纯 computed 响应，无 async，无竞态 |
---

## 3. 调用链设计

### 3.1 过滤调用链

```
用户从 Course <select> 选择课程名 / Priority <select> 选择优先级
  → filterCourse.value / filterPriority.value 更新（reactive ref）
  → filteredDeadlines computed 重新计算（纯前端，无 I/O）
     ├─ 应用 hideCompleted 过滤
     ├─ 应用 filterCourse 过滤（若非空，仅保留 d.course === filterCourse）
     └─ 应用 filterPriority 过滤（若非空，仅保留 d.priority === filterPriority）
  → TaskListView / WeekView / MonthView 接收 :deadlines="filteredDeadlines" 自动重渲染
```

**无额外 API 调用**：所有过滤在前端已加载数据上执行，避免网络开销。

### 3.2 课程选项生成链

```
deadlines.value 更新（onMounted 或刷新）
  → uniqueCourses computed 重算：
     deadlines.value
       .map(d => d.course)
       .filter(Boolean)         ← 排除空字符串
       → Set 去重 → [...].sort()
  → Course <select> 选项重新渲染
  ─ 若当前 filterCourse 不在新选项中 → filterCourse 重置为 ''（watch 守卫）
```

### 3.3 设计决策：客户端过滤 vs 服务端过滤

| 维度 | 客户端过滤（本方案） | 服务端过滤 |
|------|--------------------|-----------| 
| 响应速度 | 即时（无网络延迟）| 有网络延迟 |
| 实现复杂度 | 低（纯 computed）| 需管理 loading/error 状态 |
| 课程选项来源 | 从已加载数据派生，始终准确 | 需额外接口或全量加载 |
| 适用场景 | 数据量在面板级别（≤数百条）| 数据量极大时更优 |

**结论**：DeadlinePanel 数据集在学生级别（数十到数百条），客户端过滤体验更优。
---

## 4. 技术方案

### 4.1 DeadlinePanelWidget.vue — 新增状态

```typescript
// 新增 filter state
const filterCourse = ref<string>('')    // '' = All courses
const filterPriority = ref<string>('')  // '' = All priorities

// 从已加载数据中派生唯一课程列表
const uniqueCourses = computed<string[]>(() => {
  const courses = new Set(deadlines.value.map((d) => d.course).filter(Boolean))
  return [...courses].sort()
})

// 当数据刷新后，若当前选中的课程已不存在则重置
watch(uniqueCourses, (courses) => {
  if (filterCourse.value && !courses.includes(filterCourse.value)) {
    filterCourse.value = ''
  }
})
```

### 4.2 DeadlinePanelWidget.vue — 更新 filteredDeadlines

```typescript
// 已有：
const filteredDeadlines = computed(() => {
  if (!hideCompleted.value) return deadlines.value
  return deadlines.value.filter((d) => !d.completed)
})

// 替换为（增加 course 和 priority 过滤）：
const filteredDeadlines = computed(() => {
  let result = deadlines.value
  if (hideCompleted.value) result = result.filter((d) => !d.completed)
  if (filterCourse.value) result = result.filter((d) => d.course === filterCourse.value)
  if (filterPriority.value) result = result.filter((d) => d.priority === filterPriority.value)
  return result
})
```

### 4.3 DeadlinePanelWidget.vue — 工具栏 UI

工具栏新增两个 `<select>` 控件，置于视图 Tab 后、New 按钮前：

```html
<!-- Course filter -->
<select v-model="filterCourse" class="...">
  <option value="">{{ t('deadlines.filterAllCourses') }}</option>
  <option v-for="c in uniqueCourses" :key="c" :value="c">{{ c }}</option>
</select>

<!-- Priority filter -->
<select v-model="filterPriority" class="...">
  <option
    v-for="opt in PRIORITY_FILTER_OPTIONS"
    :key="opt.value"
    :value="opt.value"
  >{{ t(opt.labelKey) }}</option>
</select>
```

### 4.4 deadlineConstants.ts — 新增常量

```typescript
/** Options for the priority filter dropdown (includes "All" sentinel). */
export const PRIORITY_FILTER_OPTIONS: ReadonlyArray<{ value: string; labelKey: string }> = [
  { value: '', labelKey: 'deadlines.filterAllPriorities' },
  { value: 'high', labelKey: 'deadlines.filterPriorityHigh' },
  { value: 'medium', labelKey: 'deadlines.filterPriorityMedium' },
  { value: 'low', labelKey: 'deadlines.filterPriorityLow' },
] as const
```

### 4.5 i18n 字符串

新增到 `en.json` 和 `zh.json` 的 `"deadlines"` 子键（若不存在则新建该键组）：

| key | en | zh |
|-----|----|----|
| `deadlines.filterAllCourses` | `"All courses"` | `"全部课程"` |
| `deadlines.filterAllPriorities` | `"All"` | `"全部"` |
| `deadlines.filterPriorityHigh` | `"High"` | `"高"` |
| `deadlines.filterPriorityMedium` | `"Medium"` | `"中"` |
| `deadlines.filterPriorityLow` | `"Low"` | `"低"` |
| `deadlines.filterNoMatch` | `"No deadlines match current filters."` | `"暂无满足筛选条件的 DDL。"` |

> ⚠️ i18n 注意：以上字符串均不含 `@` / `|` / `{` / `}` 特殊字符，无需转义。
---

## 5. 文件变更清单

| 文件 | 操作 | 变更说明 |
|------|------|---------|
| `packages/gui/src/components/widgets/DeadlinePanelWidget.vue` | 修改 | 添加 `filterCourse` / `filterPriority` refs；更新 `filteredDeadlines` computed；添加 `uniqueCourses` computed + watch；在工具栏添加两个 `<select>` |
| `packages/gui/src/components/widgets/deadlineConstants.ts` | 修改 | 添加 `PRIORITY_FILTER_OPTIONS` 常量 |
| `packages/gui/src/i18n/locales/en.json` | 修改 | 新增 `deadlines.*` 键组，含6条字符串 |
| `packages/gui/src/i18n/locales/zh.json` | 修改 | 新增 `deadlines.*` 键组，含6条中文字符串 |
| `packages/gui/src/components/widgets/__tests__/DeadlinePanelWidget.spec.ts` | 新建 | 组件测试（见第6节）|

**无后端变更**：后端接口已满足需求，本次不触及后端文件。
---

## 6. 测试计划

> 测试计划已分离至独立文件，**编码阶段不应读取**，仅在执行测试阶段参考：
>
> 📄 [`zh-CN_deadline_filter_test_plan.md`](zh-CN_deadline_filter_test_plan.md)
>
> 包含：测试环境、Mock 设置模板、9 个组件测试用例（T1–T9）、T3 代码示例、安全性 checklist。
