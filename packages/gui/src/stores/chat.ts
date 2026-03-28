import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import {
  streamMessage,
  checkHealth,
  approveToolCall,
  listSessions,
  createSession,
  getSession,
  deleteSession as apiDeleteSession,
  fetchSkills,
} from '@/api/agent'
import type { AgentEvent, SessionInfo, SkillInfo } from '@/api/agent'

// ---------- Enums / Constants ----------

/** Event types matching backend EventType StrEnum. */
export const EVENT_TYPES = {
  TOKEN: 'token',
  TOOL_START: 'tool_start',
  TOOL_END: 'tool_end',
  THINKING: 'thinking',
  LOOP_START: 'loop_start',
  LOOP_END: 'loop_end',
  APPROVAL_REQUEST: 'approval_request',
  WIDGET_DISPLAY: 'widget_display',
  ERROR: 'error',
} as const

/** Widget types matching backend WidgetType StrEnum. */
export const WIDGET_TYPES = {
  CALENDAR: 'calendar',
  DOCUMENT: 'document',
  WEB_PREVIEW: 'web_preview',
  COURSE_CARDS: 'course_cards',
  SOURCES: 'sources',
  INBOX: 'inbox',
  EMPTY: 'empty',
} as const

// ---------- Interfaces ----------

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
  type:
    | 'loop_start'
    | 'thinking'
    | 'tool_start'
    | 'tool_end'
    | 'loop_end'
    | 'approval_request'
    | 'widget_display'
  content?: string
  name?: string
  input?: Record<string, unknown>
  output?: string
  widgetType?: string
  widgetData?: Record<string, unknown>
}

/** Pending approval dialog state. */
export interface PendingApproval {
  toolName: string
  toolArgs: Record<string, unknown>
  toolCallId: string
}

/** Widget display state for the right panel. */
export interface WidgetState {
  type: string
  data: Record<string, unknown>
}

/** A chat session with messages. */
export interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
  skill?: string
  createdAt: Date
  updatedAt: Date
}

// ---------- Store ----------

