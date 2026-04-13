import { describe, it, expect, vi, afterEach } from 'vitest'
import { DateType, type DeadlineInfo } from '@/api/agent'
import { TASK_STATUS } from '../deadlineConstants'
import {
  todayDateStr,
  toDateOnly,
  computeTaskStatus,
  computePeriodProgress,
  formatDueDate,
  formatStartDate,
  isPeriodType,
  groupByDate,
  getWeekStart,
  getWeekDays,
  getMonthGrid,
  dateToStr,
  tasksForDate,
  WEEKDAY_LABELS,
  MONTH_LABELS,
} from '../deadlineUtils'

// ── helpers ──────────────────────────────────────────────────────

/** Build a minimal DeadlineInfo with sensible defaults. */
function makeTask(overrides: Partial<DeadlineInfo> = {}): DeadlineInfo {
  return {
    id: 'test-id',
    title: 'Test Task',
    course: '',
    due_date: '2026-04-15',
    priority: 'medium',
    source: 'manual',
    description: '',
    date_type: DateType.MOMENT_DAY,
    start_date: '',
    completed: false,
    ...overrides,
  }
}

// ── todayDateStr ─────────────────────────────────────────────────

describe('todayDateStr', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns YYYY-MM-DD for a normal date', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 3, 12)) // April 12 local
    expect(todayDateStr()).toBe('2026-04-12')
  })

  it('uses local time, not UTC', () => {
    // The function should use local date components, so setting a
    // specific local date should always produce that date string.
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 0, 1, 23, 59)) // Jan 1 23:59 local
    expect(todayDateStr()).toBe('2026-01-01')
  })

  it('pads single-digit month and day', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 0, 5)) // Jan 5
    expect(todayDateStr()).toBe('2026-01-05')
  })
})

// ── toDateOnly ───────────────────────────────────────────────────

describe('toDateOnly', () => {
  it('extracts the first 10 characters', () => {
    expect(toDateOnly('2026-04-15T14:30:00Z')).toBe('2026-04-15')
  })

  it('returns the input when already a date-only string', () => {
    expect(toDateOnly('2026-04-15')).toBe('2026-04-15')
  })
})

// ── computeTaskStatus ────────────────────────────────────────────

describe('computeTaskStatus', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns COMPLETED for a completed task', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 3, 12))
    const task = makeTask({ completed: true, due_date: '2026-04-10' })
    expect(computeTaskStatus(task)).toBe(TASK_STATUS.COMPLETED)
  })

  it('returns NO_DATE for no_date type', () => {
    const task = makeTask({ date_type: DateType.NO_DATE, due_date: '' })
    expect(computeTaskStatus(task)).toBe(TASK_STATUS.NO_DATE)
  })

  it('returns NO_DATE for empty due_date', () => {
    const task = makeTask({ due_date: '' })
    expect(computeTaskStatus(task)).toBe(TASK_STATUS.NO_DATE)
  })

  it('returns OVERDUE when due_date < today', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 3, 15))
    const task = makeTask({ due_date: '2026-04-10' })
    expect(computeTaskStatus(task)).toBe(TASK_STATUS.OVERDUE)
  })

  it('returns TODAY when due_date == today', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 3, 15))
    const task = makeTask({ due_date: '2026-04-15' })
    expect(computeTaskStatus(task)).toBe(TASK_STATUS.TODAY)
  })

  it('returns UPCOMING when due_date > today', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 3, 10))
    const task = makeTask({ due_date: '2026-04-15' })
    expect(computeTaskStatus(task)).toBe(TASK_STATUS.UPCOMING)
  })
})

// ── computePeriodProgress ────────────────────────────────────────

describe('computePeriodProgress', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns 0 for non-period types', () => {
    const task = makeTask({ date_type: DateType.MOMENT_DAY })
    expect(computePeriodProgress(task)).toBe(0)
  })

  it('returns 0 when start_date is missing', () => {
    const task = makeTask({
      date_type: DateType.PERIOD_DAY,
      start_date: '',
      due_date: '2026-04-20',
    })
    expect(computePeriodProgress(task)).toBe(0)
  })

  it('returns 0 when due_date is missing', () => {
    const task = makeTask({
      date_type: DateType.PERIOD_DAY,
      start_date: '2026-04-10',
      due_date: '',
    })
    expect(computePeriodProgress(task)).toBe(0)
  })

  it('returns 100 when end <= start', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 3, 15))
    const task = makeTask({
      date_type: DateType.PERIOD_DAY,
      start_date: '2026-04-20',
      due_date: '2026-04-10',
    })
    expect(computePeriodProgress(task)).toBe(100)
  })

  it('returns 50 at midpoint of period', () => {
    vi.useFakeTimers()
    // Use explicit local-midnight timestamps to avoid UTC parsing offsets.
    // Period: Apr 10 00:00 → Apr 20 00:00 (local), now = Apr 15 00:00 (local)
    vi.setSystemTime(new Date(2026, 3, 15, 0, 0, 0))
    const task = makeTask({
      date_type: DateType.PERIOD_DAY,
      start_date: new Date(2026, 3, 10, 0, 0, 0).toISOString(),
      due_date: new Date(2026, 3, 20, 0, 0, 0).toISOString(),
    })
    expect(computePeriodProgress(task)).toBe(50)
  })

  it('clamps to 0 when now < start', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 3, 5))
    const task = makeTask({
      date_type: DateType.PERIOD_HM,
      start_date: '2026-04-10T00:00',
      due_date: '2026-04-20T00:00',
    })
    expect(computePeriodProgress(task)).toBe(0)
  })

  it('clamps to 100 when now > end', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 3, 25))
    const task = makeTask({
      date_type: DateType.PERIOD_DAY,
      start_date: '2026-04-10',
      due_date: '2026-04-20',
    })
    expect(computePeriodProgress(task)).toBe(100)
  })
})

