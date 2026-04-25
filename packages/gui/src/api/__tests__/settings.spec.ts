import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  getLlmSettings,
  getSettings,
  resetLlmSettings,
  resetSettings,
  updateLlmSettings,
  updateSettings,
} from '../settings'
import type { LlmSettingsResponse, SettingsResponse } from '../settings'

const MOCK_RESPONSE: SettingsResponse = {
  cas_account: 'testuser',
  cas_password_is_set: true,
  email_account: 'test@mail.sustech.edu.cn',
  email_password_is_set: false,
}

const EMPTY_RESPONSE: SettingsResponse = {
  cas_account: '',
  cas_password_is_set: false,
  email_account: '',
  email_password_is_set: false,
}

const MOCK_LLM_RESPONSE: LlmSettingsResponse = {
  temperature: 0.4,
  max_iterations: 8,
  system_prompt: 'Configured prompt',
  debug_mode: true,
  providers: [
    {
      id: 'primary',
      name: 'Primary',
      priority: 0,
      base_url: 'https://example.test/v1',
      api_key: 'secret-key',
      model: 'gpt-4o',
      enabled: true,
    },
  ],
}

// Mock fetch globally
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

function mockFetchResponse(data: unknown, status = 200) {
  mockFetch.mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  })
}

describe('settings API client', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  describe('getSettings', () => {
    it('calls GET /api/settings', async () => {
      mockFetchResponse(EMPTY_RESPONSE)
      await getSettings()
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/settings'),
        expect.objectContaining({ method: 'GET' }),
      )
    })

    it('returns parsed response on success', async () => {
      mockFetchResponse(MOCK_RESPONSE)
      const result = await getSettings()
      expect(result).toEqual(MOCK_RESPONSE)
    })

    it('throws on non-OK response', async () => {
      mockFetchResponse({ detail: 'Server error' }, 500)
      await expect(getSettings()).rejects.toThrow('Server error')
    })
  })

  describe('updateSettings', () => {
    it('calls PUT /api/settings with JSON body', async () => {
      mockFetchResponse(MOCK_RESPONSE)
      await updateSettings({ cas_account: 'user', cas_password: 'pw' })
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/settings'),
        expect.objectContaining({
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ cas_account: 'user', cas_password: 'pw' }),
        }),
      )
    })

    it('returns updated response on success', async () => {
      mockFetchResponse(MOCK_RESPONSE)
      const result = await updateSettings({ cas_account: 'testuser' })
      expect(result).toEqual(MOCK_RESPONSE)
    })

    it('throws on non-OK response', async () => {
      mockFetchResponse({ detail: 'Bad Request' }, 400)
      await expect(updateSettings({ cas_account: 'x' })).rejects.toThrow('Bad Request')
    })

    it('serializes null fields in body', async () => {
      mockFetchResponse(EMPTY_RESPONSE)
      await updateSettings({ cas_account: null, cas_password: null })
      const call = mockFetch.mock.calls[0]
      if (!call || !call[1]) throw new Error('fetch not called')
      const body = JSON.parse(call[1].body as string)
      expect(body.cas_account).toBeNull()
      expect(body.cas_password).toBeNull()
    })
  })

  describe('resetSettings', () => {
    it('calls DELETE /api/settings', async () => {
      mockFetchResponse(EMPTY_RESPONSE)
      await resetSettings()
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/settings'),
        expect.objectContaining({ method: 'DELETE' }),
      )
    })

    it('returns parsed response on success', async () => {
      mockFetchResponse(EMPTY_RESPONSE)
      const result = await resetSettings()
      expect(result).toEqual(EMPTY_RESPONSE)
    })

    it('throws on non-OK response', async () => {
      mockFetchResponse({ detail: 'Server error' }, 500)
      await expect(resetSettings()).rejects.toThrow('Server error')
    })
  })

  describe('LLM settings endpoints', () => {
    it('calls GET /api/settings/llm', async () => {
      mockFetchResponse(MOCK_LLM_RESPONSE)
      await getLlmSettings()
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/settings/llm'),
        expect.objectContaining({ method: 'GET' }),
      )
    })

    it('calls PUT /api/settings/llm with JSON body', async () => {
      mockFetchResponse(MOCK_LLM_RESPONSE)
      await updateLlmSettings(MOCK_LLM_RESPONSE)
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/settings/llm'),
        expect.objectContaining({
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(MOCK_LLM_RESPONSE),
        }),
      )
    })

    it('calls DELETE /api/settings/llm', async () => {
      mockFetchResponse(MOCK_LLM_RESPONSE)
      await resetLlmSettings()
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/settings/llm'),
        expect.objectContaining({ method: 'DELETE' }),
      )
    })

    it('surfaces FastAPI validation details from failed LLM saves', async () => {
      mockFetchResponse(
        {
          detail: [
            {
              msg: "Value error, Provider 'provider_2' is enabled but has no API key",
            },
          ],
        },
        422,
      )

      await expect(updateLlmSettings(MOCK_LLM_RESPONSE)).rejects.toThrow(
        "Provider 'provider_2' is enabled but has no API key",
      )
    })
  })
})
