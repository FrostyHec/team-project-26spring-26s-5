import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useChatStore } from '../chat'

// Mock the API module
vi.mock('@/api/agent', () => ({
  checkHealth: vi.fn(),
  streamMessage: vi.fn(),
}))

import { checkHealth, streamMessage } from '@/api/agent'

const mockCheckHealth = vi.mocked(checkHealth)
const mockStreamMessage = vi.mocked(streamMessage)

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

  describe('sendMessage', () => {
    it('ignores empty messages', async () => {
      const store = useChatStore()

      await store.sendMessage('')
      await store.sendMessage('   ')

      expect(store.messages).toHaveLength(0)
    })

    it('adds user and assistant messages', async () => {
      // Mock an async generator that yields token events
      async function* fakeStream() {
        yield { type: 'token' as const, content: 'Hello!' }
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
      async function* fakeStream() {
        yield { type: 'token' as const, content: 'Hello' }
        yield { type: 'token' as const, content: ' world' }
      }
      mockStreamMessage.mockReturnValue(fakeStream())

      const store = useChatStore()
      await store.sendMessage('test')

      const assistantMsg = store.messages[1]!
      expect(assistantMsg.content).toBe('Hello world')
    })

    it('handles tool_start and tool_end events', async () => {
      async function* fakeStream() {
        yield { type: 'tool_start' as const, name: 'add', input: { a: 1, b: 2 } }
        yield { type: 'tool_end' as const, name: 'add', output: '3' }
        yield { type: 'token' as const, content: 'Result: 3' }
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

    it('sets error on stream failure', async () => {
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

      // isLoading should be true while streaming
      expect(store.isLoading).toBe(true)

      resolve!()
      await promise

      expect(store.isLoading).toBe(false)
    })
  })

  describe('clearMessages', () => {
    it('removes all messages', async () => {
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
