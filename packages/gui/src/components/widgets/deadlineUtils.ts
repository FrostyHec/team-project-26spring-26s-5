/**
 * Utility helpers for deadline panel date logic.
 */

import { DateType, type DeadlineInfo, type DateTypeValue } from '@/api/agent'
import { TASK_STATUS, type TaskStatus } from './deadlineConstants'

/** Number of milliseconds in one day. */
const MS_PER_DAY = 86_400_000

/**
 * Return today's date string at midnight (local time) as `YYYY-MM-DD`.
 */
export function todayDateStr(): string {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/**
 * Extract just the date portion (`YYYY-MM-DD`) from an ISO string.
 */
export function toDateOnly(iso: string): string {
  return iso.slice(0, 10)
}

/**
 * Return the computed timeline status for a task.
 */
export function computeTaskStatus(task: DeadlineInfo): TaskStatus {
  if (task.completed) return TASK_STATUS.COMPLETED
  if (task.date_type === DateType.NO_DATE || !task.due_date) return TASK_STATUS.NO_DATE

  const today = todayDateStr()
  const dueDay = toDateOnly(task.due_date)

  if (dueDay < today) return TASK_STATUS.OVERDUE
  if (dueDay === today) return TASK_STATUS.TODAY
  return TASK_STATUS.UPCOMING
}

/**
 * Calculate progress percentage for a period task (0–100).
 * Returns 0 for non-period types or missing dates.
 */
export function computePeriodProgress(task: DeadlineInfo): number {
  if (
    (task.date_type !== DateType.PERIOD_DAY && task.date_type !== DateType.PERIOD_HM) ||
    !task.start_date ||
    !task.due_date
  ) {
    return 0
  }
  const start = new Date(task.start_date).getTime()
  const end = new Date(task.due_date).getTime()
  const now = Date.now()
  if (end <= start) return 100
  const progress = ((now - start) / (end - start)) * 100
  return Math.max(0, Math.min(100, Math.round(progress)))
}

/**
 * Format a due date for display, based on date_type.
 */
export function formatDueDate(task: DeadlineInfo): string {
  if (!task.due_date) return ''
  const d = new Date(task.due_date)
  const month = d.getMonth() + 1
  const day = d.getDate()

  if (task.date_type === DateType.MOMENT_HM || task.date_type === DateType.PERIOD_HM) {
    const hours = String(d.getHours()).padStart(2, '0')
    const minutes = String(d.getMinutes()).padStart(2, '0')
    return `${month}/${day} ${hours}:${minutes}`
  }
  return `${month}/${day}`
}

/**
 * Format a start date for display.
 */
export function formatStartDate(task: DeadlineInfo): string {
  if (!task.start_date) return ''
  const d = new Date(task.start_date)
  const month = d.getMonth() + 1
  const day = d.getDate()

  if (task.date_type === DateType.PERIOD_HM) {
    const hours = String(d.getHours()).padStart(2, '0')
    const minutes = String(d.getMinutes()).padStart(2, '0')
    return `${month}/${day} ${hours}:${minutes}`
  }
  return `${month}/${day}`
}

/**
 * Check whether a date_type represents a period (range) task.
 */
export function isPeriodType(dt: DateTypeValue): boolean {
  return dt === DateType.PERIOD_DAY || dt === DateType.PERIOD_HM
}

/**
 * Group tasks by their due date (YYYY-MM-DD) for timeline rendering.
 * Returns entries sorted by date ascending, with NO_DATE tasks excluded.
 */
export function groupByDate(tasks: DeadlineInfo[]): Map<string, DeadlineInfo[]> {
  const map = new Map<string, DeadlineInfo[]>()
  for (const t of tasks) {
    if (t.date_type === DateType.NO_DATE || !t.due_date) continue
    const key = toDateOnly(t.due_date)
    const list = map.get(key) ?? []
    list.push(t)
    map.set(key, list)
  }
  // Sort by key
  return new Map([...map.entries()].sort(([a], [b]) => a.localeCompare(b)))
}

/**
 * Get the Monday of the week that contains the given date.
 */
export function getWeekStart(date: Date): Date {
  const d = new Date(date)
  const day = d.getDay()
  // JS getDay: 0=Sun, 1=Mon ... 6=Sat → offset to Monday
  const diff = day === 0 ? -6 : 1 - day
  d.setDate(d.getDate() + diff)
  d.setHours(0, 0, 0, 0)
  return d
}

/**
 * Generate an array of 7 Date objects (Mon–Sun) for a given week start.
 */
export function getWeekDays(weekStart: Date): Date[] {
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(weekStart)
    d.setDate(d.getDate() + i)
    return d
  })
}

/**
 * Generate the grid of dates for a month view (6 rows × 7 cols starting Mon).
 */
export function getMonthGrid(year: number, month: number): Date[] {
  const firstDay = new Date(year, month, 1)
  const startOffset = firstDay.getDay() === 0 ? -6 : 1 - firstDay.getDay()
  const gridStart = new Date(year, month, 1 + startOffset)

  return Array.from({ length: 42 }, (_, i) => {
    const d = new Date(gridStart)
    d.setDate(d.getDate() + i)
    return d
  })
}

/**
 * Format a Date as `YYYY-MM-DD`.
 */
export function dateToStr(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/**
 * Get tasks that fall on a specific date string (YYYY-MM-DD).
 * A task "falls on" a date if:
 * - For moment types: due_date matches the date
 * - For period types: the date is within [start_date, due_date]
 */
export function tasksForDate(tasks: DeadlineInfo[], dateStr: string): DeadlineInfo[] {
  return tasks.filter((t) => {
    if (t.date_type === DateType.NO_DATE || !t.due_date) return false
    const dueDay = toDateOnly(t.due_date)
    if (isPeriodType(t.date_type) && t.start_date) {
      const startDay = toDateOnly(t.start_date)
      return dateStr >= startDay && dateStr <= dueDay
    }
    return dueDay === dateStr
  })
}

/** Short day-of-week labels (Mon–Sun). */
export const WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as const

/** Short month names. */
export const MONTH_LABELS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
] as const
