# Vue3 前端实现详解

本文档详细说明 `packages/gui` 包的实现，即基于 Vue3 + Vite + Pinia 的生产级前端。

---

## 1. 项目概述

Vue3 前端作为 ReAct Agent 的正式 GUI 客户端，通过 HTTP API 与后端通信，提供完整的对话体验。

### 技术栈

| 技术 | 用途 |
|------|------|
| Vue 3 | UI 框架（Composition API） |
| TypeScript | 类型安全（strict 模式） |
| Vite | 构建工具 + 开发服务器 |
| Pinia | 状态管理 |
| Vue Router | 路由管理 |
| Vitest + jsdom | 单元测试 |
| Playwright | E2E 测试 |

### 目录结构

```
packages/gui/src/
├── App.vue            # 根组件
├── main.ts            # 应用入口
├── api/
│   └── agent.ts       # API 客户端层
├── stores/
│   └── chat.ts        # Pinia 状态管理
├── views/
│   └── ChatView.vue   # 对话视图组件
├── router/
│   └── index.ts       # Vue Router 配置
├── assets/
│   └── main.css       # 全局样式
└── components/        # 可复用组件（预留）
```

---

## 2. API 客户端层

**文件：** `packages/gui/src/api/agent.ts`

### 2.1 类型定义

```typescript
/** 工具信息 */
export interface ToolInfo {
  name: string
  description: string
  sensitivity: string
}

/** Agent 流式事件 */
export interface AgentEvent {
  type: 'token' | 'tool_start' | 'tool_end'
  content?: string
  name?: string
  input?: Record<string, unknown>
  output?: string
}
```

### 2.2 API 基础地址

```typescript
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'
```

- 优先使用环境变量 `VITE_API_BASE_URL`
- 默认值 `/api`，配合 Vite 代理转发到后端

### 2.3 同步对话 — `sendMessage()`

```typescript
export async function sendMessage(message: string): Promise<string> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }

  const data = await response.json()
  return data.response
}
```

发送 POST 请求到 `/api/chat`，返回完整文本响应。

### 2.4 流式对话 — `streamMessage()`

```typescript
export async function* streamMessage(message: string): AsyncGenerator<AgentEvent> {
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6).trim()
        if (data === '[DONE]') return
        try {
          yield JSON.parse(data) as AgentEvent
        } catch {
          // 跳过格式错误的 JSON
        }
      }
    }
  }
}
```

**SSE 解析实现要点：**

1. **AsyncGenerator 模式**：使用 `async function*` 定义异步生成器，调用方通过 `for await...of` 消费
2. **ReadableStream Reader**：通过 `response.body.getReader()` 逐块读取二进制数据
3. **TextDecoder**：将 `Uint8Array` 解码为字符串，设置 `{ stream: true }` 处理多字节字符截断
4. **缓冲区处理**：用 `buffer` 累积不完整的行，`split('\n')` 后保留最后一个未完成的片段
5. **SSE 协议解析**：只处理 `data: ` 前缀的行，遇到 `[DONE]` 标记立即返回
6. **容错设计**：`JSON.parse()` 异常被捕获并静默跳过

### 2.5 工具列表 — `fetchTools()`

```typescript
export async function fetchTools(): Promise<ToolInfo[]> {
  const response = await fetch(`${API_BASE}/tools`)
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}
```

### 2.6 健康检查 — `checkHealth()`

```typescript
export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/health`)
    return response.ok
  } catch {
    return false
  }
}
```

网络异常时返回 `false`，不抛出错误。

---

## 3. 状态管理（Pinia Store）

**文件：** `packages/gui/src/stores/chat.ts`

### 3.1 数据模型

```typescript
/** 聊天消息 */
export interface ChatMessage {
  id: string              // 唯一标识 (msg-{timestamp}-{counter})
  role: 'user' | 'assistant'
  content: string
  toolCalls?: ToolCallInfo[]
  timestamp: Date
}

