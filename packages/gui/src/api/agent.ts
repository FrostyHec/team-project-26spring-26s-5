/**
 * API client for the ReAct Agent backend.
 * Handles chat requests, SSE streaming, session CRUD, and skills.
 */

import type { EventType, SessionMessageRole, WidgetType } from '@/stores/chatConstants'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

/** Tool information from the API. */
export interface ToolInfo {
  name: string
  description: string
  sensitivity: string
}

/** Skill definition from the backend. */
export interface SkillInfo {
  id: string
  name: string
  description: string
  system_prompt: string
  icon: string
  color: string
}

/** Session summary from the API. */
export interface SessionInfo {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count?: number
  selected_provider_id?: string | null
  fallback_mode?: FallbackMode
}

export const FALLBACK_MODES = {
  MANUAL: 'manual',
  AUTO: 'auto',
} as const

export type FallbackMode = (typeof FALLBACK_MODES)[keyof typeof FALLBACK_MODES]

export const NODE_SOURCE_KINDS = {
  INITIAL: 'initial',
  RETRY: 'retry',
  USER_EDIT: 'user_edit',
  ASSISTANT_EDIT: 'assistant_edit',
  FALLBACK: 'fallback',
} as const

export type NodeSourceKind = (typeof NODE_SOURCE_KINDS)[keyof typeof NODE_SOURCE_KINDS]

export interface UpdateSessionPreferencesRequest {
  selected_provider_id?: string | null
  fallback_mode?: FallbackMode
}

/** Session detail with messages. */
export interface SessionDetail {
  session: SessionInfo
  messages: SessionMessage[]
  nodes?: SessionNode[]
  visible_path?: string[]
  version_groups?: SessionVersionGroup[]
}

export interface SessionNodeToolCall {
  name: string
  input?: Record<string, unknown>
  output?: string
  status?: string
}

export const SESSION_NODE_TRACE_TYPES = {
  LOOP_START: 'loop_start',
  THINKING: 'thinking',
  TOOL_START: 'tool_start',
  TOOL_END: 'tool_end',
  LOOP_END: 'loop_end',
  APPROVAL_REQUEST: 'approval_request',
  WIDGET_DISPLAY: 'widget_display',
  PROVIDER_SWITCH: 'provider_switch',
} as const

export type SessionNodeTraceType =
  (typeof SESSION_NODE_TRACE_TYPES)[keyof typeof SESSION_NODE_TRACE_TYPES]

export interface SessionNodeTraceStep {
  type: SessionNodeTraceType
  content?: string
  name?: string
  input?: Record<string, unknown>
  output?: string
  fromProviderId?: string | null
  toProviderId?: string
  widgetType?: WidgetType
  widgetData?: Record<string, unknown>
}

export interface SessionNode {
  id: string
  session_id: string
  parent_id?: string | null
  role: SessionMessageRole
  content: string
  status?: 'completed' | 'interrupted' | 'failed' | 'streaming'
  version_group_id: string
  version_index: number
  source_kind: NodeSourceKind
  source_node_id?: string | null
  response_to_node_id?: string | null
  tool_calls?: SessionNodeToolCall[]
  trace_steps?: SessionNodeTraceStep[]
  created_at: string
  updated_at: string
}

export interface SessionVersionGroup {
  version_group_id: string
  node_ids: string[]
  selected_node_id: string
  position_in_path: number
}

/** A persisted message from the session store. */
export interface SessionMessage {
  id: number
  session_id: string
  role: SessionMessageRole
  content: string
  tool_call_id?: string
  tool_calls?: unknown[]
  status?: 'completed' | 'interrupted' | 'failed' | 'streaming'
  created_at: string
  ordinal: number
}

/** A streaming event from the agent. */
export interface AgentEvent {
  type: EventType
  content?: string
  name?: string
  input?: Record<string, unknown>
  output?: string
  tool_name?: string
  tool_args?: Record<string, unknown>
  tool_call_id?: string
  widget_type?: WidgetType
  data?: Record<string, unknown>
  from_provider_id?: string | null
  to_provider_id?: string
  reason?: string
}

/**
 * Send a chat message and get a complete response.
 */
