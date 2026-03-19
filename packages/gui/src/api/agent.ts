/**
 * API client for the ReAct Agent backend.
 * Handles chat requests and SSE streaming.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

/** Tool information from the API. */
export interface ToolInfo {
  name: string
  description: string
  sensitivity: string
}

/** A streaming event from the agent. */
export interface AgentEvent {
  type: 'token' | 'tool_start' | 'tool_end'
  content?: string
  name?: string
  input?: Record<string, unknown>
  output?: string
}

/**
 * Send a chat message and get a complete response.
 */
export async function sendMessage(message: string): Promise<string> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
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
export async function* streamMessage(message: string): AsyncGenerator<AgentEvent> {
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
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
