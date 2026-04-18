/**
 * Composable that polls the backend every 30 seconds for pending alarm notifications.
 *
 * Usage::
 *
 *   const poller = useNotificationPoller()
 *   onMounted(() => poller.start())
 *   onUnmounted(() => poller.stop())
 */

import { useAlarmStore } from '@/stores/alarm'

const POLL_INTERVAL_MS = 30_000

export function useNotificationPoller() {
  const alarmStore = useAlarmStore()
  let intervalId: ReturnType<typeof setInterval> | null = null

  /** Start polling — runs an immediate check, then repeats every 30 s. */
  function start(): void {
    if (intervalId !== null) return // Already running
    void alarmStore.fetchPendingNotifications()
    intervalId = setInterval(() => {
      void alarmStore.fetchPendingNotifications()
    }, POLL_INTERVAL_MS)
  }

  /** Stop polling. */
  function stop(): void {
    if (intervalId !== null) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  return { start, stop }
}
