import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import {
  useChatStore,
  EVENT_TYPES,
  WIDGET_TYPES,
  MESSAGE_ROLES,
  SESSION_MESSAGE_ROLES,
  TRACE_STEP_TYPES,
  TOOL_CALL_STATUS,
} from '../chat'
import { DEADLINE_MUTATING_TOOLS } from '../chatConstants'

// Mock the API module
vi.mock('@/api/agent', () => ({
  checkHealth: vi.fn(),
  streamMessage: vi.fn(),
  approveToolCall: vi.fn(),
  interruptSession: vi.fn(),
  persistPartialResponse: vi.fn(),
  listSessions: vi.fn(),
  createSession: vi.fn(),
  getSession: vi.fn(),
  selectSessionVersion: vi.fn(),
  retrySessionNode: vi.fn(),
  editSessionNode: vi.fn(),
  deleteSession: vi.fn(),
  fetchSkills: vi.fn(),
  updateSession: vi.fn(),
  updateSessionPreferences: vi.fn(),
  FALLBACK_MODES: {
    MANUAL: 'manual',
    AUTO: 'auto',
  },
}))

import {
  checkHealth,
  streamMessage,
  approveToolCall,
  interruptSession,
  persistPartialResponse,
  listSessions,
  createSession,
  getSession,
  selectSessionVersion,
  retrySessionNode,
  editSessionNode,
  deleteSession,
  fetchSkills,
  updateSession,
  updateSessionPreferences,
} from '@/api/agent'
import type {
  SessionDetail,
  SessionNode,
  SessionNodeToolCall,
  SessionNodeTraceStep,
} from '@/api/agent'

const mockCheckHealth = vi.mocked(checkHealth)
const mockStreamMessage = vi.mocked(streamMessage)
const mockApproveToolCall = vi.mocked(approveToolCall)
const mockInterruptSession = vi.mocked(interruptSession)
const mockPersistPartialResponse = vi.mocked(persistPartialResponse)
const mockListSessions = vi.mocked(listSessions)
const mockCreateSession = vi.mocked(createSession)
const mockGetSession = vi.mocked(getSession)
const mockSelectSessionVersion = vi.mocked(selectSessionVersion)
const mockRetrySessionNode = vi.mocked(retrySessionNode)
const mockEditSessionNode = vi.mocked(editSessionNode)
const mockDeleteSession = vi.mocked(deleteSession)
const mockFetchSkills = vi.mocked(fetchSkills)
const mockUpdateSession = vi.mocked(updateSession)
const mockUpdateSessionPreferences = vi.mocked(updateSessionPreferences)

