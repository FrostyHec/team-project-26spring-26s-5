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
  selectSessionVersion,
  retrySessionNode,
  editSessionNode,
  deleteSession,
  interruptSession,
  persistPartialResponse,
  updateSession,
  updateSessionPreferences,
  fetchDeadlines,
  toggleDeadlineComplete,
  syncPreview,
  syncCommit,
  deleteDeadline,
  updateDeadline,
  createDeadline,
  evaluateQuiz,
  fetchNewsPushSettings,
  saveNewsPushSettings,
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

    it('sends message with providerId', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ response: 'Done' }),
      })

      await sendMessage('help', 'sess-1', 'course_assistant', 'primary')

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/chat'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            message: 'help',
            session_id: 'sess-1',
            skill: 'course_assistant',
            provider_id: 'primary',
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

  describe('updateSessionPreferences', () => {
    it('patches session-level preferences', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            id: 'sess-1',
            title: 'Chat',
            created_at: '',
            updated_at: '',
            selected_provider_id: 'primary',
            fallback_mode: 'auto',
          }),
      })

      const result = await updateSessionPreferences('sess-1', {
        selected_provider_id: 'primary',
        fallback_mode: 'auto',
      })

      expect(result.selected_provider_id).toBe('primary')
      expect(result.fallback_mode).toBe('auto')
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/sessions/sess-1/preferences'),
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({
            selected_provider_id: 'primary',
            fallback_mode: 'auto',
          }),
        }),
      )
    })
  })

  describe('interruptSession', () => {
    it('posts interrupted partial output', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            session: { id: 'sess-1', title: 'Chat', created_at: '', updated_at: '' },
            messages: [],
          }),
      })

      await interruptSession('sess-1', {
        user_message: 'hello',
        assistant_content: 'partial answer',
      })

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/sessions/sess-1/interrupt'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            user_message: 'hello',
            assistant_content: 'partial answer',
          }),
        }),
      )
    })
  })

  describe('persistPartialResponse', () => {
    it('posts a failed partial response', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            session: { id: 'sess-1', title: 'Chat', created_at: '', updated_at: '' },
            messages: [],
          }),
      })

      await persistPartialResponse('sess-1', {
        user_message: 'hello',
        assistant_content: 'partial answer',
        assistant_status: 'failed',
      })

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/sessions/sess-1/partial-response'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            user_message: 'hello',
            assistant_content: 'partial answer',
            assistant_status: 'failed',
          }),
        }),
      )
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

  describe('updateSession', () => {
    it('patches session title', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ id: 's1', title: 'Renamed', created_at: '', updated_at: '' }),
      })

      const result = await updateSession('s1', { title: 'Renamed' })

      expect(result.title).toBe('Renamed')
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/sessions/s1'),
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ title: 'Renamed' }),
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

  describe('tree session actions', () => {
    it('selects a version group node', async () => {
      const detail = { session: { id: 's1' }, messages: [] }
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(detail),
      })

      const result = await selectSessionVersion('s1', 'group-1', 'node-2')

      expect(result).toEqual(detail)
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/sessions/s1/version-groups/group-1/select'),
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ node_id: 'node-2' }),
        }),
      )
    })

    it('creates a retry version for an assistant node', async () => {
      const detail = { session: { id: 's1' }, messages: [] }
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(detail),
      })

      const result = await retrySessionNode('s1', 'assistant-1')

      expect(result).toEqual(detail)
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/sessions/s1/nodes/assistant-1/retry'),
        expect.objectContaining({ method: 'POST' }),
      )
    })

    it('edits a session node', async () => {
      const detail = { session: { id: 's1' }, messages: [] }
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(detail),
      })

      const result = await editSessionNode('s1', 'node-1', 'updated content')

      expect(result).toEqual(detail)
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/sessions/s1/nodes/node-1/edit'),
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ content: 'updated content' }),
        }),
      )
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

  describe('toggleDeadlineComplete', () => {
    it('sends PATCH request with completed flag', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ id: 'd1', completed: true }),
      })

      const result = await toggleDeadlineComplete('d1', true)

      expect(result).toEqual({ id: 'd1', completed: true })
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/deadlines/d1/complete'),
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ completed: true }),
        }),
      )
    })

    it('throws on API error', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 404 })

      await expect(toggleDeadlineComplete('missing', true)).rejects.toThrow('API error: 404')
    })
  })

  describe('syncPreview', () => {
    it('posts candidates and returns new/duplicate split', async () => {
      const previewResult = {
        new_tasks: [{ id: '', title: 'New', due_date: '2026-04-20' }],
        duplicate_tasks: [{ candidate: { title: 'Dup' }, existing_id: 'e1' }],
      }
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(previewResult),
      })

      const result = await syncPreview([])

      expect(result.new_tasks).toHaveLength(1)
      expect(result.duplicate_tasks).toHaveLength(1)
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/deadlines/sync-preview'),
        expect.objectContaining({ method: 'POST' }),
      )
    })

    it('throws on API error', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 500 })

      await expect(syncPreview([])).rejects.toThrow('API error: 500')
    })
  })

  describe('syncCommit', () => {
    it('posts confirmed tasks and returns added list', async () => {
      const commitResult = {
        added: [{ id: 'x1', title: 'Task A' }],
      }
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(commitResult),
      })

      const result = await syncCommit([])

      expect(result.added).toHaveLength(1)
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/deadlines/sync-commit'),
        expect.objectContaining({ method: 'POST' }),
      )
    })

    it('throws on API error', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 500 })

      await expect(syncCommit([])).rejects.toThrow('API error: 500')
    })
  })

  describe('deleteDeadline', () => {
    it('sends DELETE and returns status + id', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ status: 'deleted', id: 'abc-123' }),
      })

      const result = await deleteDeadline('abc-123')

      expect(result).toEqual({ status: 'deleted', id: 'abc-123' })
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/deadlines/abc-123'),
        expect.objectContaining({ method: 'DELETE' }),
      )
    })

    it('throws on API error', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 404 })

      await expect(deleteDeadline('bad-id')).rejects.toThrow('API error: 404')
    })
  })

  // ── A007: updateDeadline ───────────────────────────────────────

  describe('updateDeadline', () => {
    it('sends PATCH and returns updated deadline', async () => {
      const updated = {
        id: 'd1',
        title: 'Updated',
        course: 'CS302',
        due_date: '2026-04-15',
        priority: 'high',
        source: 'manual',
        description: '',
        date_type: 'moment_day',
        start_date: '',
        completed: false,
      }
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(updated),
      })

      const result = await updateDeadline('d1', { title: 'Updated', priority: 'high' })

      expect(result).toEqual(updated)
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/deadlines/d1'),
        expect.objectContaining({
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    })

    it('throws on API error', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 422 })

      await expect(updateDeadline('d1', { priority: 'bogus' })).rejects.toThrow('API error: 422')
    })
  })

  // ── A008: createDeadline ───────────────────────────────────────

  describe('createDeadline', () => {
    it('sends POST and returns created deadline', async () => {
      const created = {
        id: 'new-1',
        title: 'My Task',
        course: 'CS302',
        due_date: '2026-05-01',
        priority: 'medium',
        source: 'manual',
        description: '',
        date_type: 'moment_day',
        start_date: '',
        completed: false,
      }
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(created),
      })

      const result = await createDeadline({ title: 'My Task', due_date: '2026-05-01' })

      expect(result).toEqual(created)
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/deadlines'),
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    })

    it('throws on API error', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 422 })

      await expect(createDeadline({ title: '' })).rejects.toThrow('API error: 422')
    })
  })

  // ── A009: evaluateQuiz ─────────────────────────────────────────

  describe('evaluateQuiz', () => {
    const mockQuestions = [
      {
        id: 1,
        type: 'multiple_choice' as const,
        question: 'What is 2+2?',
        options: ['3', '4', '5'],
        correct_answer: '4',
        explanation: null,
        score: 1,
      },
    ]
    const mockUserAnswers = { '1': '4' }
    const mockResult = {
      evaluations: {
        '1': {
          score: 1,
          standard_answer: '4',
          analysis: 'Correct!',
          total_score_included: true,
        },
      },
    }

    it('sends POST to /evaluate with correct body and X-Language header', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResult),
      })

      const result = await evaluateQuiz(mockQuestions, mockUserAnswers, true, 'zh')

      expect(result).toEqual(mockResult)
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/evaluate'),
        expect.objectContaining({
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Language': 'zh',
          },
          body: JSON.stringify({
            questions: mockQuestions,
            user_answers: mockUserAnswers,
            use_ai_grading: true,
          }),
        }),
      )
    })

    it('uses default language en when not specified', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResult),
      })

      await evaluateQuiz(mockQuestions, mockUserAnswers)

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/evaluate'),
        expect.objectContaining({
          headers: expect.objectContaining({ 'X-Language': 'en' }),
        }),
      )
    })

    it('uses default useAiGrading true when not specified', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResult),
      })

      await evaluateQuiz(mockQuestions, mockUserAnswers)

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/evaluate'),
        expect.objectContaining({
          body: JSON.stringify({
            questions: mockQuestions,
            user_answers: mockUserAnswers,
            use_ai_grading: true,
          }),
        }),
      )
    })

    it('throws on non-OK response', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 500 })

      await expect(evaluateQuiz(mockQuestions, mockUserAnswers)).rejects.toThrow('API error: 500')
    })
  })

  describe('news push settings', () => {
    const defaultSettings = {
      enabled: false,
      push_time: '08:30',
      limit: 20,
    }

    it('fetches news push settings', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(defaultSettings),
      })

      const settings = await fetchNewsPushSettings()

      expect(settings).toEqual(defaultSettings)
      expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining('/news/push/settings'))
    })

    it('throws when fetching settings fails', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 500 })

      await expect(fetchNewsPushSettings()).rejects.toThrow('API error: 500')
    })

    it('saves news push settings via PUT', async () => {
      const payload = {
        enabled: true,
        push_time: '09:30',
        limit: 10,
      }
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(payload),
      })

      const saved = await saveNewsPushSettings(payload)

      expect(saved).toEqual(payload)
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/news/push/settings'),
        expect.objectContaining({
          method: 'PUT',
          headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
        }),
      )
    })

    it('throws when saving settings fails', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 422 })

      await expect(saveNewsPushSettings(defaultSettings)).rejects.toThrow('API error: 422')
    })
  })
})
