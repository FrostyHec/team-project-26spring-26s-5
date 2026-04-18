/**
 * Pinia store for the deadline alarm feature.
 *
 * Manages global alarm settings and the in-app pending notification queue.
 */

import { ref } from 'vue'
import { defineStore } from 'pinia'
import {
  getAlarmSettings,
  updateAlarmSettings,
  getPendingNotifications,
  ackNotification,
} from '@/api/alarm'
import type { AlarmSettings, PendingNotification } from '@/api/alarm'
import { ALARM_LEAD_TIMES, ALARM_CHANNELS, DEADLINE_PRIORITIES } from '@/stores/alarmConstants'

export type { AlarmSettings, PendingNotification }

export const useAlarmStore = defineStore('alarm', () => {
  // ---------- State ----------

  /** Current alarm configuration from the backend. */
  const settings = ref<AlarmSettings>({
    enabled: true,
    lead_times: [ALARM_LEAD_TIMES.DAY_1],
    channels: [ALARM_CHANNELS.IN_APP],
    enabled_priorities: [DEADLINE_PRIORITIES.HIGH, DEADLINE_PRIORITIES.MEDIUM],
  })

  /** Unacknowledged in-app notifications. */
  const pendingNotifications = ref<PendingNotification[]>([])

  /** Whether the alarm notification modal is visible. */
  const showModal = ref(false)

  /** True while loading settings from the backend. */
  const isLoading = ref(false)

  /** True while saving settings to the backend. */
  const isSaving = ref(false)

  /** Error from the last failed operation, or null. */
  const error = ref<string | null>(null)

  // ---------- Actions ----------

  /** Fetch current alarm settings from the backend. */
  async function fetchAlarmSettings(): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      settings.value = await getAlarmSettings()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load alarm settings'
    } finally {
      isLoading.value = false
    }
  }

  /** Save updated alarm settings to the backend.
   *
   * @param newSettings - Settings to persist.
   * @returns True on success, false on failure.
   */
  async function saveAlarmSettings(newSettings: AlarmSettings): Promise<boolean> {
    isSaving.value = true
    error.value = null
    try {
      settings.value = await updateAlarmSettings(newSettings)
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to save alarm settings'
      return false
    } finally {
      isSaving.value = false
    }
  }

  /** Poll the backend for pending notifications and show the modal if any. */
  async function fetchPendingNotifications(): Promise<void> {
    try {
      pendingNotifications.value = await getPendingNotifications()
      if (pendingNotifications.value.length > 0) {
        showModal.value = true
      }
    } catch {
      // Silently ignore polling errors to avoid spamming the user
    }
  }

  /** Acknowledge all pending notifications and close the modal. */
  async function ackAll(): Promise<void> {
    const ids = pendingNotifications.value.map((n) => n.id)
    await Promise.allSettled(ids.map((id) => ackNotification(id)))
    pendingNotifications.value = []
    showModal.value = false
  }

  /** Close the modal without acknowledging (user can re-open later). */
  function dismissModal(): void {
    showModal.value = false
  }

  return {
    settings,
    pendingNotifications,
    showModal,
    isLoading,
    isSaving,
    error,
    fetchAlarmSettings,
    saveAlarmSettings,
    fetchPendingNotifications,
    ackAll,
    dismissModal,
  }
})