export async function sendMessage(
  message: string,
  sessionId?: string,
  skill?: string,
  providerId?: string,
): Promise<string> {
  const body: Record<string, unknown> = { message }
  if (sessionId) body.session_id = sessionId
  if (skill) body.skill = skill
  if (providerId) body.provider_id = providerId

  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }

  const data = await response.json()
  return data.response
}

/**
 * Stream a chat response via SSE.
 * Yields AgentEvent objects for real-time UI updates.
 *
 * The language is sent via X-Language header to the backend for
 * multi-language prompt selection.
 */
export async function* streamMessage(
  message: string,
  sessionId?: string,
  skill?: string,
  language: string = 'en',
  providerId?: string,
  signal?: AbortSignal,
): AsyncGenerator<AgentEvent> {
  const body: Record<string, unknown> = { message }
  if (sessionId) body.session_id = sessionId
  if (skill) body.skill = skill
  if (providerId) body.provider_id = providerId

  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Language': language,
    },
    body: JSON.stringify(body),
    signal,
  })

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6).trim()
        if (data === '[DONE]') return
        try {
          yield JSON.parse(data) as AgentEvent
        } catch {
          // Skip malformed JSON
        }
      }
    }
  }
}

/**
 * Persist a partial assistant response when the user interrupts streaming.
 */
export async function interruptSession(
  sessionId: string,
  request: { user_message: string; assistant_content: string },
): Promise<SessionDetail> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/interrupt`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

/**
 * Persist a partial assistant response with an explicit terminal status.
 */
export async function persistPartialResponse(
  sessionId: string,
  request: {
    user_message: string
    assistant_content: string
    assistant_status: 'interrupted' | 'failed'
  },
): Promise<SessionDetail> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/partial-response`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

/**
 * Fetch the list of available tools.
 */
export async function fetchTools(): Promise<ToolInfo[]> {
  const response = await fetch(`${API_BASE}/tools`)
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

/**
 * Fetch the list of available skills.
 */
export async function fetchSkills(): Promise<SkillInfo[]> {
  const response = await fetch(`${API_BASE}/skills`)
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

/**
 * List all sessions.
 */
export async function listSessions(): Promise<SessionInfo[]> {
  const response = await fetch(`${API_BASE}/sessions`)
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

/**
 * Create a new session.
 */
export async function createSession(title: string = ''): Promise<SessionInfo> {
  const response = await fetch(`${API_BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

/**
 * Get a session with its message history.
 */
export async function getSession(sessionId: string): Promise<SessionDetail> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}`)
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

export async function selectSessionVersion(
  sessionId: string,
  versionGroupId: string,
  nodeId: string,
): Promise<SessionDetail> {
  const response = await fetch(
    `${API_BASE}/sessions/${sessionId}/version-groups/${versionGroupId}/select`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node_id: nodeId }),
    },
  )
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

export async function retrySessionNode(sessionId: string, nodeId: string): Promise<SessionDetail> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/nodes/${nodeId}/retry`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

export async function editSessionNode(
  sessionId: string,
  nodeId: string,
  content: string,
): Promise<SessionDetail> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/nodes/${nodeId}/edit`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

/**
 * Delete a session.
 */
export async function deleteSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
}

/**
 * Update session-level provider selection and fallback mode.
 */
export async function updateSessionPreferences(
  sessionId: string,
  request: UpdateSessionPreferencesRequest,
): Promise<SessionInfo> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/preferences`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

/**
 * Update mutable session fields such as the title.
 */
export async function updateSession(
  sessionId: string,
  request: { title: string },
): Promise<SessionInfo> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

/**
 * Approve or reject a pending sensitive tool call.
 */
export async function approveToolCall(
  toolCallId: string,
  approved: boolean,
): Promise<{ ok: boolean }> {
  const response = await fetch(`${API_BASE}/chat/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tool_call_id: toolCallId, approved }),
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

/**
 * Check if the backend is healthy.
 */
