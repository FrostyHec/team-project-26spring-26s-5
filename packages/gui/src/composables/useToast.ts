/**
 * Lightweight toast composable backed by the email store's toast queue.
 *
 * Usage:
 *   const { toast } = useToast()
 *   toast('Done', 'success')
 */

import { useEmailStore } from '@/stores/email'

export function useToast() {
  const emailStore = useEmailStore()

  function toast(message: string, type: 'info' | 'success' | 'error' = 'info', duration = 3000) {
    emailStore.showToast(message, type, duration)
  }

  return { toast }
}
