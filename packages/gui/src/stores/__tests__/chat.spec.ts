import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useChatStore, EVENT_TYPES, WIDGET_TYPES } from '../chat'

// Mock the API module
vi.mock('@/api/agent', () => ({
  checkHealth: vi.fn(),
  streamMessage: vi.fn(),
  approveToolCall: vi.fn(),
  listSessions: vi.fn(),
  createSession: vi.fn(),
  getSession: vi.fn(),
  deleteSession: vi.fn(),
  fetchSkills: vi.fn(),
}))

import {
  checkHealth,
  streamMessage,
  approveToolCall,
  listSessions,
  createSession,
  getSession,
  deleteSession,
  fetchSkills,
} from '@/api/agent'

const mockCheckHealth = vi.mocked(checkHealth)
const mockStreamMessage = vi.mocked(streamMessage)
const mockApproveToolCall = vi.mocked(approveToolCall)
const mockListSessions = vi.mocked(listSessions)
const mockCreateSession = vi.mocked(createSession)
const mockGetSession = vi.mocked(getSession)
const mockDeleteSession = vi.mocked(deleteSession)
const mockFetchSkills = vi.mocked(fetchSkills)

describe('useChatStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('initializes with empty state', () => {
    const store = useChatStore()
    expect(store.messages).toHaveLength(0)
    expect(store.isLoading).toBe(false)
    expect(store.isConnected).toBe(false)
    expect(store.error).toBeNull()
    expect(store.sessions).toHaveLength(0)
    expect(store.activeSessionId).toBeNull()
    expect(store.activeWidget.type).toBe(WIDGET_TYPES.EMPTY)
    expect(store.skills).toHaveLength(0)
  })

  it('exports EVENT_TYPES and WIDGET_TYPES constants', () => {
    expect(EVENT_TYPES.TOKEN).toBe('token')
    expect(EVENT_TYPES.WIDGET_DISPLAY).toBe('widget_display')
    expect(WIDGET_TYPES.CALENDAR).toBe('calendar')
    expect(WIDGET_TYPES.COURSE_CARDS).toBe('course_cards')
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
        session: { id: 'sess-1', title: 'Chat', created_at: '', updated_at: '' },
        messages: [
          { id: 1, session_id: 'sess-1', role: 'human', content: 'hi', created_at: '', ordinal: 0 },
          { id: 2, session_id: 'sess-1', role: 'ai', content: 'hello', created_at: '', ordinal: 1 },
        ],
      })

      const store = useChatStore()
      await store.newSession()
      // Clear messages to test loading
      store.sessions[0]!.messages = []

      await store.switchSession('sess-1')

      expect(store.activeSessionId).toBe('sess-1')
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
        },
      ])
      const store = useChatStore()

      await store.loadSessions()

      expect(store.sessions).toHaveLength(1)
      expect(store.sessions[0]!.id).toBe('remote-1')
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
      await store.sendMessage('Hi')

      expect(store.messages).toHaveLength(2)
      expect(store.messages[0]!.role).toBe('user')
      expect(store.messages[0]!.content).toBe('Hi')
      expect(store.messages[1]!.role).toBe('assistant')
      expect(store.messages[1]!.content).toBe('Hello!')
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
      expect(assistantMsg.toolCalls![0]!.status).toBe('completed')
      expect(assistantMsg.toolCalls![0]!.output).toBe('3')
      expect(assistantMsg.content).toBe('Result: 3')
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
      expect(assistantMsg.traceSteps![0]!.type).toBe('loop_start')
      expect(assistantMsg.traceSteps![1]!.type).toBe('loop_end')
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
        yield { type: 'token' as const, content: 'Done' }
        yield { type: 'loop_end' as const }
      }
      mockStreamMessage.mockReturnValue(fakeStream())

      const store = useChatStore()
      await store.sendMessage('compute')

      const assistantMsg = store.messages[1]!
      const thinkingSteps = assistantMsg.traceSteps!.filter((s) => s.type === 'thinking')
      expect(thinkingSteps).toHaveLength(1)
      expect(thinkingSteps[0]!.content).toBe('Let me analyze...')
    })

    it('handles widget_display events', async () => {
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
          widget_type: 'calendar',
          data: { events: [{ title: 'Exam' }] },
        }
        yield { type: 'token' as const, content: 'Here are your events' }
        yield { type: 'loop_end' as const }
      }
      mockStreamMessage.mockReturnValue(fakeStream())

      const store = useChatStore()
      await store.sendMessage('show calendar')

      expect(store.activeWidget.type).toBe('calendar')
      expect(store.activeWidget.data).toEqual({ events: [{ title: 'Exam' }] })
      expect(store.isWorkspaceOpen).toBe(true)
    })

    it('sets error on stream failure', async () => {
      mockCreateSession.mockResolvedValue({
        id: 'sess-err',
        title: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })

      async function* fakeStream(): AsyncGenerator<never> {
        throw new Error('Connection failed')
      }
      mockStreamMessage.mockReturnValue(fakeStream())

      const store = useChatStore()
      await store.sendMessage('test')

      expect(store.error).toBe('Connection failed')
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
      const approvalSteps = assistantMsg.traceSteps!.filter((s) => s.type === 'approval_request')
      expect(approvalSteps).toHaveLength(1)
      expect(approvalSteps[0]!.name).toBe('get_weather')
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

      store.setWidget('calendar', { events: [] })

      expect(store.activeWidget.type).toBe('calendar')
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
