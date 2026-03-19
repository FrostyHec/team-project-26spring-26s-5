import { describe, it, expect, vi, beforeEach } from 'vitest'
import { checkHealth, fetchTools, sendMessage } from '../agent'

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
  })
})