// ── formatDueDate ────────────────────────────────────────────────

describe('formatDueDate', () => {
  it('returns empty string for missing due_date', () => {
    expect(formatDueDate(makeTask({ due_date: '' }))).toBe('')
  })

  it('returns month/day for MOMENT_DAY', () => {
    const task = makeTask({ due_date: '2026-04-05', date_type: DateType.MOMENT_DAY })
    expect(formatDueDate(task)).toBe('4/5')
  })

  it('includes HH:MM for MOMENT_HM', () => {
    const task = makeTask({ due_date: '2026-04-05T14:30', date_type: DateType.MOMENT_HM })
    expect(formatDueDate(task)).toBe('4/5 14:30')
  })

  it('includes HH:MM for PERIOD_HM', () => {
    const task = makeTask({ due_date: '2026-04-05T09:00', date_type: DateType.PERIOD_HM })
    expect(formatDueDate(task)).toBe('4/5 09:00')
  })
})

// ── formatStartDate ──────────────────────────────────────────────

describe('formatStartDate', () => {
  it('returns empty string for missing start_date', () => {
    expect(formatStartDate(makeTask({ start_date: '' }))).toBe('')
  })

  it('returns month/day for PERIOD_DAY', () => {
    const task = makeTask({
      start_date: '2026-04-01',
      date_type: DateType.PERIOD_DAY,
    })
    expect(formatStartDate(task)).toBe('4/1')
  })

  it('includes HH:MM for PERIOD_HM', () => {
    const task = makeTask({
      start_date: '2026-04-01T08:30',
      date_type: DateType.PERIOD_HM,
    })
    expect(formatStartDate(task)).toBe('4/1 08:30')
  })
})

// ── isPeriodType ─────────────────────────────────────────────────

describe('isPeriodType', () => {
  it('returns true for PERIOD_DAY', () => {
    expect(isPeriodType(DateType.PERIOD_DAY)).toBe(true)
  })

  it('returns true for PERIOD_HM', () => {
    expect(isPeriodType(DateType.PERIOD_HM)).toBe(true)
  })

  it('returns false for MOMENT_DAY', () => {
    expect(isPeriodType(DateType.MOMENT_DAY)).toBe(false)
  })

  it('returns false for NO_DATE', () => {
    expect(isPeriodType(DateType.NO_DATE)).toBe(false)
  })
})

// ── groupByDate ──────────────────────────────────────────────────

describe('groupByDate', () => {
  it('groups tasks by due_date', () => {
    const tasks = [
      makeTask({ id: 'a', due_date: '2026-04-15' }),
      makeTask({ id: 'b', due_date: '2026-04-15' }),
      makeTask({ id: 'c', due_date: '2026-04-16' }),
    ]
    const result = groupByDate(tasks)
    expect(result.size).toBe(2)
    expect(result.get('2026-04-15')?.length).toBe(2)
    expect(result.get('2026-04-16')?.length).toBe(1)
  })

  it('excludes NO_DATE tasks', () => {
    const tasks = [
      makeTask({ id: 'a', due_date: '2026-04-15' }),
      makeTask({ id: 'b', date_type: DateType.NO_DATE, due_date: '' }),
    ]
    const result = groupByDate(tasks)
    expect(result.size).toBe(1)
  })

  it('excludes tasks with empty due_date', () => {
    const tasks = [makeTask({ id: 'a', due_date: '' })]
    const result = groupByDate(tasks)
    expect(result.size).toBe(0)
  })

  it('returns entries sorted by date ascending', () => {
    const tasks = [
      makeTask({ id: 'b', due_date: '2026-04-20' }),
      makeTask({ id: 'a', due_date: '2026-04-10' }),
    ]
    const keys = [...groupByDate(tasks).keys()]
    expect(keys).toEqual(['2026-04-10', '2026-04-20'])
  })
})

// ── getWeekStart ─────────────────────────────────────────────────

