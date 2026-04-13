# Vue / TypeScript 代码规范

本文档定义 ReAct Agent 项目中 Vue3 + TypeScript 前端（`packages/gui`）的代码规范。

## 格式化工具：Prettier

项目使用 [Prettier](https://prettier.io/) 进行代码格式化。

### 格式化规则

| 配置项 | 值 | 说明 |
|--------|------|------|
| 引号风格 | 单引号 `'` | `singleQuote: true` |
| 缩进 | 2 空格 | 标准前端缩进 |
| 分号 | 无 | `semi: false` |
| 尾逗号 | ES5 风格 | `trailingComma: "es5"` |

### 格式化命令

```bash
cd packages/gui

# 自动格式化
pnpm format

# 或直接调用 Prettier
pnpm prettier --write --experimental-cli src/
```

## Lint 工具：ESLint + oxlint

项目同时使用 ESLint 和 oxlint 进行代码质量检查：

- **oxlint**：快速的 Rust 实现 Linter，优先执行
- **ESLint**：功能全面的 JavaScript/TypeScript Linter

### Lint 命令

```bash
cd packages/gui

# 运行所有 Lint（oxlint → ESLint，自动修复）
pnpm lint

# 单独运行
pnpm lint:oxlint   # oxlint + 自动修复
pnpm lint:eslint    # ESLint + 自动修复
```

### ESLint 插件

项目使用以下 ESLint 插件：

- `eslint-plugin-vue` — Vue 组件专用规则
- `@vue/eslint-config-typescript` — TypeScript 规则
- `eslint-config-prettier` — 禁用与 Prettier 冲突的规则
- `eslint-plugin-oxlint` — 与 oxlint 协调，避免规则重复
- `@vitest/eslint-plugin` — Vitest 测试规则
- `eslint-plugin-playwright` — Playwright E2E 测试规则

## 命名约定

| 类别 | 风格 | 示例 |
|------|------|------|
| 变量、函数 | `camelCase` | `chatStore`, `sendMessage()` |
| 类、接口、类型 | `PascalCase` | `ChatMessage`, `AgentApi` |
| 常量 | `UPPER_SNAKE_CASE` | `API_BASE_URL`, `MAX_RETRIES` |
| Vue 组件 | `PascalCase` | `ChatView.vue`, `MessageList.vue` |
| 普通 TS 文件 | `camelCase` | `agent.ts`, `chat.ts` |
| 测试文件 | `camelCase.spec.ts` | `agent.spec.ts`, `chat.spec.ts` |
| 目录名 | `camelCase` 或短横线 | `stores/`, `__tests__/` |

### 文件命名规则

```
src/
├── api/
│   └── agent.ts              # camelCase.ts — 普通模块
├── stores/
│   └── chat.ts               # camelCase.ts — Pinia Store
├── views/
│   └── ChatView.vue          # PascalCase.vue — Vue 组件
├── components/
│   └── MessageItem.vue       # PascalCase.vue — Vue 组件
├── router/
│   └── index.ts              # 特殊入口文件
└── App.vue                   # 根组件
```

## Vue 3 组件规范

### Composition API + `<script setup>`

所有组件必须使用 Vue 3 Composition API 和 `<script setup>` 语法：

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import { useChatStore } from '@/stores/chat'

// Props & Emits
const props = defineProps<{
  title: string
  maxLength?: number
}>()

const emit = defineEmits<{
  submit: [message: string]
}>()

// Reactive state
const inputText = ref('')
const chatStore = useChatStore()

// Computed
const isValid = computed(() => inputText.value.trim().length > 0)

// Methods
function handleSubmit() {
  if (!isValid.value) return
  emit('submit', inputText.value)
  inputText.value = ''
}
</script>

<template>
  <div class="chat-input">
    <input v-model="inputText" :maxlength="props.maxLength" />
    <button :disabled="!isValid" @click="handleSubmit">
      Send
    </button>
  </div>
</template>

<style scoped>
.chat-input {
  display: flex;
  gap: 8px;
}
</style>
```

### 组件结构顺序

```vue
<script setup lang="ts">
  <!-- 1. 导入 -->
  <!-- 2. Props / Emits -->
  <!-- 3. 响应式状态 -->
  <!-- 4. 计算属性 -->
  <!-- 5. 方法 -->
  <!-- 6. 生命周期钩子 -->
</script>

<template>
  <!-- 模板 -->
</template>

<style scoped>
  /* 样式（使用 scoped） */
</style>
```

## TypeScript 规范

### 严格模式

项目开启 TypeScript 严格模式（`strict: true`），包括：

- `noImplicitAny` — 禁止隐式 any
- `strictNullChecks` — 严格空值检查
- `strictFunctionTypes` — 严格函数类型

### 类型定义

```typescript
// ✅ 使用 interface 定义对象结构
interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

// ✅ 使用 type 定义联合/交叉类型
type StreamEvent =
  | { type: 'thinking'; content: string }
  | { type: 'tool_call'; name: string; args: Record<string, unknown> }
  | { type: 'response'; content: string }

// ❌ 避免 any
function processData(data: any) { ... }

// ✅ 使用 unknown 或具体类型
function processData(data: unknown) { ... }
```

### Pinia Store 规范

```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useChatStore = defineStore('chat', () => {
  // State
  const messages = ref<ChatMessage[]>([])
  const isLoading = ref(false)

  // Getters
  const messageCount = computed(() => messages.value.length)

  // Actions
  async function sendMessage(content: string): Promise<void> {
    isLoading.value = true
    try {
      // ... API call
    } finally {
      isLoading.value = false
    }
  }

  return { messages, isLoading, messageCount, sendMessage }
})
```

## 国际化 (i18n) 规范

所有用户可见的 UI 文本必须通过 Vue I18n 进行国际化。详见 [`zh-CN_i18n.md`](zh-CN_i18n.md)。

### i18n 快速要点

1. **禁止硬编码字符串**：组件中的所有用户可见文本必须从语言包读取
2. **使用 `useI18n()` Composition API**：

```vue
<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <button>{{ t('common.save') }}</button>
</template>
```

3. **i18n key 命名规范**：`模块.功能.字段` (camelCase)
   - 例：`settings.sections.casService`、`common.save`、`errors.networkError`

4. **同步维护两个语言包**：修改 `en.json` 时必须同步修改 `zh.json`
   - 位置：`src/i18n/locales/`
   - `zh.json` 使用 UTF-8 中文字符（不是 Unicode 转义 `\uXXXX`）

5. **Vitest 中 Mock vue-i18n**：

```typescript
import { vi } from 'vitest'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key, // 测试中返回 key 本身（语言无关）
  }),
}))
```

详细规范见 [`zh-CN_i18n.md`](zh-CN_i18n.md)。

---

## 语言策略

**所有源代码必须使用英文**，包括：

- 变量名、函数名、组件名
- 注释和 JSDoc
- 字符串字面值（用户可见的 UI 文本由 i18n 管理，见上文）
- 常量名和类型名

语言检查工具 `check_language.py` 扫描 `.ts`、`.vue`、`.tsx` 文件，CI 中自动执行。

## 测试规范

### 单元测试（Vitest）

```typescript
import { describe, it, expect, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useChatStore } from '@/stores/chat'

describe('ChatStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should add a message', () => {
    const store = useChatStore()
    store.messages.push({ role: 'user', content: 'hello', timestamp: Date.now() })
    expect(store.messages).toHaveLength(1)
  })
})
```

### E2E 测试（Playwright）

```typescript
import { test, expect } from '@playwright/test'

test('chat page loads', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('h1')).toBeVisible()
})
```

### 测试命令

```bash
cd packages/gui

pnpm vitest run          # 运行所有单元测试
pnpm vitest              # watch 模式
pnpm test:e2e            # 运行 Playwright E2E 测试
pnpm run type-check      # TypeScript 类型检查
pnpm build               # 构建检查
```
