import { ref } from 'vue'
import { defineStore } from 'pinia'
import { streamMessage, checkHealth, approveToolCall } from '@/api/agent'

/** A single message in the chat. */
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  toolCalls?: ToolCallInfo[]
  traceSteps?: TraceStep[]
  loopActive?: boolean
  timestamp: Date
}

/** Information about a tool call during agent reasoning. */
export interface ToolCallInfo {
  name: string
  input: Record<string, unknown>
  output?: string
  status: 'running' | 'completed' | 'error'
}

/** A step in the linear ReAct trace. */
export interface TraceStep {
  type: 'loop_start' | 'thinking' | 'tool_start' | 'tool_end' | 'loop_end' | 'approval_request'
  content?: string
  name?: string
  input?: Record<string, unknown>
  output?: string
}

/** Pending approval dialog state. */
export interface PendingApproval {
  toolName: string
  toolArgs: Record<string, unknown>
  toolCallId: string
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const isLoading = ref(false)
  const isConnected = ref(false)
  const error = ref<string | null>(null)
  const pendingApproval = ref<PendingApproval | null>(null)

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
      traceSteps: [],
      loopActive: false,
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

          case 'loop_start':
            assistantMsg.loopActive = true
            assistantMsg.traceSteps?.push({ type: 'loop_start' })
            break

          case 'thinking':
            assistantMsg.traceSteps?.push({
              type: 'thinking',
              content: event.content || '',
            })
            break

          case 'tool_start':
            assistantMsg.toolCalls?.push({
              name: event.name || 'unknown',
              input: event.input || {},
              status: 'running',
            })
            assistantMsg.traceSteps?.push({
              type: 'tool_start',
              name: event.name || 'unknown',
              input: event.input || {},
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
            assistantMsg.traceSteps?.push({
              type: 'tool_end',
              name: event.name || 'unknown',
              output: event.output || '',
            })
            break
          }

          case 'loop_end':
            assistantMsg.loopActive = false
            assistantMsg.traceSteps?.push({ type: 'loop_end' })
            break

          case 'approval_request':
            pendingApproval.value = {
              toolName: event.tool_name || 'unknown',
              toolArgs: event.tool_args || {},
              toolCallId: event.tool_call_id || '',
            }
            assistantMsg.traceSteps?.push({
              type: 'approval_request',
              name: event.tool_name || 'unknown',
              input: event.tool_args || {},
            })
            break
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

  /** Respond to a pending approval request. */
  async function respondToApproval(approved: boolean): Promise<void> {
    if (!pendingApproval.value) return
    try {
      await approveToolCall(pendingApproval.value.toolCallId, approved)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Approval request failed'
    } finally {
      pendingApproval.value = null
    }
  }

  return {
    messages,
    isLoading,
    isConnected,
    error,
    pendingApproval,
    sendMessage,
    clearMessages,
    checkConnection,
    respondToApproval,
  }
})
