import { describe, it, expect, vi, beforeEach } from 'vitest'
import { syncEmails, listEmails, sendEmail } from '../email'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

function mockFetchResponse(data: unknown, status = 200) {
  mockFetch.mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  })
}

describe('email API client', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('returns parsed sync payload on success', async () => {
    mockFetchResponse({ new_count: 1, updated_count: 0, total_count: 2, synced_at: '2026-04-13' })
    const result = await syncEmails()
    expect(result.new_count).toBe(1)
    expect(result.total_count).toBe(2)
  })

  it('includes backend code and detail on sync failure', async () => {
    mockFetchResponse(
      {
        detail: {
          code: 'EMAIL_CREDENTIALS_MISSING',
          message: 'Email credentials not configured',
        },
      },
      428,
    )

    await expect(syncEmails()).rejects.toThrow(
      'Sync failed [EMAIL_CREDENTIALS_MISSING]: Email credentials not configured',
    )
  })

  it('throws readable error for list endpoint failures', async () => {
    mockFetchResponse({ detail: 'Server error' }, 500)
    await expect(listEmails()).rejects.toThrow('List emails failed: Server error')
  })

  it('throws readable error for send endpoint failures', async () => {
    mockFetchResponse({ detail: 'bad request' }, 400)
    await expect(sendEmail({ to: 'a@b.com', subject: 'x' })).rejects.toThrow(
      'Send email failed: bad request',
    )
  })
})