export const useChatStore = defineStore('chat', () => {
  // Session management
  const sessions = ref<ChatSession[]>([])
  const activeSessionId = ref<string | null>(null)
  const sessionList = ref<SessionInfo[]>([])

  // Chat state
  const isLoading = ref(false)
  const isConnected = ref(false)
  const error = ref<string | null>(null)
  const pendingApproval = ref<PendingApproval | null>(null)

  // Widget state
  const activeWidget = ref<WidgetState>({ type: WIDGET_TYPES.EMPTY, data: {} })
  const isWorkspaceOpen = ref(true)

  // Skills
  const skills = ref<SkillInfo[]>([])

  let messageCounter = 0

  function generateId(): string {
    return `msg-${Date.now()}-${messageCounter++}`
  }

  /** Currently active session. */
  const activeSession = computed<ChatSession | null>(() => {
    if (!activeSessionId.value) return null
    return sessions.value.find((s) => s.id === activeSessionId.value) ?? null
  })

  /** Messages for the active session. */
  const messages = computed<ChatMessage[]>(() => {
    return activeSession.value?.messages ?? []
  })

  // ---- Skills ----

  /** Load available skills from backend. */
  async function loadSkills(): Promise<void> {
    try {
      skills.value = await fetchSkills()
    } catch {
      // Skills are optional, don't error
    }
  }

  // ---- Connection ----

  async function checkConnection(): Promise<void> {
    isConnected.value = await checkHealth()
  }

  // ---- Session Management ----

  /** Load sessions from backend. */
  async function loadSessions(): Promise<void> {
    try {
      sessionList.value = await listSessions()
      // Sync local sessions with remote
      for (const remote of sessionList.value) {
        if (!sessions.value.find((s) => s.id === remote.id)) {
          sessions.value.push({
            id: remote.id,
            title: remote.title || 'New Chat',
            messages: [],
            createdAt: new Date(remote.created_at),
            updatedAt: new Date(remote.updated_at),
          })
        }
      }
    } catch {
      // Fallback: keep local sessions
    }
  }

  /** Create a new session and switch to it. */
  async function newSession(skill?: string): Promise<string> {
    try {
      const remote = await createSession('')
      const session: ChatSession = {
        id: remote.id,
        title: 'New Chat',
        messages: [],
        skill,
        createdAt: new Date(remote.created_at),
        updatedAt: new Date(remote.updated_at),
      }
      sessions.value.unshift(session)
      activeSessionId.value = session.id
      activeWidget.value = { type: WIDGET_TYPES.EMPTY, data: {} }
      return session.id
    } catch {
      // Fallback: create local-only session
      const id = `local-${Date.now()}`
      const session: ChatSession = {
        id,
        title: 'New Chat',
        messages: [],
        skill,
        createdAt: new Date(),
        updatedAt: new Date(),
      }
      sessions.value.unshift(session)
      activeSessionId.value = id
      return id
    }
  }

  /** Switch to an existing session, loading its history. */
  async function switchSession(sessionId: string): Promise<void> {
    activeSessionId.value = sessionId
    activeWidget.value = { type: WIDGET_TYPES.EMPTY, data: {} }

    const session = sessions.value.find((s) => s.id === sessionId)
    if (session && session.messages.length === 0) {
      // Load message history from backend
      try {
        const detail = await getSession(sessionId)
        for (const msg of detail.messages) {
          session.messages.push({
            id: generateId(),
            role: msg.role === 'human' ? 'user' : 'assistant',
            content: msg.content,
            timestamp: new Date(msg.created_at),
          })
        }
        session.title = detail.session.title || session.title
      } catch {
        // Session might not exist in backend
      }
    }
  }

  /** Delete a session. */
  async function removeSession(sessionId: string): Promise<void> {
    try {
      await apiDeleteSession(sessionId)
    } catch {
      // Local delete even if remote fails
    }
    sessions.value = sessions.value.filter((s) => s.id !== sessionId)
    if (activeSessionId.value === sessionId) {
      activeSessionId.value = sessions.value[0]?.id ?? null
    }
  }

  // ---- Chat ----

  /** Send a message and stream the response. */
  async function sendMessage(content: string): Promise<void> {
    if (!content.trim() || isLoading.value) return

    error.value = null

    // Ensure we have an active session
    if (!activeSessionId.value) {
      await newSession()
    }

    const session = activeSession.value
    if (!session) return

    // Add user message
    const userMsg: ChatMessage = {
      id: generateId(),
      role: 'user',
      content: content.trim(),
      timestamp: new Date(),
    }
    session.messages.push(userMsg)

    // Update title from first message
    if (session.messages.length === 1) {
      session.title = content.trim().slice(0, 60) || 'New Chat'
    }

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
    session.messages.push(assistantMsg)

    isLoading.value = true

    try {
      for await (const event of streamMessage(
        content,
        activeSessionId.value ?? undefined,
        session.skill,
      )) {
        handleStreamEvent(event, assistantMsg)
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
      assistantMsg.content = assistantMsg.content || 'Failed to get response.'
    } finally {
      isLoading.value = false
      session.updatedAt = new Date()
    }
  }

  /** Process a single stream event. */
  function handleStreamEvent(event: AgentEvent, msg: ChatMessage): void {
    switch (event.type) {
      case EVENT_TYPES.TOKEN:
        msg.content += event.content || ''
        break

      case EVENT_TYPES.LOOP_START:
        msg.loopActive = true
        msg.traceSteps?.push({ type: 'loop_start' })
        break

      case EVENT_TYPES.THINKING:
        msg.traceSteps?.push({
          type: 'thinking',
          content: event.content || '',
        })
        break

      case EVENT_TYPES.TOOL_START:
        msg.toolCalls?.push({
          name: event.name || 'unknown',
          input: event.input || {},
          status: 'running',
        })
        msg.traceSteps?.push({
          type: 'tool_start',
          name: event.name || 'unknown',
          input: event.input || {},
        })
        break

      case EVENT_TYPES.TOOL_END: {
        const tc = msg.toolCalls?.find((t) => t.name === event.name && t.status === 'running')
        if (tc) {
          tc.output = event.output || ''
          tc.status = 'completed'
        }
        msg.traceSteps?.push({
          type: 'tool_end',
          name: event.name || 'unknown',
          output: event.output || '',
        })
        break
      }

      case EVENT_TYPES.LOOP_END:
        msg.loopActive = false
        msg.traceSteps?.push({ type: 'loop_end' })
        break

      case EVENT_TYPES.APPROVAL_REQUEST:
        pendingApproval.value = {
          toolName: event.tool_name || 'unknown',
          toolArgs: event.tool_args || {},
          toolCallId: event.tool_call_id || '',
        }
        msg.traceSteps?.push({
          type: 'approval_request',
          name: event.tool_name || 'unknown',
          input: event.tool_args || {},
        })
        break

      case EVENT_TYPES.WIDGET_DISPLAY:
        activeWidget.value = {
          type: event.widget_type || WIDGET_TYPES.EMPTY,
          data: event.data || {},
        }
        isWorkspaceOpen.value = true
        msg.traceSteps?.push({
          type: 'widget_display',
          widgetType: event.widget_type,
          widgetData: event.data || {},
        })
        break
    }
  }

  /** Switch the active widget manually (e.g., via @mention). */
  function setWidget(type: string, data: Record<string, unknown> = {}): void {
    activeWidget.value = { type, data }
    isWorkspaceOpen.value = true
  }

  /** Toggle the workspace panel. */
  function toggleWorkspace(): void {
    isWorkspaceOpen.value = !isWorkspaceOpen.value
  }

  /** Clear all messages in active session. */
  function clearMessages(): void {
    if (activeSession.value) {
      activeSession.value.messages = []
    }
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
    // State
    sessions,
    activeSessionId,
    sessionList,
    isLoading,
    isConnected,
    error,
    pendingApproval,
    activeWidget,
    isWorkspaceOpen,
    skills,
    // Computed
    activeSession,
    messages,
    // Actions
    loadSkills,
    checkConnection,
    loadSessions,
    newSession,
    switchSession,
    removeSession,
    sendMessage,
    handleStreamEvent,
    setWidget,
    toggleWorkspace,
    clearMessages,
    respondToApproval,
  }
})
