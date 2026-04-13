/**
 * Constants for the deadline panel widget views and task status.
 */

/** Panel view mode tabs. */
export const PANEL_VIEWS = {
  TASKS: 'tasks',
  WEEK: 'week',
  MONTH: 'month',
} as const

export type PanelView = (typeof PANEL_VIEWS)[keyof typeof PANEL_VIEWS]

/** Tab definitions for the panel toolbar. */
export const PANEL_VIEW_TABS: ReadonlyArray<{ key: PanelView; label: string; icon: string }> = [
  { key: PANEL_VIEWS.TASKS, label: 'Tasks', icon: 'list' },
  { key: PANEL_VIEWS.WEEK, label: 'Week', icon: 'calendar-days' },
  { key: PANEL_VIEWS.MONTH, label: 'Month', icon: 'calendar' },
] as const

/** Computed task timeline status (based on date + completed). */
export const TASK_STATUS = {
  OVERDUE: 'overdue',
  TODAY: 'today',
  UPCOMING: 'upcoming',
  NO_DATE: 'no_date',
  COMPLETED: 'completed',
} as const

export type TaskStatus = (typeof TASK_STATUS)[keyof typeof TASK_STATUS]

/** Tailwind background class per priority level (shared across components). */
export const PRIORITY_COLORS: Record<string, string> = {
  high: 'bg-red-500',
  medium: 'bg-yellow-400',
  low: 'bg-green-400',
} as const

/** Maximum task-count dots shown per cell in month-view. */
export const MAX_DOTS_PER_CELL = 4

/** Number of leading characters shown when previewing a UUID. */
export const ID_PREVIEW_LENGTH = 8
