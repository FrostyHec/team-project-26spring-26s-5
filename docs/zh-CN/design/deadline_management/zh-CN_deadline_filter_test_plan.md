# Deadline 过滤功能 — 测试计划

## 1. 测试环境

| 项目 | 值 |
|------|---|
| 框架 | Vitest + jsdom（见 `vitest.config.ts`）|
| 组件测试库 | `@vue/test-utils` (`mount`) |
| i18n | 挂载时注入 `createI18n({ locale: 'en', messages: { en } })` |
| 测试文件路径 | `packages/gui/src/components/widgets/__tests__/DeadlinePanelWidget.spec.ts` |
---

## 2. Mock 设置

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import enMessages from '@/i18n/locales/en.json'
import DeadlinePanelWidget from '../DeadlinePanelWidget.vue'
import { DateType, type DeadlineInfo } from '@/api/agent'
import * as agentApi from '@/api/agent'

// Mock fetchDeadlines — 不发出真实请求
vi.mock('@/api/agent', async (importOriginal) => {
  const actual = await importOriginal<typeof agentApi>()
  return { ...actual, fetchDeadlines: vi.fn() }
})

const mockFetchDeadlines = vi.mocked(agentApi.fetchDeadlines)

/** 构造最小化 DeadlineInfo */
function makeTask(overrides: Partial<DeadlineInfo> = {}): DeadlineInfo {
  return {
    id: crypto.randomUUID(),
    title: 'Test Task',
    course: '',
    due_date: '2026-05-01',
    priority: 'medium',
    source: 'manual',
    description: '',
    date_type: DateType.MOMENT_DAY,
    start_date: '',
    completed: false,
    ...overrides,
  }
}

// 预置测试数据集
const TASKS = [
  makeTask({ id: '1', title: 'CS302 High', course: 'CS302', priority: 'high' }),
  makeTask({ id: '2', title: 'CS302 Low', course: 'CS302', priority: 'low' }),
  makeTask({ id: '3', title: 'MATH201 Med', course: 'MATH201', priority: 'medium' }),
  makeTask({ id: '4', title: 'No Course', course: '', priority: 'high' }),
]

const i18n = createI18n({ legacy: false, locale: 'en', messages: { en: enMessages } })

async function mountWidget(tasks = TASKS) {
  mockFetchDeadlines.mockResolvedValue(tasks)
  const wrapper = mount(DeadlinePanelWidget, {
    global: { plugins: [i18n] },
  })
  await flushPromises()   // 等待 onMounted 中的 fetchDeadlines 完成
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
})
```
---

## 3. 测试用例

### 3.1 用例列表（T1–T9）

| # | 测试用例名称 | 关键断言 |
|---|------------|---------|
| T1 | `renders course dropdown with unique sorted courses` | Course `<select>` 含 "All courses" + "CS302" + "MATH201"（不含空字符串，不重复，字母序）|
| T2 | `renders priority dropdown with all 4 options` | Priority `<select>` 含 All / High / Medium / Low（共 4 项）|
| T3 | `filter by course CS302 shows only CS302 tasks` | 选择 CS302 后，渲染的 task 标题只有 "CS302 High" 和 "CS302 Low" |
| T4 | `filter by priority HIGH shows only high tasks` | 选择 High 后，渲染"CS302 High"和"No Course"，不渲染"CS302 Low"/"MATH201 Med" |
| T5 | `combined filter CS302 + HIGH shows single task` | 选择 CS302 + High → 只有"CS302 High" |
| T6 | `empty filter result shows no-match message` | 选择 MATH201 + High → 渲染 "No deadlines match current filters." |
| T7 | `reset course to All shows all tasks again` | 先选 CS302，再重置为 '' → 4 条任务全部显示 |
| T8 | `filter combined with hideCompleted` | hideCompleted checkbox 勾上 + course=CS302 → 只显示 CS302 且未完成的任务 |
| T9 | `course dropdown resets when loaded data no longer contains selected course` | 先选 CS302，再 `mockFetchDeadlines` 切换为只含 MATH201 的数据并刷新 → `filterCourse` 重置为 '' |

### 3.2 T3 实现示例

```typescript
it('filter by course CS302 shows only CS302 tasks', async () => {
  const wrapper = await mountWidget()

  const courseSelect = wrapper.find('[data-testid="filter-course"]')
  await courseSelect.setValue('CS302')

  const titles = wrapper.findAll('[data-testid="task-title"]').map((w) => w.text())
  expect(titles).toContain('CS302 High')
  expect(titles).toContain('CS302 Low')
  expect(titles).not.toContain('MATH201 Med')
  expect(titles).not.toContain('No Course')
})
```

> **data-testid 约定**：`<select>` 添加 `data-testid="filter-course"` / `data-testid="filter-priority"`；
> 任务标题渲染处添加 `data-testid="task-title"`。编码时同步落实。

### 3.3 无 Dump 说明

本功能为纯前端客户端计算，不涉及外部服务，不需要 dump 真实响应数据。

### 3.4 安全性检查

| 类别 | 检查项 | 状态 |
|------|-------|------|
| 用户输入 | `filterCourse` 来源于 `<select>` 选项（从自身数据派生），非自由文本，无注入风险 | ✅ |
| 用户输入 | `filterPriority` 来源于 `PRIORITY_FILTER_OPTIONS` 枚举常量 | ✅ |
| i18n | 所有新增字符串不含 `@`/`\|`/`{`/`}` | ✅ |
| 空 catch | 不新增 try/catch 块 | ✅ |
| 共享状态 | 过滤状态为组件本地 ref，不写入全局 store | ✅ |
