/**
 * API client for deadline alarm settings and pending notifications.
 * Communicates with ``/alarm-settings`` and ``/notifications`` endpoints.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

const ALARM_SETTINGS_ENDPOINT = `${API_BASE}/alarm-settings`
const NOTIFICATIONS_ENDPOINT = `${API_BASE}/notifications`

import type { AlarmLeadTime, AlarmChannel, DeadlinePriority } from '@/stores/alarmConstants'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Global deadline alarm configuration (mirrors backend AlarmSettings). */
export interface AlarmSettings {
  enabled: boolean
  lead_times: AlarmLeadTime[]
  channels: AlarmChannel[]
  enabled_priorities: DeadlinePriority[]
}

/** An unacknowledged in-app alarm notification. */
export interface PendingNotification {
  id: string
  message: string
  details: string[]
  created_at: string
}

// ---------------------------------------------------------------------------
// Alarm settings
// ---------------------------------------------------------------------------

/**
 * Fetch the current global alarm settings.
 *
 * @returns Current {@link AlarmSettings}.
 * @throws Error on network or server error.
 */
export async function getAlarmSettings(): Promise<AlarmSettings> {
  const response = await fetch(ALARM_SETTINGS_ENDPOINT, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch alarm settings: ${response.status}`)
  }
  return (await response.json()) as AlarmSettings
}

/**
 * Update the global alarm settings.
 *
 * @param settings - New settings to persist.
 * @returns Saved {@link AlarmSettings}.
 * @throws Error on network or server error (including 422 validation errors).
 */
export async function updateAlarmSettings(settings: AlarmSettings): Promise<AlarmSettings> {
  const response = await fetch(ALARM_SETTINGS_ENDPOINT, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  })
  if (!response.ok) {
    const body = await response.text()
    throw new Error(`Failed to update alarm settings: ${response.status} ${body}`)
  }
  return (await response.json()) as AlarmSettings
}

// ---------------------------------------------------------------------------
// Pending notifications
// ---------------------------------------------------------------------------

/**
 * Fetch all unacknowledged in-app alarm notifications.
 *
 * @returns List of {@link PendingNotification}, oldest first.
 * @throws Error on network or server error.
 */
export async function getPendingNotifications(): Promise<PendingNotification[]> {
  const response = await fetch(`${NOTIFICATIONS_ENDPOINT}/pending`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch notifications: ${response.status}`)
  }
  return (await response.json()) as PendingNotification[]
}

/**
 * Acknowledge (dismiss) a single pending notification.
 *
 * @param id - UUID of the notification to dismiss.
 * @throws Error on network or server error (including 404 if not found).
 */
export async function ackNotification(id: string): Promise<void> {
  const response = await fetch(`${NOTIFICATIONS_ENDPOINT}/${encodeURIComponent(id)}/ack`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!response.ok) {
    throw new Error(`Failed to acknowledge notification ${id}: ${response.status}`)
  }
}