export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/health`)
    return response.ok
  } catch {
    return false
  }
}

// ---------- Campus News ----------

/** Compact campus news article from the backend mock source. */
export type CampusNewsSourceType =
  | 'mock'
  | 'email'
  | 'wechat'
  | 'official_site'
  | 'rss'
  | 'api'
  | 'manual'
  | 'unknown'

export interface CampusNewsArticle {
  id: string
  title: string
  date: string
  category: string
  summary: string
  source: string
  url: string
  source_type?: CampusNewsSourceType
  source_name?: string
  source_id?: string
  external_id?: string
  author?: string
  tags?: string[]
  raw_metadata?: Record<string, unknown>
}

/** Full campus news article detail. */
export interface CampusNewsArticleDetail extends CampusNewsArticle {
  content: string
}

export interface CampusNewsReportArticleRef {
  id: string
  title: string
  date: string
  category: string
  source: string
  source_type?: CampusNewsSourceType
  summary: string
}

export interface CampusNewsReport {
  title: string
  generated_at: string
  filter_text: string
  article_count: number
  summary: string
  key_points: string[]
  action_items: string[]
  articles: CampusNewsReportArticleRef[]
}

/** Response for date and keyword campus news queries. */
export interface CampusNewsListResponse {
  date: string | null
  query: string | null
  mode: 'daily' | 'search' | 'latest'
  count: number
  articles: CampusNewsArticle[]
}

/** Fetch campus news. Date and keyword filters are combined when both are provided. */
export async function fetchCampusNews(
  options: {
    targetDate?: string
    query?: string
    source?: CampusNewsSourceType | 'all'
    limit?: number
  } = {},
): Promise<CampusNewsListResponse> {
  const params = new URLSearchParams()
  if (options.targetDate) params.set('target_date', options.targetDate)
  if (options.query) params.set('query', options.query)
  if (options.source && options.source !== 'all') params.set('source', options.source)
  if (options.limit) params.set('limit', String(options.limit))

  const qs = params.toString()
  const response = await fetch(`${API_BASE}/news${qs ? `?${qs}` : ''}`)
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

/** Fetch latest campus news, independent of date. */
export async function fetchLatestCampusNews(limit: number = 10): Promise<CampusNewsListResponse> {
  const response = await fetch(`${API_BASE}/news/latest?limit=${limit}`)
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

/** Fetch full detail for one campus news article. */
export async function fetchCampusNewsDetail(newsId: string): Promise<CampusNewsArticleDetail> {
  const response = await fetch(`${API_BASE}/news/${encodeURIComponent(newsId)}`)
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

/** Generate an AI campus news report for the current filters. */
export async function generateCampusNewsReport(
  options: {
    targetDate?: string
    query?: string
    source?: CampusNewsSourceType | 'all'
    limit?: number
  } = {},
): Promise<CampusNewsReport> {
  const response = await fetch(`${API_BASE}/news/report`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      target_date: options.targetDate || null,
      query: options.query || null,
      source: options.source || 'all',
      limit: options.limit || 20,
    }),
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

// ---------- Daily Campus News Push ----------

export interface NewsPushSettings {
  enabled: boolean
  push_time: string
  limit: number
}

export async function fetchNewsPushSettings(): Promise<NewsPushSettings> {
  const response = await fetch(`${API_BASE}/news/push/settings`)
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

export async function saveNewsPushSettings(settings: NewsPushSettings): Promise<NewsPushSettings> {
  const response = await fetch(`${API_BASE}/news/push/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

// ---------- Deadlines ----------

/** Date classification for a deadline task (mirrors backend DateType). */
export const DateType = {
  NO_DATE: 'no_date',
  MOMENT_DAY: 'moment_day',
  MOMENT_HM: 'moment_hm',
  PERIOD_DAY: 'period_day',
  PERIOD_HM: 'period_hm',
} as const
export type DateTypeValue = (typeof DateType)[keyof typeof DateType]

/** A single deadline record from the backend. */
export interface DeadlineInfo {
  id: string
  title: string
  course: string
  due_date: string
  priority: string
  source: string
  description: string
  date_type: DateTypeValue
  start_date: string
  completed: boolean
}

/** A candidate that duplicates an existing record (from sync-preview). */
export interface DuplicateEntry {
  candidate: DeadlineInfo
  existing_id: string
}