/** 工具调用信息 */
export interface ToolCallInfo {
  name: string
  input: Record<string, unknown>
  output?: string
  status: 'running' | 'completed' | 'error'
}
```

### 3.2 Store 定义

```typescript
export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const isLoading = ref(false)
  const isConnected = ref(false)
  const error = ref<string | null>(null)

  let messageCounter = 0

  function generateId(): string {
    return `msg-${Date.now()}-${messageCounter++}`
  }
  // ...
})
```

使用 Pinia 的 **Setup Store** 模式（Composition API 风格）：

| 状态 | 类型 | 说明 |
|------|------|------|
| `messages` | `ref<ChatMessage[]>` | 消息列表，支持响应式更新 |
| `isLoading` | `ref<boolean>` | 加载状态，防止重复发送 |
| `isConnected` | `ref<boolean>` | 后端连接状态 |
| `error` | `ref<string \| null>` | 最近的错误信息 |

### 3.3 发送消息 — `sendMessage()`

```typescript
async function sendMessage(content: string): Promise<void> {
  if (!content.trim() || isLoading.value) return

  error.value = null

  // 1. 添加用户消息
  const userMsg: ChatMessage = {
    id: generateId(),
    role: 'user',
    content: content.trim(),
    timestamp: new Date(),
  }
  messages.value.push(userMsg)

  // 2. 创建助手消息占位
  const assistantMsg: ChatMessage = {
    id: generateId(),
    role: 'assistant',
    content: '',
    toolCalls: [],
    timestamp: new Date(),
  }
  messages.value.push(assistantMsg)

  isLoading.value = true

  try {
    // 3. 流式消费事件
    for await (const event of streamMessage(content)) {
      switch (event.type) {
        case 'token':
          assistantMsg.content += event.content || ''
          break

        case 'tool_start':
          assistantMsg.toolCalls?.push({
            name: event.name || 'unknown',
            input: event.input || {},
            status: 'running',
          })
          break

        case 'tool_end': {
          const tc = assistantMsg.toolCalls?.find(
            (t) => t.name === event.name && t.status === 'running',
          )
          if (tc) {
            tc.output = event.output || ''
            tc.status = 'completed'
          }
          break
        }
      }
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Unknown error'
    assistantMsg.content = assistantMsg.content || 'Failed to get response.'
  } finally {
    isLoading.value = false
  }
}
```

**执行流程：**

1. **输入校验**：空输入或正在加载时直接返回
2. **用户消息入列**：立即将用户消息推入 `messages` 数组，UI 即时显示
3. **助手消息占位**：创建空的助手消息，后续通过引用直接修改其 `content` 和 `toolCalls`
4. **流式事件处理**：
   - `token` → 追加文本到 `assistantMsg.content`
   - `tool_start` → 向 `toolCalls` 数组追加新的 `ToolCallInfo`（状态为 `running`）
   - `tool_end` → 查找对应的 `running` 状态工具调用，更新 `output` 和 `status`
5. **错误处理**：捕获异常后设置 `error` 状态，若助手消息无内容则显示回退文本
6. **清理**：`finally` 中重置 `isLoading`

**响应式更新机制：** 由于 `assistantMsg` 是 `messages` 数组中的对象引用，对其属性的修改会被 Vue 的响应式系统自动追踪，UI 实时更新。

### 3.4 其他 Actions

```typescript
/** 检查后端连接 */
async function checkConnection(): Promise<void> {
  isConnected.value = await checkHealth()
}

/** 清空消息 */
function clearMessages(): void {
  messages.value = []
}
```

### 3.5 导出

```typescript
return {
  messages, isLoading, isConnected, error,
  sendMessage, clearMessages, checkConnection,
}
```

---

## 4. ChatView 对话视图组件

**文件：** `packages/gui/src/views/ChatView.vue`

### 4.1 脚本部分（Composition API）

```typescript
<script setup lang="ts">
import { ref, nextTick, watch, onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()
const inputText = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

onMounted(() => {
  chatStore.checkConnection()
})
```

- **`onMounted`**：组件挂载时自动检查后端连接状态

### 4.2 发送消息

```typescript
async function handleSend() {
  if (!inputText.value.trim()) return
  const msg = inputText.value
  inputText.value = ''
  await chatStore.sendMessage(msg)
}
```

先清空输入框再发送，保证用户体验流畅。

### 4.3 键盘快捷键

```typescript
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}
```

- **Enter**：发送消息
- **Shift+Enter**：换行（默认行为不阻止）

### 4.4 自动滚动

```typescript
watch(
  () => chatStore.messages.length,
  async () => {
    await nextTick()
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  },
)
```

监听消息数量变化，在 DOM 更新后（`nextTick`）自动滚动到底部。

### 4.5 模板结构

#### 连接状态栏

```html
<div class="status-bar" :class="{ connected: chatStore.isConnected }">
  <span class="status-dot" />
  {{ chatStore.isConnected ? 'Connected' : 'Disconnected' }}
  <button v-if="!chatStore.isConnected" class="btn-retry"
          @click="chatStore.checkConnection">Retry</button>
  <button class="btn-clear" @click="chatStore.clearMessages">Clear</button>
</div>
```

- 红/绿色圆点指示连接状态
- 断开时显示 Retry 按钮
- Clear 按钮始终可见

#### 消息列表

```html
<div ref="messagesContainer" class="messages">
  <!-- 空状态 -->
  <div v-if="chatStore.messages.length === 0" class="empty-state">
    <h2>ReAct Agent</h2>
    <p>Ask me to perform calculations or answer questions!</p>
  </div>

  <!-- 消息循环 -->
  <div v-for="msg in chatStore.messages" :key="msg.id"
       class="message" :class="msg.role">
    <div class="message-header">
      {{ msg.role === 'user' ? 'You' : 'Agent' }}
    </div>

    <!-- 工具调用展示 -->
    <div v-if="msg.toolCalls && msg.toolCalls.length > 0" class="tool-calls">
      <details v-for="(tc, i) in msg.toolCalls" :key="i" class="tool-call" open>
        <summary>
          <span class="tool-status" :class="tc.status">
            {{ tc.status === 'running' ? '⏳' : '✅' }}
          </span>
          Tool: {{ tc.name }}
        </summary>
        <div class="tool-detail">
          <div class="tool-input">
            <strong>Input:</strong>
            <code>{{ JSON.stringify(tc.input) }}</code>
          </div>
          <div v-if="tc.output" class="tool-output">
            <strong>Output:</strong>
            <code>{{ tc.output }}</code>
          </div>
        </div>
      </details>
    </div>

    <!-- 消息正文 -->
    <div class="message-content">{{ msg.content }}</div>
  </div>

  <!-- 加载指示器 -->
  <div v-if="chatStore.isLoading" class="loading-indicator">
    <span class="dot-pulse" />
  </div>
</div>
```

**工具调用可视化：**
- 使用 HTML 原生 `<details>` 标签实现折叠/展开
- 默认 `open` 展开状态
- 状态图标：`⏳`（running）/ `✅`（completed）
- 显示工具名称、JSON 格式的输入参数、执行结果

#### 输入区域

```html
<div class="input-area">
  <textarea v-model="inputText"
            placeholder="Type your message..."
            rows="1"
            :disabled="chatStore.isLoading"
            @keydown="handleKeydown" />
  <button class="btn-send"
          :disabled="!inputText.trim() || chatStore.isLoading"
          @click="handleSend">Send</button>
</div>
```

- `textarea` 高度固定为 1 行
- 加载时禁用输入和发送按钮
- 发送按钮在输入为空或加载中时禁用

#### 错误显示

```html
<div v-if="chatStore.error" class="error-bar">
  {{ chatStore.error }}
</div>
```

底部红色横条，显示最近的错误信息。

### 4.6 样式设计

组件使用 `<style scoped>` 作用域 CSS，主要设计特点：

| 元素 | 样式 |
|------|------|
| 整体布局 | Flexbox 垂直布局，最大宽度 800px 居中 |
| 用户消息 | 蓝色背景（`#007bff`），右对齐 |
| 助手消息 | 灰色背景（`#f0f0f0`），左对齐 |
| 工具调用卡片 | 浅蓝背景（`#e8f4f8`），圆角卡片 |
| 加载动画 | CSS `@keyframes pulse` 脉冲圆点 |
| 连接状态 | 红/绿色圆点（8px 圆形） |

---

## 5. 路由配置

**文件：** `packages/gui/src/router/index.ts`

```typescript
import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '../views/ChatView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'chat',
      component: ChatView,
    },
  ],
})

export default router
```

- 使用 HTML5 History 模式（`createWebHistory`）
- 当前仅一条路由：根路径 `/` → `ChatView` 组件
- 路由名称为 `'chat'`，可通过 `router.push({ name: 'chat' })` 编程式导航

---

## 6. Vite 配置与代理

**文件：** `packages/gui/vite.config.ts`

```typescript
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
```

### 6.1 插件

- `vue()`：Vue 3 SFC 编译支持
- `vueDevTools()`：Vue DevTools 集成

### 6.2 路径别名

`@` 映射到 `./src` 目录，简化导入路径：

```typescript
import { useChatStore } from '@/stores/chat'  // 等价于 ../stores/chat
```

### 6.3 开发代理

| 配置项 | 值 | 说明 |
|--------|-----|------|
| 匹配路径 | `/api` | 前缀匹配 |
| 目标 | `http://localhost:8000` | FastAPI 后端地址 |
| `changeOrigin` | `true` | 修改请求 Host 头 |
| `rewrite` | 去除 `/api` 前缀 | `/api/chat` → `/chat` |

**请求转发示例：**

```
前端请求: GET http://localhost:5173/api/health
代理转发: GET http://localhost:8000/health
```

这保证了前端代码中使用 `/api` 统一前缀，开发时由 Vite 代理转发，生产部署时可通过 Nginx 等反向代理实现相同效果。

---

## 7. TypeScript 配置

项目使用 strict 模式的 TypeScript，通过多个 `tsconfig` 文件组织：

| 文件 | 用途 |
|------|------|
| `tsconfig.json` | 根配置，引用其他配置 |
| `tsconfig.app.json` | 应用代码编译配置 |
| `tsconfig.node.json` | Node.js 相关（Vite 配置等） |
| `tsconfig.vitest.json` | 测试相关配置 |

---

## 8. 测试设置

### 8.1 单元测试

- **框架**：Vitest + jsdom
- **配置文件**：`vitest.config.ts`
- **测试文件位置**：
  - `src/api/__tests__/agent.spec.ts` — API 客户端测试
  - `src/stores/__tests__/chat.spec.ts` — Pinia Store 测试
  - `src/components/__tests__/` — 组件测试（预留）

### 8.2 E2E 测试

- **框架**：Playwright
- **配置文件**：`playwright.config.ts`
- **测试文件**：`e2e/vue.spec.ts`

---

## 9. 数据流全景

```
┌──────────────────────────────────────────────────────────┐
│                  ChatView.vue                             │
│  ┌──────────┐   handleSend()   ┌──────────────────────┐ │
│  │ textarea │ ─────────────────│ chatStore.sendMessage │ │
│  └──────────┘                  └──────────┬───────────┘ │
│       ▲                                   │              │
│       │ v-model                           ▼              │
│  ┌──────────┐              ┌──────────────────────────┐ │
│  │ inputText│              │    Pinia chat Store       │ │
│  └──────────┘              │  messages[]               │ │
│                            │  isLoading                │ │
│                            │  isConnected              │ │
│                            │  error                    │ │
│                            └──────────┬───────────────┘ │
│                                       │                  │
│  ┌────────────────────────────────────┤                  │
│  │ v-for="msg in messages"           │                  │
│  │   .message-content                 │                  │
│  │   .tool-calls                      │                  │
│  └────────────────────────────────────┘                  │
└──────────────────────────────────────────────────────────┘
                              │
                    streamMessage() (SSE)
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│              agent.ts (API Client)                        │
│  POST /api/chat/stream                                   │
│  ReadableStream → TextDecoder → SSE Parse → yield Event │
└──────────────────────────────────────────────────────────┘
                              │
                     Vite Proxy (/api → :8000)
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│              FastAPI Server (server.py)                   │
│  POST /chat/stream → ReactAgent.stream()                 │
│  → StreamingResponse (text/event-stream)                 │
└──────────────────────────────────────────────────────────┘
```
