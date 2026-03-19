import { ref } from 'vue'
import { defineStore } from 'pinia'
import { streamMessage, checkHealth } from '@/api/agent'

/** A single message in the chat. */
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  toolCalls?: ToolCallInfo[]
  timestamp: Date
}

/** Information about a tool call during agent reasoning. */
export interface ToolCallInfo {
  name: string
  input: Record<string, unknown>
  output?: string
  status: 'running' | 'completed' | 'error'
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const isLoading = ref(false)
  const isConnected = ref(false)
  const error = ref<string | null>(null)

  let messageCounter = 0

  function generateId(): string {
    return `msg-${Date.now()}-${messageCounter++}`
  }

  /** Check backend connectivity. */
  async function checkConnection(): Promise<void> {
    isConnected.value = await checkHealth()
  }

  /** Send a message and stream the response. */
  async function sendMessage(content: string): Promise<void> {
    if (!content.trim() || isLoading.value) return

    error.value = null

    // Add user message
    const userMsg: ChatMessage = {
      id: generateId(),
      role: 'user',
      content: content.trim(),
      timestamp: new Date(),
    }
    messages.value.push(userMsg)

    // Create assistant message placeholder
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

  /** Clear all messages. */
  function clearMessages(): void {
    messages.value = []
  }

  return {
    messages,
    isLoading,
    isConnected,
    error,
    sendMessage,
    clearMessages,
    checkConnection,
  }
})