describe('getWeekStart', () => {
  it('returns Monday for a Wednesday', () => {
    const wed = new Date(2026, 3, 15) // Wed Apr 15 2026
    const mon = getWeekStart(wed)
    expect(mon.getDay()).toBe(1)
    expect(dateToStr(mon)).toBe('2026-04-13')
  })

  it('returns Monday for a Monday (unchanged)', () => {
    const mon = new Date(2026, 3, 13) // Mon Apr 13
    const result = getWeekStart(mon)
    expect(dateToStr(result)).toBe('2026-04-13')
  })

  it('returns previous Monday for a Sunday', () => {
    const sun = new Date(2026, 3, 19) // Sun Apr 19
    const result = getWeekStart(sun)
    expect(dateToStr(result)).toBe('2026-04-13')
  })

  it('does not mutate the original date', () => {
    const original = new Date(2026, 3, 15)
    const originalStr = original.toISOString()
    getWeekStart(original)
    expect(original.toISOString()).toBe(originalStr)
  })
})

// ── getWeekDays ──────────────────────────────────────────────────

describe('getWeekDays', () => {
  it('returns 7 consecutive days', () => {
    const mon = new Date(2026, 3, 13)
    const days = getWeekDays(mon)
    expect(days).toHaveLength(7)
  })

  it('starts on the given date and ends 6 days later', () => {
    const mon = new Date(2026, 3, 13)
    const days = getWeekDays(mon)
    expect(dateToStr(days[0]!)).toBe('2026-04-13')
    expect(dateToStr(days[6]!)).toBe('2026-04-19')
  })
})

// ── getMonthGrid ─────────────────────────────────────────────────

describe('getMonthGrid', () => {
  it('returns exactly 42 dates (6 rows × 7 cols)', () => {
    const grid = getMonthGrid(2026, 3) // April 2026
    expect(grid).toHaveLength(42)
  })

  it('starts on a Monday', () => {
    const grid = getMonthGrid(2026, 3) // April 2026 (Wed start)
    expect(grid[0]!.getDay()).toBe(1) // Monday
  })

  it('includes dates from the current month', () => {
    const grid = getMonthGrid(2026, 3) // April 2026
    const aprilDates = grid.filter((d) => d.getMonth() === 3)
    expect(aprilDates.length).toBe(30) // April has 30 days
  })

  it('handles a month starting on Monday', () => {
    // June 2026 starts on Monday
    const grid = getMonthGrid(2026, 5)
    expect(dateToStr(grid[0]!)).toBe('2026-06-01')
  })
})

// ── dateToStr ────────────────────────────────────────────────────

describe('dateToStr', () => {
  it('formats a date as YYYY-MM-DD', () => {
    expect(dateToStr(new Date(2026, 3, 5))).toBe('2026-04-05')
  })

  it('pads single-digit month and day', () => {
    expect(dateToStr(new Date(2026, 0, 1))).toBe('2026-01-01')
  })
})

// ── tasksForDate ─────────────────────────────────────────────────

describe('tasksForDate', () => {
  it('returns moment tasks whose due_date matches', () => {
    const tasks = [
      makeTask({ id: 'a', due_date: '2026-04-15' }),
      makeTask({ id: 'b', due_date: '2026-04-16' }),
    ]
    const result = tasksForDate(tasks, '2026-04-15')
    expect(result).toHaveLength(1)
    expect(result[0]!.id).toBe('a')
  })

  it('excludes NO_DATE tasks', () => {
    const tasks = [makeTask({ date_type: DateType.NO_DATE, due_date: '' })]
    expect(tasksForDate(tasks, '2026-04-15')).toHaveLength(0)
  })

  it('includes period tasks when date falls within range', () => {
    const task = makeTask({
      id: 'p',
      date_type: DateType.PERIOD_DAY,
      start_date: '2026-04-10',
      due_date: '2026-04-20',
    })
    expect(tasksForDate([task], '2026-04-15')).toHaveLength(1)
    expect(tasksForDate([task], '2026-04-10')).toHaveLength(1) // start bound
    expect(tasksForDate([task], '2026-04-20')).toHaveLength(1) // end bound
  })

  it('excludes period tasks outside range', () => {
    const task = makeTask({
      date_type: DateType.PERIOD_DAY,
      start_date: '2026-04-10',
      due_date: '2026-04-20',
    })
    expect(tasksForDate([task], '2026-04-09')).toHaveLength(0)
    expect(tasksForDate([task], '2026-04-21')).toHaveLength(0)
  })

  it('treats period tasks without start_date as moment tasks', () => {
    const task = makeTask({
      date_type: DateType.PERIOD_DAY,
      start_date: '',
      due_date: '2026-04-15',
    })
    expect(tasksForDate([task], '2026-04-15')).toHaveLength(1)
    expect(tasksForDate([task], '2026-04-14')).toHaveLength(0)
  })
})

// ── constant arrays ──────────────────────────────────────────────

describe('constants', () => {
  it('WEEKDAY_LABELS has 7 entries starting with Mon', () => {
    expect(WEEKDAY_LABELS).toHaveLength(7)
    expect(WEEKDAY_LABELS[0]).toBe('Mon')
    expect(WEEKDAY_LABELS[6]).toBe('Sun')
  })

  it('MONTH_LABELS has 12 entries starting with Jan', () => {
    expect(MONTH_LABELS).toHaveLength(12)
    expect(MONTH_LABELS[0]).toBe('Jan')
    expect(MONTH_LABELS[11]).toBe('Dec')
  })
})
