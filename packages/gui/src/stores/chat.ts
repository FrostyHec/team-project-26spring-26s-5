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
import type { AgentEvent, SessionDetail, SessionInfo, SkillInfo } from '@/api/agent'
import {
  EVENT_TYPES,
  WIDGET_TYPES,
  TOOL_CALL_STATUS,
  TRACE_STEP_TYPES,
  SESSION_MESSAGE_ROLES,
  MESSAGE_ROLES,
  DEADLINE_MUTATING_TOOLS,
} from './chatConstants'
import type { WidgetType } from './chatConstants'
import type {
  ChatMessage,
  ToolCallInfo,
  TraceStep,
  PendingApproval,
  WidgetState,
  ChatSession,
} from './chatTypes'

// Re-export constants so consumers can import from '@/stores/chat' as before
export {
  EVENT_TYPES,
  WIDGET_TYPES,
  TOOL_CALL_STATUS,
  TRACE_STEP_TYPES,
  SESSION_MESSAGE_ROLES,
  MESSAGE_ROLES,
}
// Re-export types
export type { ChatMessage, ToolCallInfo, TraceStep, PendingApproval, WidgetState, ChatSession }

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
  const isSidebarCollapsed = ref(false)

  /**
   * Monotonically increasing counter bumped whenever a deadline-mutating
   * tool completes.  The DeadlinePanelWidget watches this to auto-refresh.
   */
  const deadlineVersion = ref(0)

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
      if (!activeSessionId.value && sessions.value.length > 0) {
        activeSessionId.value = sessions.value[0]!.id
      }
    } catch {
      // Fallback: keep local sessions
    }
  }

  /** Rebuild frontend message model from persisted session detail. */
  function buildMessagesFromSessionDetail(detail: SessionDetail): ChatMessage[] {
    const rebuilt: ChatMessage[] = []
    let currentAssistant: ChatMessage | null = null

    for (const msg of detail.messages) {
      if (msg.role === SESSION_MESSAGE_ROLES.HUMAN) {
        rebuilt.push({
          id: generateId(),
          role: MESSAGE_ROLES.USER,
          content: msg.content,
          timestamp: new Date(msg.created_at),
        })
        currentAssistant = null
        continue
      }

      if (!currentAssistant) {
        currentAssistant = {
          id: generateId(),
          role: MESSAGE_ROLES.ASSISTANT,
          content: '',
          toolCalls: [],
          traceSteps: [],
          loopActive: false,
          timestamp: new Date(msg.created_at),
        }
        rebuilt.push(currentAssistant)
      }

      if (msg.role === SESSION_MESSAGE_ROLES.AI) {
        if (msg.content) {
          currentAssistant.content += (currentAssistant.content ? '\n\n' : '') + msg.content
        }

        if (msg.tool_calls && Array.isArray(msg.tool_calls)) {
          for (const toolCall of msg.tool_calls) {
            const tc = toolCall as Record<string, any>
            const callName = tc.name || 'unknown'
            const callArgs = tc.args || {}
            if (!currentAssistant.toolCalls!.some((t) => t.name === callName)) {
              currentAssistant.toolCalls!.push({
                name: callName,
                input: callArgs,
                status: TOOL_CALL_STATUS.COMPLETED,
              })
              currentAssistant.traceSteps!.push({
                type: TRACE_STEP_TYPES.TOOL_START,
                name: callName,
                input: callArgs,
              })
            }
          }
        }
      } else if (msg.role === SESSION_MESSAGE_ROLES.TOOL) {
        const tools = currentAssistant.toolCalls || []
        const callName = tools[tools.length - 1]?.name || 'unknown'
        currentAssistant.traceSteps!.push({
          type: TRACE_STEP_TYPES.TOOL_END,
          name: callName,
          output: msg.content,
        })
        const tc = tools.find((t) => t.name === callName)
        if (tc) {
          tc.output = msg.content
        }
      }
    }

    return rebuilt
  }

  /** Refresh a session from backend persisted messages. */
  async function refreshSessionFromServer(sessionId: string): Promise<void> {
    const session = sessions.value.find((s) => s.id === sessionId)
    if (!session) return

    const detail = await getSession(sessionId)
    session.messages = buildMessagesFromSessionDetail(detail)
    session.title = detail.session.title || session.title
    session.updatedAt = new Date(detail.session.updated_at)
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

  /** Switch to an existing session, loading its history.
   * Restores the per-session widget state from the target session.
   */
  async function switchSession(sessionId: string): Promise<void> {
    // Save current widget state to the session we're leaving
    const oldSession = sessions.value.find((s) => s.id === activeSessionId.value)
    if (oldSession) {
      oldSession.widgetState = { ...activeWidget.value }
    }

    activeSessionId.value = sessionId

    // Restore widget state from the session we're entering
    const newSession = sessions.value.find((s) => s.id === sessionId)
    if (newSession?.widgetState) {
      activeWidget.value = { ...newSession.widgetState }
    } else {
      activeWidget.value = { type: WIDGET_TYPES.EMPTY, data: {} }
    }

    if (newSession && newSession.messages.length === 0) {
      // Load message history from backend
      try {
        await refreshSessionFromServer(sessionId)
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

  /** Send a message and stream the response.
   * @param content The message content to send.
   * @param language The language code for multi-language prompt selection (e.g., 'en' or 'zh').
   */
  async function sendMessage(content: string, language: string = 'en'): Promise<void> {
    if (!content.trim() || isLoading.value) return

    error.value = null

    // Ensure we have an active session
    if (!activeSessionId.value) {
      await newSession()
    }

    const currentSessionId = activeSessionId.value
    const session = activeSession.value
    if (!session) return

    // Add user message
    const userMsg: ChatMessage = {
      id: generateId(),
      role: MESSAGE_ROLES.USER,
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
      role: MESSAGE_ROLES.ASSISTANT,
      content: '',
      toolCalls: [],
      traceSteps: [],
      loopActive: false,
      timestamp: new Date(),
    }
    session.messages.push(assistantMsg)

    // IMPORTANT: After push, Vue wraps the object in a reactive Proxy inside
    // the array.  We must mutate through that proxy so changes are tracked.
    const reactiveMsg = session.messages[session.messages.length - 1]!

    isLoading.value = true
    let streamError = false

    try {
      for await (const event of streamMessage(
        content,
        currentSessionId ?? undefined,
        session.skill,
        language,
      )) {
        handleStreamEvent(event, reactiveMsg)
        // Check if this was an error event (from backend LLM failure, not a thrown exception)
        if (event.type === EVENT_TYPES.ERROR) {
          streamError = true
          error.value = event.content || 'Unknown error'
          if (!reactiveMsg.content) {
            reactiveMsg.content = 'Failed to get response.'
          }
        }
      }
    } catch (e) {
      streamError = true
      error.value = e instanceof Error ? e.message : 'Unknown error'
      reactiveMsg.content = reactiveMsg.content || 'Failed to get response.'
    } finally {
      isLoading.value = false
      session.updatedAt = new Date()
      // Only refresh from server if there was no stream error.
      // On stream error, messages were not persisted by the backend,
      // so refreshing would overwrite the local (failed) message with empty server state.
      if (streamError || !currentSessionId || currentSessionId.startsWith('local-')) {
        return
      }
      try {
        await refreshSessionFromServer(currentSessionId)
      } catch {
        // Best effort reconciliation, keep streamed view on failure
      }
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
        msg.traceSteps?.push({ type: TRACE_STEP_TYPES.LOOP_START })
        break

      case EVENT_TYPES.THINKING:
        msg.traceSteps?.push({
          type: TRACE_STEP_TYPES.THINKING,
          content: event.content || '',
        })
        break

      case EVENT_TYPES.TOOL_START:
        msg.toolCalls?.push({
          name: event.name || 'unknown',
          input: event.input || {},
          status: TOOL_CALL_STATUS.RUNNING,
        })
        msg.traceSteps?.push({
          type: TRACE_STEP_TYPES.TOOL_START,
          name: event.name || 'unknown',
          input: event.input || {},
        })
        break

      case EVENT_TYPES.TOOL_END: {
        const tc = msg.toolCalls?.find(
          (t) => t.name === event.name && t.status === TOOL_CALL_STATUS.RUNNING,
        )
        if (tc) {
          tc.output = event.output || ''
          tc.status = TOOL_CALL_STATUS.COMPLETED
        }
        // Bump deadline version so the panel auto-refreshes
        if (event.name && DEADLINE_MUTATING_TOOLS.has(event.name)) {
          deadlineVersion.value++
        }
        msg.traceSteps?.push({
          type: TRACE_STEP_TYPES.TOOL_END,
          name: event.name || 'unknown',
          output: event.output || '',
        })
        break
      }

      case EVENT_TYPES.LOOP_END:
        msg.loopActive = false
        msg.traceSteps?.push({ type: TRACE_STEP_TYPES.LOOP_END })
        break

      case EVENT_TYPES.APPROVAL_REQUEST:
        pendingApproval.value = {
          toolName: event.tool_name || 'unknown',
          toolArgs: event.tool_args || {},
          toolCallId: event.tool_call_id || '',
        }
        msg.traceSteps?.push({
          type: TRACE_STEP_TYPES.APPROVAL_REQUEST,
          name: event.tool_name || 'unknown',
          input: event.tool_args || {},
        })
        break

      case EVENT_TYPES.WIDGET_DISPLAY: {
        const wType = event.widget_type || WIDGET_TYPES.EMPTY
        // Calendar widget self-fetches deadlines from REST API.
        // Deadline_manager skill uses show_deadline_dashboard() tool.
        const SELF_FETCH_WIDGETS: ReadonlySet<string> = new Set([WIDGET_TYPES.CALENDAR])
        const newWidget = {
          type: wType,
          data: SELF_FETCH_WIDGETS.has(wType) ? {} : event.data || {},
        }
        activeWidget.value = newWidget
        // Persist widget state to the active session
        if (activeSession.value) {
          activeSession.value.widgetState = { ...newWidget }
        }
        isWorkspaceOpen.value = true
        msg.traceSteps?.push({
          type: TRACE_STEP_TYPES.WIDGET_DISPLAY,
          widgetType: event.widget_type,
          widgetData: event.data || {},
        })
        break
      }

      case EVENT_TYPES.ERROR:
        // Error events are handled in sendMessage via streamError flag
        break
    }
  }

  /** Switch the active widget manually (e.g., via @mention). */
  function setWidget(type: WidgetType, data: Record<string, unknown> = {}): void {
    activeWidget.value = { type, data }
    isWorkspaceOpen.value = true
  }

  /** Toggle the workspace panel. */
  function toggleWorkspace(): void {
    isWorkspaceOpen.value = !isWorkspaceOpen.value
  }

  /** Toggle the session sidebar collapse state. */
  function toggleSidebar(): void {
    isSidebarCollapsed.value = !isSidebarCollapsed.value
  }

  /** Set sidebar collapse state explicitly. */
  function setSidebarCollapsed(collapsed: boolean): void {
    isSidebarCollapsed.value = collapsed
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
    isSidebarCollapsed,
    skills,
    deadlineVersion,
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
    toggleSidebar,
    setSidebarCollapsed,
    clearMessages,
    respondToApproval,
  }
})
