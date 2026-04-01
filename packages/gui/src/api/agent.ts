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
}

/** Session detail with messages. */
export interface SessionDetail {
  session: SessionInfo
  messages: SessionMessage[]
}

/** A persisted message from the session store. */
export interface SessionMessage {
  id: number
  session_id: string
  role: SessionMessageRole
  content: string
  tool_call_id?: string
  tool_calls?: unknown[]
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
}

/**
 * Send a chat message and get a complete response.
 */
export async function sendMessage(
  message: string,
  sessionId?: string,
  skill?: string,
): Promise<string> {
  const body: Record<string, unknown> = { message }
  if (sessionId) body.session_id = sessionId
  if (skill) body.skill = skill

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
 */
export async function* streamMessage(
  message: string,
  sessionId?: string,
  skill?: string,
): AsyncGenerator<AgentEvent> {
  const body: Record<string, unknown> = { message }
  if (sessionId) body.session_id = sessionId
  if (skill) body.skill = skill

  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
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

// ---------- Deadlines ----------

/** A single deadline record from the backend. */
export interface DeadlineInfo {
  id: string
  title: string
  course: string
  due_date: string
  priority: string
  source: string
  description: string
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
