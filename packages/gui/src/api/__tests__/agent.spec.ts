import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  checkHealth,
  fetchTools,
  sendMessage,
  approveToolCall,
  fetchSkills,
  listSessions,
  createSession,
  getSession,
  deleteSession,
  fetchDeadlines,
} from '../agent'

// Mock global fetch
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

beforeEach(() => {
  vi.clearAllMocks()
})

describe('API client', () => {
  describe('checkHealth', () => {
    it('returns true when server is healthy', async () => {
      mockFetch.mockResolvedValue({ ok: true })

      const result = await checkHealth()

      expect(result).toBe(true)
      expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining('/health'))
    })

    it('returns false on network error', async () => {
      mockFetch.mockRejectedValue(new Error('Network error'))

      const result = await checkHealth()

      expect(result).toBe(false)
    })
  })

  describe('fetchTools', () => {
    it('returns tool list from API', async () => {
      const tools = [{ name: 'add', description: 'Add numbers', sensitivity: 'SAFE' }]
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(tools),
      })

      const result = await fetchTools()

      expect(result).toEqual(tools)
    })

    it('throws on API error', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 500 })

      await expect(fetchTools()).rejects.toThrow('API error: 500')
    })
  })

  describe('sendMessage', () => {
    it('sends message and returns response', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ response: 'Hello!' }),
      })

      const result = await sendMessage('Hi')

      expect(result).toBe('Hello!')
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/chat'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ message: 'Hi' }),
        }),
      )
    })

    it('sends message with sessionId and skill', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ response: 'Done' }),
      })

      await sendMessage('help', 'sess-1', 'course_assistant')

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/chat'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            message: 'help',
            session_id: 'sess-1',
            skill: 'course_assistant',
          }),
        }),
      )
    })
  })

  describe('approveToolCall', () => {
    it('sends approval request and returns result', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ ok: true }),
      })

      const result = await approveToolCall('tc_123', true)

      expect(result).toEqual({ ok: true })
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/chat/approve'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ tool_call_id: 'tc_123', approved: true }),
        }),
      )
    })

    it('throws on API error', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 404 })

      await expect(approveToolCall('missing', true)).rejects.toThrow('API error: 404')
    })
  })

  describe('fetchSkills', () => {
    it('returns skills from API', async () => {
      const skills = [
        {
          id: 'general',
          name: 'General',
          description: '',
          system_prompt: '',
          icon: '💬',
          color: '#000',
        },
      ]
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(skills),
      })

      const result = await fetchSkills()

      expect(result).toEqual(skills)
      expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining('/skills'))
    })

    it('throws on API error', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 500 })

      await expect(fetchSkills()).rejects.toThrow('API error: 500')
    })
  })

  describe('listSessions', () => {
    it('returns sessions from API', async () => {
      const sessions = [{ id: 's1', title: 'Chat', created_at: '', updated_at: '' }]
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(sessions),
      })

      const result = await listSessions()

      expect(result).toEqual(sessions)
      expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining('/sessions'))
    })
  })

  describe('createSession', () => {
    it('creates a session via POST', async () => {
      const session = { id: 's1', title: 'New', created_at: '', updated_at: '' }
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(session),
      })

      const result = await createSession('New')

      expect(result).toEqual(session)
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/sessions'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ title: 'New' }),
        }),
      )
    })
  })

  describe('getSession', () => {
    it('fetches session detail by ID', async () => {
      const detail = { session: { id: 's1' }, messages: [] }
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(detail),
      })

      const result = await getSession('s1')

      expect(result).toEqual(detail)
      expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining('/sessions/s1'))
    })
  })

  describe('deleteSession', () => {
    it('deletes a session by ID', async () => {
      mockFetch.mockResolvedValue({ ok: true })

      await deleteSession('s1')

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/sessions/s1'),
        expect.objectContaining({ method: 'DELETE' }),
      )
    })

    it('throws on API error', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 404 })

      await expect(deleteSession('missing')).rejects.toThrow('API error: 404')
    })
  })

  describe('fetchDeadlines', () => {
    it('returns deadlines from API', async () => {
      const deadlines = [
        {
          id: 'd1',
          title: 'HW1',
          course: 'CS302',
          due_date: '2026-05-01',
          priority: 'high',
          source: 'manual',
          description: '',
        },
      ]
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ deadlines }),
      })

      const result = await fetchDeadlines()

      expect(result).toEqual(deadlines)
      expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining('/deadlines'))
    })

    it('passes course and priority query params', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ deadlines: [] }),
      })

      await fetchDeadlines('CS302', 'high')

      const calledUrl = mockFetch.mock.calls[0]![0] as string
      expect(calledUrl).toContain('course=CS302')
      expect(calledUrl).toContain('priority=high')
    })

    it('throws on API error', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 500 })

      await expect(fetchDeadlines()).rejects.toThrow('API error: 500')
    })
  })
})
