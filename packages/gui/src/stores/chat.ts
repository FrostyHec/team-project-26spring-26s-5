import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import {
  FALLBACK_MODES,
  streamMessage,
  checkHealth,
  approveToolCall,
  interruptSession,
  persistPartialResponse,
  listSessions,
  createSession,
  getSession,
  selectSessionVersion,
  retrySessionNode,
  editSessionNode,
  deleteSession as apiDeleteSession,
  fetchSkills,
  updateSession as apiUpdateSession,
  updateSessionPreferences as apiUpdateSessionPreferences,
} from '@/api/agent'
import type {
  AgentEvent,
  FallbackMode,
  SessionDetail,
  SessionInfo,
  SessionNode,
  SkillInfo,
  UpdateSessionPreferencesRequest,
} from '@/api/agent'
import {
  EVENT_TYPES,
  WIDGET_TYPES,
  MESSAGE_STATUSES,
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
  ChatSessionNode,
  ChatVersionChoice,
  ChatVersionGroup,
} from './chatTypes'

// Re-export constants so consumers can import from '@/stores/chat' as before
export {
  EVENT_TYPES,
  WIDGET_TYPES,
  MESSAGE_STATUSES,
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
  const selectedProviderId = ref<string | null>(null)
  const fallbackMode = ref<FallbackMode>(FALLBACK_MODES.MANUAL)

  // Chat state
  const isLoading = ref(false)
  const isInterrupting = ref(false)
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
  let currentAbortController: AbortController | null = null
  let currentStreamingUserContent: string | null = null
  let currentStreamingAssistantId: string | null = null
  let interruptedByUser = false
  const pendingSessionTitleRefreshes = new Set<string>()
  const GENERATED_TITLE_POLL_DELAYS_MS = [1000, 2000, 4000]

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

  function syncActiveSessionPreferences(session: ChatSession | null): void {
    selectedProviderId.value = session?.selectedProviderId ?? null
    fallbackMode.value = session?.fallbackMode ?? FALLBACK_MODES.MANUAL
  }

  function isBlankSession(session: ChatSession | null | undefined): boolean {
    return !!session && session.messages.length === 0
  }

  function shouldScheduleGeneratedTitleRefresh(session: ChatSession | null | undefined): boolean {
    return !!session && session.title === 'New Chat' && session.messages.length === 2
  }

  function isAwaitingGeneratedTitle(session: ChatSession | null | undefined): boolean {
    return !!session && session.title === 'New Chat'
  }

  function wait(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms))
  }

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
            visiblePath: [],
            versionGroups: [],
            nodeMap: {},
            selectedProviderId: remote.selected_provider_id ?? null,
            fallbackMode: remote.fallback_mode ?? FALLBACK_MODES.MANUAL,
            createdAt: new Date(remote.created_at),
            updatedAt: new Date(remote.updated_at),
          })
        }
      }
      if (!activeSessionId.value && sessions.value.length > 0) {
        activeSessionId.value = sessions.value[0]!.id
        syncActiveSessionPreferences(sessions.value[0] ?? null)
      }
    } catch {
      // Fallback: keep local sessions
    }
  }

  /** Rebuild frontend message model from persisted session detail. */
  function buildMessagesFromSessionDetail(detail: SessionDetail): ChatMessage[] {
    const nodeMap = buildNodeMap(detail)
    const versionGroups = detail.version_groups ?? []
    const visiblePath = detail.visible_path ?? []
    const groupMap = new Map(versionGroups.map((group) => [group.version_group_id, group]))
    const rebuilt: ChatMessage[] = []
    let currentAssistant: ChatMessage | null = null

    for (const [index, msg] of detail.messages.entries()) {
      const nodeId = visiblePath[index]
      const node = nodeId ? nodeMap[nodeId] : undefined
      const versionGroup = node ? groupMap.get(node.versionGroupId) : undefined
      const versionChoices = versionGroup
        ? versionGroup.node_ids
            .map((choiceNodeId) => {
              const choiceNode = nodeMap[choiceNodeId]
              if (!choiceNode) return null
              const choice: ChatVersionChoice = {
                nodeId: choiceNode.id,
                role: choiceNode.role,
                versionIndex: choiceNode.versionIndex,
                sourceKind: choiceNode.sourceKind,
              }
              return choice
            })
            .filter((choice): choice is ChatVersionChoice => choice !== null)
            .sort((left, right) => left.versionIndex - right.versionIndex)
        : undefined

      if (msg.role === SESSION_MESSAGE_ROLES.HUMAN) {
        rebuilt.push({
          id: nodeId ?? generateId(),
          role: MESSAGE_ROLES.USER,
          content: msg.content,
          status: msg.status,
          nodeId,
          sourceKind: node?.sourceKind,
          sourceNodeId: node?.sourceNodeId,
          versionGroupId: node?.versionGroupId,
          versionIndex: node?.versionIndex,
          selectedVersionId: versionGroup?.selected_node_id,
          versionChoices,
          canEdit: !!nodeId,
          canRetry: false,
          timestamp: new Date(msg.created_at),
        })
        currentAssistant = null
        continue
      }

      if (!currentAssistant) {
        const persistedToolCalls = node?.toolCalls?.map(
          (toolCall): ToolCallInfo => ({
            name: toolCall.name,
            input: { ...(toolCall.input ?? {}) },
            output: toolCall.output,
            status: toolCall.status,
          }),
        )
        const persistedTraceSteps = node?.traceSteps?.map(
          (step): TraceStep => ({
            type: step.type,
            content: step.content,
            name: step.name,
            input: step.input ? { ...step.input } : undefined,
            output: step.output,
            fromProviderId: step.fromProviderId,
            toProviderId: step.toProviderId,
            widgetType: step.widgetType,
            widgetData: step.widgetData ? { ...step.widgetData } : undefined,
          }),
        )
        currentAssistant = {
          id: nodeId ?? generateId(),
          role: MESSAGE_ROLES.ASSISTANT,
          content: '',
          status: msg.status,
          nodeId,
          sourceKind: node?.sourceKind,
          sourceNodeId: node?.sourceNodeId,
          versionGroupId: node?.versionGroupId,
          versionIndex: node?.versionIndex,
          selectedVersionId: versionGroup?.selected_node_id,
          versionChoices,
          canEdit: !!nodeId,
          canRetry: !!nodeId && node?.status !== 'streaming',
          toolCalls: persistedToolCalls ?? [],
          traceSteps: persistedTraceSteps ?? [],
          loopActive: persistedTraceSteps?.some((step) => step.type === TRACE_STEP_TYPES.LOOP_START)
            ? persistedTraceSteps[persistedTraceSteps.length - 1]?.type !==
              TRACE_STEP_TYPES.LOOP_END
            : false,
          timestamp: new Date(msg.created_at),
        }
        rebuilt.push(currentAssistant)
      }

      if (msg.role === SESSION_MESSAGE_ROLES.AI) {
        if (msg.content) {
          currentAssistant.content += (currentAssistant.content ? '\n\n' : '') + msg.content
        }
        currentAssistant.status = msg.status

        if (
          (!node?.toolCalls || node.toolCalls.length === 0) &&
          msg.tool_calls &&
          Array.isArray(msg.tool_calls)
        ) {
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
      } else if (
        msg.role === SESSION_MESSAGE_ROLES.TOOL &&
        (!node?.traceSteps || node.traceSteps.length === 0)
      ) {
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

  function buildNodeMap(detail: SessionDetail): Record<string, ChatSessionNode> {
    return Object.fromEntries(
      (detail.nodes ?? []).map((node) => [
        node.id,
        {
          id: node.id,
          parentId: node.parent_id ?? null,
          role: node.role,
          content: node.content,
          status: node.status,
          versionGroupId: node.version_group_id,
          versionIndex: node.version_index,
          sourceKind: node.source_kind,
          sourceNodeId: node.source_node_id ?? null,
          responseToNodeId: node.response_to_node_id ?? null,
          toolCalls: mapPersistedToolCalls(node),
          traceSteps: mapPersistedTraceSteps(node),
        },
      ]),
    )
  }

  function mapPersistedToolCalls(node: SessionNode): ToolCallInfo[] | undefined {
    if (!node.tool_calls?.length) {
      return undefined
    }
    return node.tool_calls.map((toolCall) => ({
      name: toolCall.name,
      input: { ...(toolCall.input ?? {}) },
      output: toolCall.output,
      status:
        toolCall.status === TOOL_CALL_STATUS.RUNNING
          ? TOOL_CALL_STATUS.RUNNING
          : TOOL_CALL_STATUS.COMPLETED,
    }))
  }

  function mapPersistedTraceSteps(node: SessionNode): TraceStep[] | undefined {
    if (!node.trace_steps?.length) {
      return undefined
    }
    return node.trace_steps.map(
      (step): TraceStep => ({
        type: step.type,
        content: step.content,
        name: step.name,
        input: step.input ? { ...step.input } : undefined,
        output: step.output,
        fromProviderId: step.fromProviderId,
        toProviderId: step.toProviderId,
        widgetType: step.widgetType,
        widgetData: step.widgetData ? { ...step.widgetData } : undefined,
      }),
    )
  }

  function buildVersionGroups(detail: SessionDetail): ChatVersionGroup[] {
    return (detail.version_groups ?? []).map((group) => ({
      versionGroupId: group.version_group_id,
      nodeIds: [...group.node_ids],
      selectedNodeId: group.selected_node_id,
      positionInPath: group.position_in_path,
    }))
  }

  function applySessionDetail(session: ChatSession, detail: SessionDetail): void {
    session.messages = buildMessagesFromSessionDetail(detail)
    session.visiblePath = [...(detail.visible_path ?? [])]
    session.versionGroups = buildVersionGroups(detail)
    session.nodeMap = buildNodeMap(detail)
    session.title = detail.session.title || session.title
    session.selectedProviderId = detail.session.selected_provider_id ?? null
    session.fallbackMode = detail.session.fallback_mode ?? FALLBACK_MODES.MANUAL
    session.updatedAt = new Date(detail.session.updated_at)

    const summary = sessionList.value.find((item) => item.id === detail.session.id)
    if (summary) {
      summary.title = detail.session.title
      summary.updated_at = detail.session.updated_at
      summary.selected_provider_id = detail.session.selected_provider_id ?? null
      summary.fallback_mode = detail.session.fallback_mode ?? FALLBACK_MODES.MANUAL
    }
  }

  /** Refresh a session from backend persisted messages. */
  async function refreshSessionFromServer(sessionId: string): Promise<void> {
    const session = sessions.value.find((s) => s.id === sessionId)
    if (!session) return

    const detail = await getSession(sessionId)
    applySessionDetail(session, detail)
    if (activeSessionId.value === sessionId) {
      syncActiveSessionPreferences(session)
    }
  }

  function scheduleGeneratedTitleRefresh(sessionId: string): void {
    if (pendingSessionTitleRefreshes.has(sessionId)) {
      return
    }

    pendingSessionTitleRefreshes.add(sessionId)
    void (async () => {
      try {
        for (const delayMs of GENERATED_TITLE_POLL_DELAYS_MS) {
          await wait(delayMs)
          const session = sessions.value.find((item) => item.id === sessionId)
          if (!isAwaitingGeneratedTitle(session)) {
            return
          }
          try {
            await refreshSessionFromServer(sessionId)
          } catch {
            // Best effort polling; keep the current title until the next attempt.
          }
          const refreshed = sessions.value.find((item) => item.id === sessionId)
          if (!isAwaitingGeneratedTitle(refreshed)) {
            return
          }
        }
      } finally {
        pendingSessionTitleRefreshes.delete(sessionId)
      }
    })()
  }

  /** Create a new session and switch to it. */
  async function newSession(skill?: string): Promise<string> {
    const reusable = sessions.value.find((session) => isBlankSession(session))
    if (reusable) {
      reusable.skill = skill
      activeSessionId.value = reusable.id
      activeWidget.value = { type: WIDGET_TYPES.EMPTY, data: {} }
      syncActiveSessionPreferences(reusable)
      return reusable.id
    }

    try {
      const remote = await createSession('')
      const session: ChatSession = {
        id: remote.id,
        title: 'New Chat',
        messages: [],
        visiblePath: [],
        versionGroups: [],
        nodeMap: {},
        skill,
        selectedProviderId: selectedProviderId.value,
        fallbackMode: fallbackMode.value,
        createdAt: new Date(remote.created_at),
        updatedAt: new Date(remote.updated_at),
      }
      sessions.value.unshift(session)
      activeSessionId.value = session.id
      activeWidget.value = { type: WIDGET_TYPES.EMPTY, data: {} }
      syncActiveSessionPreferences(session)
      if (selectedProviderId.value || fallbackMode.value !== FALLBACK_MODES.MANUAL) {
        await updateActiveSessionPreferences({
          selected_provider_id: selectedProviderId.value,
          fallback_mode: fallbackMode.value,
        })
      }
      return session.id
    } catch {
      // Fallback: create local-only session
      const id = `local-${Date.now()}`
      const session: ChatSession = {
        id,
        title: 'New Chat',
        messages: [],
        visiblePath: [],
        versionGroups: [],
        nodeMap: {},
        skill,
        selectedProviderId: selectedProviderId.value,
        fallbackMode: fallbackMode.value,
        createdAt: new Date(),
        updatedAt: new Date(),
      }
      sessions.value.unshift(session)
      activeSessionId.value = id
      syncActiveSessionPreferences(session)
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
    syncActiveSessionPreferences(newSession ?? null)

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
      status: MESSAGE_STATUSES.COMPLETED,
      timestamp: new Date(),
    }
    session.messages.push(userMsg)

    // Create assistant message placeholder
    const assistantMsg: ChatMessage = {
      id: generateId(),
      role: MESSAGE_ROLES.ASSISTANT,
      content: '',
      status: MESSAGE_STATUSES.COMPLETED,
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
    interruptedByUser = false
    await streamIntoAssistant(session, reactiveMsg, content.trim(), language)
  }

  async function streamIntoAssistant(
    session: ChatSession,
    msg: ChatMessage,
    requestMessage: string,
    language: string,
  ): Promise<void> {
    const currentSessionId = session.id
    currentAbortController = new AbortController()
    currentStreamingUserContent = requestMessage
    currentStreamingAssistantId = msg.id
    let streamError = false

    try {
      for await (const event of streamMessage(
        requestMessage,
        currentSessionId,
        session.skill,
        language,
        session.selectedProviderId ?? selectedProviderId.value ?? undefined,
        currentAbortController.signal,
      )) {
        handleStreamEvent(event, msg)
        if (event.type === EVENT_TYPES.ERROR || event.type === EVENT_TYPES.FAILED) {
          streamError = true
          msg.status = MESSAGE_STATUSES.FAILED
          error.value = event.content || 'Unknown error'
          if (!msg.content) {
            msg.content = 'Failed to get response.'
          }
        }
      }
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError' && interruptedByUser) {
        msg.status = MESSAGE_STATUSES.INTERRUPTED
        msg.loopActive = false
      } else {
        streamError = true
        msg.status = MESSAGE_STATUSES.FAILED
        error.value = e instanceof Error ? e.message : 'Unknown error'
        msg.content = msg.content || 'Failed to get response.'
      }
    } finally {
      const pendingUserContent = currentStreamingUserContent
      isLoading.value = false
      isInterrupting.value = false
      currentAbortController = null
      currentStreamingUserContent = null
      currentStreamingAssistantId = null
      session.updatedAt = new Date()

      if (
        streamError &&
        currentSessionId &&
        !currentSessionId.startsWith('local-') &&
        pendingUserContent !== null
      ) {
        try {
          await persistPartialResponse(currentSessionId, {
            user_message: pendingUserContent,
            assistant_content: msg.content,
            assistant_status: MESSAGE_STATUSES.FAILED,
          })
        } catch {
          // Keep the local failed message if persistence also fails.
        }
      }

      if (
        streamError ||
        interruptedByUser ||
        !currentSessionId ||
        currentSessionId.startsWith('local-')
      ) {
        return
      }
      try {
        await refreshSessionFromServer(currentSessionId)
        const refreshedSession = sessions.value.find((item) => item.id === currentSessionId)
        if (shouldScheduleGeneratedTitleRefresh(refreshedSession)) {
          scheduleGeneratedTitleRefresh(currentSessionId)
        }
      } catch {
        // Best effort reconciliation, keep streamed view on failure
      }
    }
  }

  async function continuePendingAssistant(language: string = 'en'): Promise<void> {
    const session = activeSession.value
    if (!session || isLoading.value || session.id.startsWith('local-')) {
      return
    }

    const pendingAssistant = [...session.messages]
      .reverse()
      .find((message) => message.role === MESSAGE_ROLES.ASSISTANT && message.status === 'streaming')
    if (!pendingAssistant) {
      return
    }

    error.value = null
    isLoading.value = true
    interruptedByUser = false
    await streamIntoAssistant(session, pendingAssistant, '', language)
  }

  async function stopStreaming(): Promise<void> {
    if (!isLoading.value || !currentAbortController || !activeSession.value) {
      return
    }

    interruptedByUser = true
    isInterrupting.value = true
    currentAbortController.abort()

    const session = activeSession.value
    const assistantMessage = session.messages.find(
      (message) => message.id === currentStreamingAssistantId,
    )
    if (assistantMessage) {
      assistantMessage.status = MESSAGE_STATUSES.INTERRUPTED
      assistantMessage.loopActive = false
    }

    if (currentStreamingUserContent === null || session.id.startsWith('local-')) {
      return
    }

    try {
      await interruptSession(session.id, {
        user_message: currentStreamingUserContent,
        assistant_content: assistantMessage?.content || '',
      })
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to interrupt stream'
    }
  }

  function setSelectedProvider(providerId: string | null): void {
    selectedProviderId.value = providerId
  }

  async function updateActiveSessionPreferences(
    request: UpdateSessionPreferencesRequest,
  ): Promise<void> {
    const session = activeSession.value
    if (!session) {
      if (request.selected_provider_id !== undefined) {
        selectedProviderId.value = request.selected_provider_id
      }
      if (request.fallback_mode !== undefined) {
        fallbackMode.value = request.fallback_mode
      }
      return
    }

    if (request.selected_provider_id !== undefined) {
      session.selectedProviderId = request.selected_provider_id
      selectedProviderId.value = request.selected_provider_id
    }
    if (request.fallback_mode !== undefined) {
      session.fallbackMode = request.fallback_mode
      fallbackMode.value = request.fallback_mode
    }

    if (session.id.startsWith('local-')) {
      return
    }

    try {
      const updated = await apiUpdateSessionPreferences(session.id, request)
      session.selectedProviderId = updated.selected_provider_id ?? null
      session.fallbackMode = updated.fallback_mode ?? FALLBACK_MODES.MANUAL
      selectedProviderId.value = session.selectedProviderId
      fallbackMode.value = session.fallbackMode
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to update session preferences'
    }
  }

  async function renameSession(sessionId: string, title: string): Promise<void> {
    const session = sessions.value.find((item) => item.id === sessionId)
    if (!session) {
      return
    }

    const trimmedTitle = title.trim()
    session.title = trimmedTitle || 'New Chat'
    session.updatedAt = new Date()

    if (session.id.startsWith('local-')) {
      return
    }

    try {
      const updated = await apiUpdateSession(session.id, { title: trimmedTitle })
      session.title = updated.title || 'New Chat'
      session.updatedAt = new Date(updated.updated_at)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to rename session'
    }
  }

  async function selectVersion(versionGroupId: string, nodeId: string): Promise<void> {
    const session = activeSession.value
    if (!session || isLoading.value || session.id.startsWith('local-')) {
      return
    }

    try {
      const detail = await selectSessionVersion(session.id, versionGroupId, nodeId)
      applySessionDetail(session, detail)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to switch version'
    }
  }

  async function retryMessage(nodeId: string, language: string = 'en'): Promise<void> {
    const session = activeSession.value
    if (!session || isLoading.value || session.id.startsWith('local-')) {
      return
    }

    error.value = null
    try {
      const detail = await retrySessionNode(session.id, nodeId)
      applySessionDetail(session, detail)
      await continuePendingAssistant(language)
    } catch (e) {
      isLoading.value = false
      error.value = e instanceof Error ? e.message : 'Failed to retry message'
    }
  }

  async function editMessage(
    nodeId: string,
    content: string,
    language: string = 'en',
  ): Promise<void> {
    const session = activeSession.value
    if (!session || isLoading.value || session.id.startsWith('local-')) {
      return
    }

    error.value = null
    try {
      const detail = await editSessionNode(session.id, nodeId, content)
      applySessionDetail(session, detail)
      const editedNode = session.nodeMap[nodeId]
      if (editedNode?.role === SESSION_MESSAGE_ROLES.HUMAN) {
        await continuePendingAssistant(language)
      }
    } catch (e) {
      isLoading.value = false
      error.value = e instanceof Error ? e.message : 'Failed to edit message'
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

      case EVENT_TYPES.PROVIDER_SWITCH:
        msg.traceSteps?.push({
          type: TRACE_STEP_TYPES.PROVIDER_SWITCH,
          fromProviderId: event.from_provider_id ?? null,
          toProviderId: event.to_provider_id,
          content: event.reason || '',
        })
        break

      case EVENT_TYPES.INTERRUPTED:
        msg.status = MESSAGE_STATUSES.INTERRUPTED
        msg.loopActive = false
        break

      case EVENT_TYPES.FAILED:
        msg.status = MESSAGE_STATUSES.FAILED
        msg.loopActive = false
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
    selectedProviderId,
    fallbackMode,
    isLoading,
    isInterrupting,
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
    continuePendingAssistant,
    stopStreaming,
    renameSession,
    selectVersion,
    retryMessage,
    editMessage,
    setSelectedProvider,
    updateActiveSessionPreferences,
    handleStreamEvent,
    setWidget,
    toggleWorkspace,
    toggleSidebar,
    setSidebarCollapsed,
    clearMessages,
    respondToApproval,
  }
})
