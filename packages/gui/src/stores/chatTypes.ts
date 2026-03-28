/**
 * Domain model types for the chat feature.
 * All interfaces are defined here to keep chat.ts focused on store logic.
 */

import type { TraceStepType, ToolCallStatus } from './chatConstants'

/** A single message in the chat. */
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  toolCalls?: ToolCallInfo[]
  traceSteps?: TraceStep[]
  loopActive?: boolean
  timestamp: Date
}

/** Information about a tool call during agent reasoning. */
export interface ToolCallInfo {
  name: string
  input: Record<string, unknown>
  output?: string
  status: ToolCallStatus
}

/** A step in the linear ReAct trace. */
export interface TraceStep {
  type: TraceStepType
  content?: string
  name?: string
  input?: Record<string, unknown>
  output?: string
  widgetType?: string
  widgetData?: Record<string, unknown>
}

/** Pending approval dialog state. */
export interface PendingApproval {
  toolName: string
  toolArgs: Record<string, unknown>
  toolCallId: string
}

/** Widget display state for the right panel. */
export interface WidgetState {
  type: string
  data: Record<string, unknown>
}

/** A chat session with messages. */
export interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
  skill?: string
  createdAt: Date
  updatedAt: Date
}
