/**
 * Domain model types for the chat feature.
 * All interfaces are defined here to keep chat.ts focused on store logic.
 */

import type { FallbackMode, NodeSourceKind } from '@/api/agent'
import type {
  MessageRole,
  MessageStatus,
  SessionMessageRole,
  TraceStepType,
  ToolCallStatus,
  WidgetType,
} from './chatConstants'

/** A single message in the chat. */
export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  status?: MessageStatus
  nodeId?: string
  sourceKind?: NodeSourceKind
  sourceNodeId?: string | null
  versionGroupId?: string
  versionIndex?: number
  selectedVersionId?: string
  versionChoices?: ChatVersionChoice[]
  canEdit?: boolean
  canRetry?: boolean
  toolCalls?: ToolCallInfo[]
  traceSteps?: TraceStep[]
  loopActive?: boolean
  timestamp: Date
}

export interface ChatVersionChoice {
  nodeId: string
  role: SessionMessageRole
  versionIndex: number
  sourceKind: NodeSourceKind
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
  fromProviderId?: string | null
  toProviderId?: string
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
  visiblePath: string[]
  versionGroups: ChatVersionGroup[]
  nodeMap: Record<string, ChatSessionNode>
  skill?: string
  selectedProviderId?: string | null
  fallbackMode?: FallbackMode
  /** Per-session widget state for the workspace panel. */
  widgetState?: WidgetState
  createdAt: Date
  updatedAt: Date
}

export interface ChatSessionNode {
  id: string
  parentId?: string | null
  role: SessionMessageRole
  content: string
  status?: MessageStatus | 'streaming'
  versionGroupId: string
  versionIndex: number
  sourceKind: NodeSourceKind
  sourceNodeId?: string | null
  responseToNodeId?: string | null
  toolCalls?: ToolCallInfo[]
  traceSteps?: TraceStep[]
}

export interface ChatVersionGroup {
  versionGroupId: string
  nodeIds: string[]
  selectedNodeId: string
  positionInPath: number
}
