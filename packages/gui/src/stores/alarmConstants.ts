/**
 * Constants for the deadline alarm feature.
 *
 * Values must match the backend ``AlarmLeadTime`` and ``AlarmChannel``
 * StrEnum definitions exactly.
 */

/** Alarm lead-time identifiers (mirrors backend ``AlarmLeadTime``). */
export const ALARM_LEAD_TIMES = {
  HOUR_1: 'hour_1',
  HOUR_3: 'hour_3',
  HOUR_6: 'hour_6',
  HOUR_12: 'hour_12',
  DAY_1: 'day_1',
  DAY_3: 'day_3',
  WEEK_1: 'week_1',
} as const

export type AlarmLeadTime = (typeof ALARM_LEAD_TIMES)[keyof typeof ALARM_LEAD_TIMES]

/** Hour-based lead times — only applicable to tasks with hour:minute precision. */
export const HOUR_BASED_LEAD_TIMES = new Set<AlarmLeadTime>([
  ALARM_LEAD_TIMES.HOUR_1,
  ALARM_LEAD_TIMES.HOUR_3,
  ALARM_LEAD_TIMES.HOUR_6,
  ALARM_LEAD_TIMES.HOUR_12,
])

/** Notification channel identifiers (mirrors backend ``AlarmChannel``). */
export const ALARM_CHANNELS = {
  IN_APP: 'in_app',
  EMAIL: 'email',
} as const

export type AlarmChannel = (typeof ALARM_CHANNELS)[keyof typeof ALARM_CHANNELS]

/** Deadline priority identifiers (mirrors backend ``DeadlinePriority``). */
export const DEADLINE_PRIORITIES = {
  HIGH: 'high',
  MEDIUM: 'medium',
  LOW: 'low',
} as const

export type DeadlinePriority = (typeof DEADLINE_PRIORITIES)[keyof typeof DEADLINE_PRIORITIES]
