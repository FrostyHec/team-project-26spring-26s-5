/**
 * Constants matching backend enums.
 * These are kept as plain const objects (not TS enums) to allow
 * easy runtime iteration and type narrowing with `as const`.
 */

/** Event types matching backend EventType StrEnum. */
export const EVENT_TYPES = {
  TOKEN: 'token',
  TOOL_START: 'tool_start',
  TOOL_END: 'tool_end',
  THINKING: 'thinking',
  LOOP_START: 'loop_start',
  LOOP_END: 'loop_end',
  APPROVAL_REQUEST: 'approval_request',
  WIDGET_DISPLAY: 'widget_display',
  ERROR: 'error',
} as const

export type EventType = (typeof EVENT_TYPES)[keyof typeof EVENT_TYPES]

/** Widget types matching backend WidgetType StrEnum. */
export const WIDGET_TYPES = {
  CALENDAR: 'calendar',
  DOCUMENT: 'document',
  WEB_PREVIEW: 'web_preview',
  COURSE_CARDS: 'course_cards',
  SOURCES: 'sources',
  NEWS_DIGEST: 'news_digest',
  INBOX: 'inbox',
  EMPTY: 'empty',
} as const

export type WidgetType = (typeof WIDGET_TYPES)[keyof typeof WIDGET_TYPES]

/** Message role values used throughout the app. */
export const MESSAGE_ROLES = {
  USER: 'user',
  ASSISTANT: 'assistant',
} as const

export type MessageRole = (typeof MESSAGE_ROLES)[keyof typeof MESSAGE_ROLES]

/** Trace step type values. */
export const TRACE_STEP_TYPES = {
  LOOP_START: 'loop_start',
  THINKING: 'thinking',
  TOOL_START: 'tool_start',
  TOOL_END: 'tool_end',
  LOOP_END: 'loop_end',
  APPROVAL_REQUEST: 'approval_request',
  WIDGET_DISPLAY: 'widget_display',
} as const

export type TraceStepType = (typeof TRACE_STEP_TYPES)[keyof typeof TRACE_STEP_TYPES]

/** Tool call status values. */
export const TOOL_CALL_STATUS = {
  RUNNING: 'running',
  COMPLETED: 'completed',
  ERROR: 'error',
} as const

export type ToolCallStatus = (typeof TOOL_CALL_STATUS)[keyof typeof TOOL_CALL_STATUS]

/**
 * Persisted message role values from the backend session store.
 * These match the backend `MessageRole` StrEnum values and are used
 * when reconstructing messages from the session history API response.
 */
export const SESSION_MESSAGE_ROLES = {
  HUMAN: 'human',
  AI: 'ai',
  TOOL: 'tool',
  SYSTEM: 'system',
} as const

export type SessionMessageRole = (typeof SESSION_MESSAGE_ROLES)[keyof typeof SESSION_MESSAGE_ROLES]

/**
 * Tool names whose completion should trigger a deadline panel refresh.
 * When a TOOL_END event fires for any of these tools, the deadline
 * version counter is incremented so the widget auto-fetches fresh data.
 */
export const DEADLINE_MUTATING_TOOLS: ReadonlySet<string> = new Set([
  'add_deadline',
  'save_deadlines',
  'show_deadline_dashboard',
  'delete_deadline',
  'update_deadline',
])