describe('useChatStore', () => {
  const now = new Date().toISOString()

  function buildTreeDetail(options?: {
    sessionId?: string
    sessionTitle?: string
    assistantContent?: string
    assistantNodeId?: string
    assistantStatus?: 'completed' | 'interrupted' | 'failed' | 'streaming'
    assistantToolCalls?: SessionNodeToolCall[]
    assistantTraceSteps?: SessionNodeTraceStep[]
    selectedAssistantNodeId?: string
    userNodeId?: string
    userContent?: string
    extraNodes?: SessionNode[]
    versionNodeIds?: string[]
  }): SessionDetail {
    const sessionId = options?.sessionId ?? 'sess-tree'
    const userNodeId = options?.userNodeId ?? 'u1'
    const assistantNodeId = options?.assistantNodeId ?? 'a1'
    const selectedAssistantNodeId = options?.selectedAssistantNodeId ?? assistantNodeId
    const assistantStatus = options?.assistantStatus ?? 'completed'
    const userContent = options?.userContent ?? 'hi'
    const assistantContent = options?.assistantContent ?? 'hello'
    const versionNodeIds = options?.versionNodeIds ?? [assistantNodeId]

    return {
      session: {
        id: sessionId,
        title: options?.sessionTitle ?? 'Tree Chat',
        created_at: now,
        updated_at: now,
        selected_provider_id: null,
        fallback_mode: 'manual' as const,
      },
      messages: [
        {
          id: 1,
          session_id: sessionId,
          role: SESSION_MESSAGE_ROLES.HUMAN,
          content: userContent,
          created_at: now,
          ordinal: 0,
          status: 'completed' as const,
        },
        {
          id: 2,
          session_id: sessionId,
          role: SESSION_MESSAGE_ROLES.AI,
          content: assistantContent,
          created_at: now,
          ordinal: 1,
          status: assistantStatus,
        },
      ],
      nodes: [
        {
          id: userNodeId,
          session_id: sessionId,
          parent_id: null,
          role: SESSION_MESSAGE_ROLES.HUMAN,
          content: userContent,
          status: 'completed' as const,
          version_group_id: 'group-user',
          version_index: 0,
          source_kind: 'initial' as const,
          created_at: now,
          updated_at: now,
        },
        {
          id: assistantNodeId,
          session_id: sessionId,
          parent_id: userNodeId,
          role: SESSION_MESSAGE_ROLES.AI,
          content: assistantContent,
          status: assistantStatus,
          version_group_id: 'group-assistant',
          version_index: versionNodeIds.indexOf(assistantNodeId),
          source_kind: 'initial' as const,
          source_node_id: null,
          response_to_node_id: userNodeId,
          tool_calls: options?.assistantToolCalls,
          trace_steps: options?.assistantTraceSteps,
          created_at: now,
          updated_at: now,
        },
        ...(options?.extraNodes ?? []),
      ],
      visible_path: [userNodeId, assistantNodeId],
      version_groups: [
        {
          version_group_id: 'group-user',
          node_ids: [userNodeId],
          selected_node_id: userNodeId,
          position_in_path: 0,
        },
        {
          version_group_id: 'group-assistant',
          node_ids: versionNodeIds,
          selected_node_id: selectedAssistantNodeId,
          position_in_path: 1,
        },
      ],
    }
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  it('initializes with empty state', () => {
    const store = useChatStore()
    expect(store.messages).toHaveLength(0)
    expect(store.isLoading).toBe(false)
    expect(store.isConnected).toBe(false)
    expect(store.error).toBeNull()
    expect(store.sessions).toHaveLength(0)
    expect(store.activeSessionId).toBeNull()
    expect(store.selectedProviderId).toBeNull()
    expect(store.fallbackMode).toBe('manual')
    expect(store.isInterrupting).toBe(false)
    expect(store.activeWidget.type).toBe(WIDGET_TYPES.EMPTY)
    expect(store.skills).toHaveLength(0)
  })

  it('exports EVENT_TYPES and WIDGET_TYPES constants', () => {
    expect(EVENT_TYPES.TOKEN).toBe('token')
    expect(EVENT_TYPES.WIDGET_DISPLAY).toBe('widget_display')
    expect(WIDGET_TYPES.CALENDAR).toBe('calendar')
    expect(WIDGET_TYPES.COURSE_CARDS).toBe('course_cards')
  })

  // ── A007: DEADLINE_MUTATING_TOOLS & deadlineVersion ────────────

  it('exports DEADLINE_MUTATING_TOOLS with expected tool names', () => {
    expect(DEADLINE_MUTATING_TOOLS.has('add_deadline')).toBe(true)
    expect(DEADLINE_MUTATING_TOOLS.has('save_deadlines')).toBe(true)
    expect(DEADLINE_MUTATING_TOOLS.has('show_deadline_dashboard')).toBe(true)
    expect(DEADLINE_MUTATING_TOOLS.has('delete_deadline')).toBe(true)
    expect(DEADLINE_MUTATING_TOOLS.has('update_deadline')).toBe(true)
    expect(DEADLINE_MUTATING_TOOLS.has('list_deadlines')).toBe(false)
  })

  it('initialises deadlineVersion to 0', () => {
    const store = useChatStore()
    expect(store.deadlineVersion).toBe(0)
  })

  describe('checkConnection', () => {
    it('sets isConnected to true when health check passes', async () => {
      mockCheckHealth.mockResolvedValue(true)
      const store = useChatStore()

      await store.checkConnection()

      expect(store.isConnected).toBe(true)
    })

    it('sets isConnected to false when health check fails', async () => {
      mockCheckHealth.mockResolvedValue(false)
      const store = useChatStore()

      await store.checkConnection()

      expect(store.isConnected).toBe(false)
    })
  })

  describe('loadSkills', () => {
    it('loads skills from backend', async () => {
      const skills = [
        {
          id: 'general',
          name: 'General',
          description: 'desc',
          system_prompt: '',
          icon: '💬',
          color: '#000',
        },
      ]
      mockFetchSkills.mockResolvedValue(skills)
      const store = useChatStore()

      await store.loadSkills()

      expect(store.skills).toHaveLength(1)
      expect(store.skills[0]!.id).toBe('general')
    })

    it('does not throw when skills API fails', async () => {
      mockFetchSkills.mockRejectedValue(new Error('fail'))
      const store = useChatStore()

      await store.loadSkills()

      expect(store.skills).toHaveLength(0)
    })
  })

  describe('session management', () => {
    it('creates a new session via API', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-1',
        title: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      const store = useChatStore()

      const id = await store.newSession()

      expect(id).toBe('sess-1')
      expect(store.sessions).toHaveLength(1)
      expect(store.activeSessionId).toBe('sess-1')
    })

    it('reuses an existing blank session instead of creating another', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-1',
        title: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })

      const store = useChatStore()
      const firstId = await store.newSession()
      const secondId = await store.newSession()

      expect(firstId).toBe(secondId)
      expect(mockCreateSession).toHaveBeenCalledTimes(1)
      expect(store.sessions).toHaveLength(1)
    })

    it('falls back to local session when API fails', async () => {
      mockCreateSession.mockRejectedValue(new Error('fail'))
      const store = useChatStore()

      const id = await store.newSession()

      expect(id).toMatch(/^local-/)
      expect(store.sessions).toHaveLength(1)
      expect(store.activeSessionId).toBe(id)
    })

    it('switches session and loads history', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-1',
        title: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      mockGetSession.mockResolvedValue({
        session: {
          id: 'sess-1',
          title: 'Chat',
          created_at: '',
          updated_at: '',
          selected_provider_id: 'primary',
          fallback_mode: 'auto',
        },
        messages: [
          {
            id: 1,
            session_id: 'sess-1',
            role: SESSION_MESSAGE_ROLES.HUMAN,
            content: 'hi',
            created_at: '',
            ordinal: 0,
          },
          {
            id: 2,
            session_id: 'sess-1',
            role: SESSION_MESSAGE_ROLES.AI,
            content: 'hello',
            created_at: '',
            ordinal: 1,
          },
        ],
      })

      const store = useChatStore()
      await store.newSession()
      // Clear messages to test loading
      store.sessions[0]!.messages = []

      await store.switchSession('sess-1')

      expect(store.activeSessionId).toBe('sess-1')
      expect(store.selectedProviderId).toBe('primary')
      expect(store.fallbackMode).toBe('auto')
      expect(store.sessions[0]!.messages).toHaveLength(2)
    })

    it('removes a session', async () => {
      mockCreateSession
        .mockResolvedValueOnce({
          id: 'sess-1',
          title: '',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        })
        .mockResolvedValueOnce({
          id: 'sess-2',
          title: '',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        })
      mockDeleteSession.mockResolvedValue(undefined)

      const store = useChatStore()
      await store.newSession()
      store.sessions[0]!.messages.push({
        id: 'msg-1',
        role: MESSAGE_ROLES.USER,
        content: 'hi',
        timestamp: new Date(),
      })
      await store.newSession()

      expect(store.sessions).toHaveLength(2)

      await store.removeSession('sess-2')

      expect(store.sessions).toHaveLength(1)
    })

    it('loads sessions from backend', async () => {
      mockListSessions.mockResolvedValue([
        {
          id: 'remote-1',
          title: 'Chat 1',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          selected_provider_id: 'backup',
          fallback_mode: 'auto',
        },
      ])
      const store = useChatStore()

      await store.loadSessions()

      expect(store.sessions).toHaveLength(1)
      expect(store.sessions[0]!.id).toBe('remote-1')
      expect(store.sessions[0]!.selectedProviderId).toBe('backup')
      expect(store.sessions[0]!.fallbackMode).toBe('auto')
    })

    it('updates active session preferences via API', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-1',
        title: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      mockUpdateSessionPreferences.mockResolvedValue({
        id: 'sess-1',
        title: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        selected_provider_id: 'primary',
        fallback_mode: 'auto',
      })

      const store = useChatStore()
      await store.newSession()
      await store.updateActiveSessionPreferences({
        selected_provider_id: 'primary',
        fallback_mode: 'auto',
      })

      expect(mockUpdateSessionPreferences).toHaveBeenCalledWith('sess-1', {
        selected_provider_id: 'primary',
        fallback_mode: 'auto',
      })
      expect(store.selectedProviderId).toBe('primary')
      expect(store.fallbackMode).toBe('auto')
      expect(store.activeSession?.selectedProviderId).toBe('primary')
    })

    it('renames a session via API', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-1',
        title: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      mockUpdateSession.mockResolvedValue({
        id: 'sess-1',
        title: 'Renamed',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })

      const store = useChatStore()
      await store.newSession()
      await store.renameSession('sess-1', 'Renamed')

      expect(mockUpdateSession).toHaveBeenCalledWith('sess-1', { title: 'Renamed' })
      expect(store.activeSession?.title).toBe('Renamed')
    })
  })

  describe('tree actions', () => {
    it('selects a message version and updates the visible assistant node', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-tree',
        title: '',
        created_at: now,
        updated_at: now,
      })
      mockSelectSessionVersion.mockResolvedValue(
        buildTreeDetail({
          assistantContent: 'alternative answer',
          assistantNodeId: 'a2',
          selectedAssistantNodeId: 'a2',
          versionNodeIds: ['a1', 'a2'],
          extraNodes: [
            {
              id: 'a1',
              session_id: 'sess-tree',
              parent_id: 'u1',
              role: SESSION_MESSAGE_ROLES.AI,
              content: 'hello',
              status: 'completed',
              version_group_id: 'group-assistant',
              version_index: 0,
              source_kind: 'initial',
              source_node_id: null,
              response_to_node_id: 'u1',
              created_at: now,
              updated_at: now,
            },
          ],
        }),
      )

      const store = useChatStore()
      await store.newSession()

      await store.selectVersion('group-assistant', 'a2')

      expect(mockSelectSessionVersion).toHaveBeenCalledWith('sess-tree', 'group-assistant', 'a2')
      expect(store.messages[1]!.id).toBe('a2')
      expect(store.messages[1]!.content).toBe('alternative answer')
    })

    it('retries an assistant node and continues streaming with an empty follow-up message', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-tree',
        title: '',
        created_at: now,
        updated_at: now,
      })
      mockRetrySessionNode.mockResolvedValue(
        buildTreeDetail({
          assistantContent: '',
          assistantNodeId: 'a2',
          assistantStatus: 'streaming',
          selectedAssistantNodeId: 'a2',
          versionNodeIds: ['a1', 'a2'],
          extraNodes: [
            {
              id: 'a1',
              session_id: 'sess-tree',
              parent_id: 'u1',
              role: SESSION_MESSAGE_ROLES.AI,
              content: 'hello',
              status: 'completed',
              version_group_id: 'group-assistant',
              version_index: 0,
              source_kind: 'initial',
              source_node_id: null,
              response_to_node_id: 'u1',
              created_at: now,
              updated_at: now,
            },
          ],
        }),
      )
      mockGetSession.mockResolvedValue(
        buildTreeDetail({
          assistantContent: 'retried answer',
          assistantNodeId: 'a2',
          assistantStatus: 'completed',
          selectedAssistantNodeId: 'a2',
          versionNodeIds: ['a1', 'a2'],
          extraNodes: [
            {
              id: 'a1',
              session_id: 'sess-tree',
              parent_id: 'u1',
              role: SESSION_MESSAGE_ROLES.AI,
              content: 'hello',
              status: 'completed',
              version_group_id: 'group-assistant',
              version_index: 0,
              source_kind: 'initial',
              source_node_id: null,
              response_to_node_id: 'u1',
              created_at: now,
              updated_at: now,
            },
          ],
        }),
      )
      async function* fakeStream() {
        yield { type: 'loop_start' as const }
        yield { type: 'token' as const, content: 'retried answer' }
        yield { type: 'loop_end' as const }
      }
      mockStreamMessage.mockReturnValue(fakeStream())

      const store = useChatStore()
      await store.newSession()

      await store.retryMessage('a1')

      expect(mockRetrySessionNode).toHaveBeenCalledWith('sess-tree', 'a1')
      expect(mockStreamMessage).toHaveBeenCalledWith(
        '',
        'sess-tree',
        undefined,
        'en',
        undefined,
        expect.any(AbortSignal),
      )
      expect(store.messages[1]!.content).toBe('retried answer')
    })

    it('edits a user node and regenerates the assistant branch', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-tree',
        title: '',
        created_at: now,
        updated_at: now,
      })
      mockEditSessionNode.mockResolvedValue({
        ...buildTreeDetail({
          assistantContent: '',
          assistantNodeId: 'a2',
          assistantStatus: 'streaming',
          userNodeId: 'u2',
          userContent: 'edited question',
        }),
        nodes: [
          {
            id: 'u1',
            session_id: 'sess-tree',
            parent_id: null,
            role: SESSION_MESSAGE_ROLES.HUMAN,
            content: 'hi',
            status: 'completed',
            version_group_id: 'group-user',
            version_index: 0,
            source_kind: 'initial',
            created_at: now,
            updated_at: now,
          },
          {
            id: 'u2',
            session_id: 'sess-tree',
            parent_id: null,
            role: SESSION_MESSAGE_ROLES.HUMAN,
            content: 'edited question',
            status: 'completed',
            version_group_id: 'group-user',
            version_index: 1,
            source_kind: 'user_edit',
            source_node_id: 'u1',
            created_at: now,
            updated_at: now,
          },
          {
            id: 'a2',
            session_id: 'sess-tree',
            parent_id: 'u2',
            role: SESSION_MESSAGE_ROLES.AI,
            content: '',
            status: 'streaming',
            version_group_id: 'group-assistant',
            version_index: 0,
            source_kind: 'initial',
            source_node_id: null,
            response_to_node_id: 'u2',
            created_at: now,
            updated_at: now,
          },
        ],
        visible_path: ['u2', 'a2'],
        version_groups: [
          {
            version_group_id: 'group-user',
            node_ids: ['u1', 'u2'],
            selected_node_id: 'u2',
            position_in_path: 0,
          },
          {
            version_group_id: 'group-assistant',
            node_ids: ['a2'],
            selected_node_id: 'a2',
            position_in_path: 1,
          },
        ],
      })
      mockGetSession.mockResolvedValue(
        buildTreeDetail({
          assistantContent: 'edited answer',
          assistantNodeId: 'a2',
          assistantStatus: 'completed',
          userNodeId: 'u2',
          userContent: 'edited question',
        }),
      )
      async function* fakeStream() {
        yield { type: 'loop_start' as const }
        yield { type: 'token' as const, content: 'edited answer' }
        yield { type: 'loop_end' as const }
      }
      mockStreamMessage.mockReturnValue(fakeStream())

      const store = useChatStore()
      await store.newSession()

      await store.editMessage('u1', 'edited question')

      expect(mockEditSessionNode).toHaveBeenCalledWith('sess-tree', 'u1', 'edited question')
      expect(mockStreamMessage).toHaveBeenCalledWith(
        '',
        'sess-tree',
        undefined,
        'en',
        undefined,
        expect.any(AbortSignal),
      )
      expect(store.messages[0]!.content).toBe('edited question')
      expect(store.messages[1]!.content).toBe('edited answer')
    })
  })

  describe('sendMessage', () => {
    it('ignores empty messages', async () => {
      const store = useChatStore()

      await store.sendMessage('')
      await store.sendMessage('   ')

      expect(store.messages).toHaveLength(0)
    })

    it('adds user and assistant messages', async () => {
      // Set up session creation
      mockCreateSession.mockResolvedValue({
        id: 'sess-auto',
        title: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })

      // Mock an async generator that yields token events
      async function* fakeStream() {
        yield { type: 'loop_start' as const }
        yield { type: 'token' as const, content: 'Hello!' }
        yield { type: 'loop_end' as const }
      }
      mockStreamMessage.mockReturnValue(fakeStream())

      const store = useChatStore()
      store.setSelectedProvider('primary')
      await store.sendMessage('Hi')

      expect(store.messages).toHaveLength(2)
      expect(store.messages[0]!.role).toBe(MESSAGE_ROLES.USER)
      expect(store.messages[0]!.content).toBe('Hi')
      expect(store.messages[1]!.role).toBe(MESSAGE_ROLES.ASSISTANT)
      expect(store.messages[1]!.content).toBe('Hello!')
      expect(mockStreamMessage).toHaveBeenCalledWith(
        'Hi',
        'sess-auto',
        undefined,
        'en',
        'primary',
        expect.any(AbortSignal),
      )
    })

    it('handles token events by appending content', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-t',
        title: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })

      async function* fakeStream() {
        yield { type: 'loop_start' as const }
        yield { type: 'token' as const, content: 'Hello' }
        yield { type: 'token' as const, content: ' world' }
        yield { type: 'loop_end' as const }
      }
      mockStreamMessage.mockReturnValue(fakeStream())

      const store = useChatStore()
      await store.sendMessage('test')

      const assistantMsg = store.messages[1]!
      expect(assistantMsg.content).toBe('Hello world')
    })

    it('reconciles final persisted response when stream has no token text', async () => {
      const now = new Date().toISOString()
      mockCreateSession.mockResolvedValue({
        id: 'sess-refresh',
        title: '',
        created_at: now,
        updated_at: now,
      })

      async function* fakeStream() {
        yield { type: 'loop_start' as const }
        yield { type: 'thinking' as const, content: 'Working on it...' }
        yield { type: 'loop_end' as const }
      }
      mockStreamMessage.mockReturnValue(fakeStream())
      mockGetSession.mockResolvedValue({
        session: { id: 'sess-refresh', title: 'Recovered Title', created_at: now, updated_at: now },
        messages: [
          {
            id: 1,
            session_id: 'sess-refresh',
            role: SESSION_MESSAGE_ROLES.HUMAN,
            content: 'question',
            created_at: now,
            ordinal: 0,
          },
          {
            id: 2,
            session_id: 'sess-refresh',
            role: SESSION_MESSAGE_ROLES.AI,
            content: 'Final persisted answer',
            created_at: now,
            ordinal: 1,
          },
        ],
      })

      const store = useChatStore()
      await store.sendMessage('question')

      expect(mockGetSession).toHaveBeenCalledWith('sess-refresh')
      expect(store.messages).toHaveLength(2)
      expect(store.messages[1]!.content).toBe('Final persisted answer')
      expect(store.activeSession?.title).toBe('Recovered Title')
    })

    it('does not locally turn the first user message into the session title', async () => {
      const now = new Date().toISOString()
      mockCreateSession.mockResolvedValue({
        id: 'sess-no-local-title',
        title: '',
        created_at: now,
        updated_at: now,
      })

      async function* fakeStream() {
        yield { type: 'loop_start' as const }
        yield { type: 'token' as const, content: 'Answer body' }
        yield { type: 'loop_end' as const }
      }
      mockStreamMessage.mockReturnValue(fakeStream())
      mockGetSession.mockRejectedValue(new Error('refresh failed'))

      const store = useChatStore()
      await store.sendMessage('Use this long first message as the session title?')

      expect(store.activeSession?.title).toBe('New Chat')
      expect(store.messages[0]!.content).toBe('Use this long first message as the session title?')
    })

    it('polls for the asynchronously generated first-round title', async () => {
      vi.useFakeTimers()
      try {
        const now = new Date().toISOString()
        mockCreateSession.mockResolvedValue({
          id: 'sess-async-title',
          title: '',
          created_at: now,
          updated_at: now,
        })

        async function* fakeStream() {
          yield { type: 'loop_start' as const }
          yield { type: 'token' as const, content: 'Answer body' }
          yield { type: 'loop_end' as const }
        }
        mockStreamMessage.mockReturnValue(fakeStream())
        mockGetSession
          .mockResolvedValueOnce(
            buildTreeDetail({
              sessionId: 'sess-async-title',
              sessionTitle: '',
              userContent: 'First question',
              assistantContent: 'Answer body',
            }),
          )
          .mockResolvedValueOnce(
            buildTreeDetail({
              sessionId: 'sess-async-title',
              sessionTitle: 'Generated Session Title',
              userContent: 'First question',
              assistantContent: 'Answer body',
            }),
          )

        const store = useChatStore()
        await store.sendMessage('First question')

        expect(store.activeSession?.title).toBe('New Chat')

        await vi.advanceTimersByTimeAsync(1000)

        expect(mockGetSession).toHaveBeenCalledTimes(2)
        expect(store.activeSession?.title).toBe('Generated Session Title')
      } finally {
        vi.useRealTimers()
      }
    })

    it('handles tool_start and tool_end events', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-tool',
        title: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })

      async function* fakeStream() {
        yield { type: 'loop_start' as const }
        yield { type: 'tool_start' as const, name: 'add', input: { a: 1, b: 2 } }
        yield { type: 'tool_end' as const, name: 'add', output: '3' }
        yield { type: 'token' as const, content: 'Result: 3' }
        yield { type: 'loop_end' as const }
      }
      mockStreamMessage.mockReturnValue(fakeStream())

      const store = useChatStore()
      await store.sendMessage('add 1+2')

      const assistantMsg = store.messages[1]!
      expect(assistantMsg.toolCalls).toHaveLength(1)
      expect(assistantMsg.toolCalls![0]!.name).toBe('add')
      expect(assistantMsg.toolCalls![0]!.status).toBe(TOOL_CALL_STATUS.COMPLETED)
      expect(assistantMsg.toolCalls![0]!.output).toBe('3')
      expect(assistantMsg.content).toBe('Result: 3')
    })

    it('preserves tool calling trace after server refresh for tree sessions', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-tool-refresh',
        title: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })

      async function* fakeStream() {
        yield { type: 'loop_start' as const }
        yield { type: 'tool_start' as const, name: 'add', input: { a: 1, b: 2 } }
        yield { type: 'tool_end' as const, name: 'add', output: '3' }
        yield { type: 'token' as const, content: 'Result: 3' }
        yield { type: 'loop_end' as const }
      }
      mockStreamMessage.mockReturnValue(fakeStream())
      mockGetSession.mockResolvedValue(
        buildTreeDetail({
          assistantContent: 'Result: 3',
          assistantToolCalls: [
            {
              name: 'add',
              input: { a: 1, b: 2 },
              output: '3',
              status: 'completed',
            },
          ],
          assistantTraceSteps: [
            { type: 'loop_start' },
            { type: 'tool_start', name: 'add', input: { a: 1, b: 2 } },
            { type: 'tool_end', name: 'add', output: '3' },
            { type: 'loop_end' },
          ],
        }),
      )

      const store = useChatStore()
      await store.sendMessage('add 1+2')

      const assistantMsg = store.messages[1]!
      expect(mockGetSession).toHaveBeenCalledWith('sess-tool-refresh')
      expect(assistantMsg.toolCalls).toHaveLength(1)
      expect(assistantMsg.toolCalls![0]!.name).toBe('add')
      expect(assistantMsg.toolCalls![0]!.output).toBe('3')
      expect(assistantMsg.traceSteps?.map((step) => step.type)).toEqual([
        TRACE_STEP_TYPES.LOOP_START,
        TRACE_STEP_TYPES.TOOL_START,
        TRACE_STEP_TYPES.TOOL_END,
        TRACE_STEP_TYPES.LOOP_END,
      ])
      expect(assistantMsg.content).toBe('Result: 3')
      expect(assistantMsg.loopActive).toBe(false)
    })

    it('preserves thinking trace after server refresh for tree sessions', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-think-refresh',
        title: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })

      async function* fakeStream() {
        yield { type: 'loop_start' as const }
        yield { type: 'thinking' as const, content: 'Plan A' }
        yield { type: 'tool_start' as const, name: 'calc', input: { x: 1 } }
        yield { type: 'tool_end' as const, name: 'calc', output: '1' }
        yield { type: 'thinking' as const, content: 'Plan B' }
        yield { type: 'token' as const, content: 'Final answer' }
        yield { type: 'loop_end' as const }
      }
      mockStreamMessage.mockReturnValue(fakeStream())
      mockGetSession.mockResolvedValue(
        buildTreeDetail({
          sessionId: 'sess-think-refresh',
          assistantContent: 'Final answer',
          assistantToolCalls: [
            {
              name: 'calc',
              input: { x: 1 },
              output: '1',
              status: 'completed',
            },
          ],
          assistantTraceSteps: [
            { type: 'loop_start' },
            { type: 'thinking', content: 'Plan A' },
            { type: 'tool_start', name: 'calc', input: { x: 1 } },
            { type: 'tool_end', name: 'calc', output: '1' },
            { type: 'thinking', content: 'Plan B' },
            { type: 'loop_end' },
          ],
        }),
      )

      const store = useChatStore()
      await store.sendMessage('compute')

      const assistantMsg = store.messages[1]!
      expect(mockGetSession).toHaveBeenCalledWith('sess-think-refresh')
      expect(assistantMsg.content).toBe('Final answer')
      expect(assistantMsg.traceSteps?.map((step) => step.type)).toEqual([
        TRACE_STEP_TYPES.LOOP_START,
        TRACE_STEP_TYPES.THINKING,
        TRACE_STEP_TYPES.TOOL_START,
        TRACE_STEP_TYPES.TOOL_END,
        TRACE_STEP_TYPES.THINKING,
        TRACE_STEP_TYPES.LOOP_END,
      ])
      expect(
        assistantMsg.traceSteps
          ?.filter((step) => step.type === TRACE_STEP_TYPES.THINKING)
          .map((step) => step.content),
      ).toEqual(['Plan A', 'Plan B'])
    })

    it('handles loop_start and loop_end events', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-loop',
        title: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })

      async function* fakeStream() {
        yield { type: 'loop_start' as const }
        yield { type: 'token' as const, content: 'Hi' }
        yield { type: 'loop_end' as const }
      }
      mockStreamMessage.mockReturnValue(fakeStream())

      const store = useChatStore()
      await store.sendMessage('hello')

      const assistantMsg = store.messages[1]!
      expect(assistantMsg.traceSteps).toHaveLength(2)
      expect(assistantMsg.traceSteps![0]!.type).toBe(TRACE_STEP_TYPES.LOOP_START)
      expect(assistantMsg.traceSteps![1]!.type).toBe(TRACE_STEP_TYPES.LOOP_END)
      expect(assistantMsg.loopActive).toBe(false)
    })

    it('handles thinking events', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-think',
        title: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })

      async function* fakeStream() {
        yield { type: 'loop_start' as const }
        yield { type: 'thinking' as const, content: 'Let me analyze...' }
        yield { type: 'tool_start' as const, name: 'add', input: { a: 1, b: 2 } }
        yield { type: 'tool_end' as const, name: 'add', output: '3' }
        yield { type: 'thinking' as const, content: 'Now I can answer.' }
        yield { type: 'token' as const, content: 'Done' }
        yield { type: 'loop_end' as const }
      }
      mockStreamMessage.mockReturnValue(fakeStream())

      const store = useChatStore()
      await store.sendMessage('compute')

      const assistantMsg = store.messages[1]!
      const thinkingSteps = assistantMsg.traceSteps!.filter(
        (s) => s.type === TRACE_STEP_TYPES.THINKING,
      )
      expect(thinkingSteps).toHaveLength(2)
      expect(thinkingSteps[0]!.content).toBe('Let me analyze...')
      expect(thinkingSteps[1]!.content).toBe('Now I can answer.')
      expect(assistantMsg.traceSteps?.map((step) => step.type)).toEqual([
        TRACE_STEP_TYPES.LOOP_START,
        TRACE_STEP_TYPES.THINKING,
        TRACE_STEP_TYPES.TOOL_START,
        TRACE_STEP_TYPES.TOOL_END,
        TRACE_STEP_TYPES.THINKING,
        TRACE_STEP_TYPES.LOOP_END,
      ])
      expect(assistantMsg.content).toBe('Done')
      expect(assistantMsg.content).not.toContain('Let me analyze...')
    })

    it('merges consecutive thinking events into a single trace step', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-think-merge',
        title: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })

      async function* fakeStream() {
        yield { type: 'loop_start' as const }
        yield { type: 'thinking' as const, content: 'Let ' }
        yield { type: 'thinking' as const, content: 'me ' }
        yield { type: 'thinking' as const, content: 'analyze...' }
        yield { type: 'token' as const, content: 'Done' }
        yield { type: 'loop_end' as const }
      }
      mockStreamMessage.mockReturnValue(fakeStream())

      const store = useChatStore()
      await store.sendMessage('compute')

      const assistantMsg = store.messages[1]!
      const thinkingSteps = assistantMsg.traceSteps!.filter(
        (s) => s.type === TRACE_STEP_TYPES.THINKING,
      )
      expect(thinkingSteps).toHaveLength(1)
      expect(thinkingSteps[0]!.content).toBe('Let me analyze...')
      expect(assistantMsg.content).toBe('Done')
    })

    it('handles widget_display events for self-fetch widget', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-widget',
        title: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })

      async function* fakeStream() {
        yield { type: 'loop_start' as const }
        yield {
          type: 'widget_display' as const,
          widget_type: 'calendar' as const,
          data: { events: [{ title: 'Exam' }] },
        }
        yield { type: 'token' as const, content: 'Here are your events' }
        yield { type: 'loop_end' as const }
      }
      mockStreamMessage.mockReturnValue(fakeStream())

      const store = useChatStore()
      await store.sendMessage('show calendar')

      expect(store.activeWidget.type).toBe(WIDGET_TYPES.CALENDAR)
      // Calendar is a self-fetch widget — event data is always ignored.
      // The widget fetches deadlines from the REST API on mount.
      expect(store.activeWidget.data).toEqual({})
      expect(store.isWorkspaceOpen).toBe(true)
    })

    it('handles widget_display events for non-self-fetch widget', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-widget2',
        title: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })

      async function* fakeStream() {
        yield { type: 'loop_start' as const }
        yield {
          type: 'widget_display' as const,
          widget_type: 'document' as const,
          data: { content: 'Hello doc' },
        }
        yield { type: 'loop_end' as const }
      }
      mockStreamMessage.mockReturnValue(fakeStream())

      const store = useChatStore()
      await store.sendMessage('show doc')

      expect(store.activeWidget.type).toBe(WIDGET_TYPES.DOCUMENT)
      // Non-self-fetch widget keeps event data
      expect(store.activeWidget.data).toEqual({ content: 'Hello doc' })
      expect(store.isWorkspaceOpen).toBe(true)
    })

    it('sets error on stream failure', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-err',
        title: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      mockPersistPartialResponse.mockResolvedValue({
        session: { id: 'sess-err', title: '', created_at: '', updated_at: '' },
        messages: [],
      })

      async function* fakeStream(): AsyncGenerator<never> {
        throw new Error('Connection failed')
      }
      mockStreamMessage.mockReturnValue(fakeStream())

      const store = useChatStore()
      await store.sendMessage('test')

      expect(store.error).toBe('Connection failed')
      expect(mockPersistPartialResponse).toHaveBeenCalledWith('sess-err', {
        user_message: 'test',
        assistant_content: 'Failed to get response.',
        assistant_status: 'failed',
      })
      expect(store.isLoading).toBe(false)
    })

    it('manages loading state', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-load',
        title: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })

      let resolve: () => void
      const barrier = new Promise<void>((r) => {
        resolve = r
      })

      async function* fakeStream() {
        await barrier
        yield { type: 'token' as const, content: 'done' }
      }
      mockStreamMessage.mockReturnValue(fakeStream())

      const store = useChatStore()
      const promise = store.sendMessage('test')

      // Allow microtasks (session creation) to settle so isLoading is set
      await new Promise((r) => setTimeout(r, 0))

      // isLoading should be true while streaming
      expect(store.isLoading).toBe(true)

      resolve!()
      await promise

      expect(store.isLoading).toBe(false)
    })

    it('interrupts streaming and persists partial output', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-stop',
        title: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      mockInterruptSession.mockResolvedValue({
        session: { id: 'sess-stop', title: '', created_at: '', updated_at: '' },
        messages: [],
      })

      let resolveBarrier: (() => void) | undefined
      const barrier = new Promise<void>((resolve) => {
        resolveBarrier = resolve
      })

      mockStreamMessage.mockImplementation(
        async function* (_message, _sessionId, _skill, _language, _providerId, signal) {
          await barrier
          if (signal?.aborted) {
            const error = new Error('aborted')
            error.name = 'AbortError'
            throw error
          }
          yield { type: 'token' as const, content: 'done' }
        },
      )

      const store = useChatStore()
      const promise = store.sendMessage('hello')
      await new Promise((r) => setTimeout(r, 0))

      store.messages[1]!.content = 'partial answer'
      await store.stopStreaming()
      resolveBarrier?.()
      await promise

      expect(mockInterruptSession).toHaveBeenCalledWith('sess-stop', {
        user_message: 'hello',
        assistant_content: 'partial answer',
      })
      expect(store.messages[1]!.status).toBe('interrupted')
      expect(store.isLoading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('handles approval_request events', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-approval',
        title: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })

      async function* fakeStream() {
        yield { type: 'loop_start' as const }
        yield {
          type: 'approval_request' as const,
          tool_name: 'get_weather',
          tool_args: { city: 'Beijing' },
          tool_call_id: 'tc_1',
        }
        yield { type: 'tool_end' as const, name: 'get_weather', output: 'cancelled' }
        yield { type: 'loop_end' as const }
      }
      mockStreamMessage.mockReturnValue(fakeStream())

      const store = useChatStore()
      await store.sendMessage('weather')

      // Pending approval should be set
      expect(store.pendingApproval).toEqual({
        toolName: 'get_weather',
        toolArgs: { city: 'Beijing' },
        toolCallId: 'tc_1',
      })

      // Trace should include approval_request step
      const assistantMsg = store.messages[1]!
      const approvalSteps = assistantMsg.traceSteps!.filter(
        (s) => s.type === TRACE_STEP_TYPES.APPROVAL_REQUEST,
      )
      expect(approvalSteps).toHaveLength(1)
      expect(approvalSteps[0]!.name).toBe('get_weather')
    })

    it('keeps provider_switch events after the session refresh', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-switch',
        title: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      mockGetSession.mockResolvedValue(
        buildTreeDetail({
          assistantContent: 'Recovered',
          assistantTraceSteps: [
            {
              type: 'provider_switch',
              fromProviderId: 'primary',
              toProviderId: 'secondary',
              content: 'primary down',
            },
          ],
        }),
      )

      async function* fakeStream() {
        yield {
          type: 'provider_switch' as const,
          from_provider_id: 'primary',
          to_provider_id: 'secondary',
          reason: 'primary down',
        }
        yield { type: 'token' as const, content: 'Recovered' }
      }
      mockStreamMessage.mockReturnValue(fakeStream())

      const store = useChatStore()
      await store.sendMessage('weather')

      const assistantMsg = store.messages[1]!
      const switchSteps = assistantMsg.traceSteps!.filter(
        (s) => s.type === TRACE_STEP_TYPES.PROVIDER_SWITCH,
      )
      expect(mockGetSession).toHaveBeenCalledWith('sess-switch')
      expect(switchSteps).toHaveLength(1)
      expect(switchSteps[0]!.fromProviderId).toBe('primary')
      expect(switchSteps[0]!.toProviderId).toBe('secondary')
      expect(switchSteps[0]!.content).toBe('primary down')
    })
  })

  describe('respondToApproval', () => {
    it('calls approveToolCall API and clears pending', async () => {
      mockApproveToolCall.mockResolvedValue({ ok: true })

      const store = useChatStore()
      store.pendingApproval = {
        toolName: 'get_weather',
        toolArgs: { city: 'Beijing' },
        toolCallId: 'tc_approve',
      }

      await store.respondToApproval(true)

      expect(mockApproveToolCall).toHaveBeenCalledWith('tc_approve', true)
      expect(store.pendingApproval).toBeNull()
    })

    it('sets error when API call fails', async () => {
      mockApproveToolCall.mockRejectedValue(new Error('Network error'))

      const store = useChatStore()
      store.pendingApproval = {
        toolName: 'get_weather',
        toolArgs: { city: 'Tokyo' },
        toolCallId: 'tc_fail',
      }

      await store.respondToApproval(false)

      expect(store.error).toBe('Network error')
      expect(store.pendingApproval).toBeNull()
    })

    it('does nothing when no pending approval', async () => {
      const store = useChatStore()
      store.pendingApproval = null

      await store.respondToApproval(true)

      expect(mockApproveToolCall).not.toHaveBeenCalled()
    })
  })

  describe('widget management', () => {
    it('setWidget updates activeWidget', () => {
      const store = useChatStore()

      store.setWidget(WIDGET_TYPES.CALENDAR, { events: [] })

      expect(store.activeWidget.type).toBe(WIDGET_TYPES.CALENDAR)
      expect(store.isWorkspaceOpen).toBe(true)
    })

    it('toggleWorkspace flips isWorkspaceOpen', () => {
      const store = useChatStore()
      expect(store.isWorkspaceOpen).toBe(true)

      store.toggleWorkspace()
      expect(store.isWorkspaceOpen).toBe(false)

      store.toggleWorkspace()
      expect(store.isWorkspaceOpen).toBe(true)
    })

    it('toggleSidebar flips isSidebarCollapsed', () => {
      const store = useChatStore()
      expect(store.isSidebarCollapsed).toBe(false)

      store.toggleSidebar()
      expect(store.isSidebarCollapsed).toBe(true)

      store.toggleSidebar()
      expect(store.isSidebarCollapsed).toBe(false)
    })
  })

  describe('clearMessages', () => {
    it('removes all messages in active session', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-clear',
        title: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })

      async function* fakeStream() {
        yield { type: 'token' as const, content: 'Hi' }
      }
      mockStreamMessage.mockReturnValue(fakeStream())

      const store = useChatStore()
      await store.sendMessage('test')

      expect(store.messages).toHaveLength(2)

      store.clearMessages()

      expect(store.messages).toHaveLength(0)
    })
  })
})
