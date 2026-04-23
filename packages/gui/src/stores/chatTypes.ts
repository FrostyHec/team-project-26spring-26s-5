/**
 * Domain model types for the chat feature.
 * All interfaces are defined here to keep chat.ts focused on store logic.
 */

import type { MessageRole, TraceStepType, ToolCallStatus, WidgetType } from './chatConstants'

/** A single message in the chat. */
export interface ChatMessage {
  id: string
  role: MessageRole
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
  /** Widget type key — one of the WIDGET_TYPES values. */
  widgetType?: WidgetType
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
  type: WidgetType
  data: Record<string, unknown>
}

/** A chat session with messages. */
export interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
  skill?: string
  /** Per-session widget state for the workspace panel. */
  widgetState?: WidgetState
  createdAt: Date
  updatedAt: Date
}