/** Response from the sync-preview endpoint. */
export interface SyncPreviewResult {
  new_tasks: DeadlineInfo[]
  duplicate_tasks: DuplicateEntry[]
}

/** Response from the sync-commit endpoint. */
export interface SyncCommitResult {
  added: DeadlineInfo[]
}

/**
 * Fetch stored deadlines with optional filters.
 */
export async function fetchDeadlines(course?: string, priority?: string): Promise<DeadlineInfo[]> {
  const params = new URLSearchParams()
  if (course) params.set('course', course)
  if (priority) params.set('priority', priority)
  const qs = params.toString()
  const url = `${API_BASE}/deadlines${qs ? `?${qs}` : ''}`

  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  const data = await response.json()
  return data.deadlines
}

// ---------- Quiz Evaluation ----------

/** A single quiz question for evaluation request. */
export interface QuizQuestionForEval {
  id: number
  type: 'multiple_choice' | 'true_false' | 'fill_blank' | 'short_answer'
  question: string
  options: string[] | null
  correct_answer: string
  explanation: string | null
  score: number
}

/** Evaluation result for a single question. */
export interface QuestionEvaluation {
  score: number
  standard_answer: string
  analysis: string
  total_score_included: boolean
}

/** Evaluation result for the whole quiz. */
export interface QuizEvaluationResult {
  evaluations: Record<string, QuestionEvaluation>
}

/**
 * Evaluate quiz answers using LLM.
 * fill_blank and short_answer questions are sent to LLM for evaluation;
 * multiple_choice and true_false are auto-scored.
 *
 * The language is determined by the frontend i18n locale and sent via
 * the X-Language header to the backend for prompt selection.
 */
export async function evaluateQuiz(
  questions: QuizQuestionForEval[],
  userAnswers: Record<string, string>,
  useAiGrading: boolean = true,
  language: string = 'en',
): Promise<QuizEvaluationResult> {
  const response = await fetch(`${API_BASE}/evaluate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Language': language,
    },
    body: JSON.stringify({
      questions,
      user_answers: userAnswers,
      use_ai_grading: useAiGrading,
    }),
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

/**
 * Toggle the completed status of a deadline.
 */
export async function toggleDeadlineComplete(
  id: string,
  completed: boolean,
): Promise<{ id: string; completed: boolean }> {
  const response = await fetch(`${API_BASE}/deadlines/${id}/complete`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ completed }),
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

/**
 * Preview sync results — separate new tasks from duplicates.
 */
export async function syncPreview(deadlines: DeadlineInfo[]): Promise<SyncPreviewResult> {
  const response = await fetch(`${API_BASE}/deadlines/sync-preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ deadlines }),
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

/**
 * Commit confirmed tasks from the sync preview.
 */
export async function syncCommit(tasks: DeadlineInfo[]): Promise<SyncCommitResult> {
  const response = await fetch(`${API_BASE}/deadlines/sync-commit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tasks }),
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

/**
 * Delete a deadline by ID.
 */
export async function deleteDeadline(id: string): Promise<{ status: string; id: string }> {
  const response = await fetch(`${API_BASE}/deadlines/${id}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

/** Fields for creating a new deadline (title is required). */
export interface CreateDeadlineFields {
  title: string
  course?: string
  due_date?: string
  priority?: string
  description?: string
  date_type?: DateTypeValue
  start_date?: string
}

/**
 * Create a new deadline via POST.
 */
export async function createDeadline(fields: CreateDeadlineFields): Promise<DeadlineInfo> {
  const response = await fetch(`${API_BASE}/deadlines`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(fields),
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}

/** Fields that can be updated on a deadline (all optional). */
export interface UpdateDeadlineFields {
  title?: string
  course?: string
  due_date?: string
  priority?: string
  description?: string
  date_type?: DateTypeValue
  start_date?: string
  completed?: boolean
}

/**
 * Update one or more fields of a deadline.
 */
export async function updateDeadline(
  id: string,
  fields: UpdateDeadlineFields,
): Promise<DeadlineInfo> {
  const response = await fetch(`${API_BASE}/deadlines/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(fields),
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  return response.json()
}
