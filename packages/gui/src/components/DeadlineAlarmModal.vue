<!-- Modal shown when there are unacknowledged deadline alarm notifications.

Displayed over the app when ``alarmStore.showModal`` is true.
The user can dismiss all notifications with the "Dismiss" button,
which calls ``alarmStore.ackAll()``.
-->
<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Bell } from 'lucide-vue-next'
import { useAlarmStore } from '@/stores/alarm'

const { t } = useI18n()
const alarmStore = useAlarmStore()

const count = computed(() => alarmStore.pendingNotifications.length)

// The backend aggregates all tasks into one notification with a pre-composed message.
// Show the most recent notification's message directly; fall back to a generic string.
const summaryMessage = computed<string>(() => {
  const messages = alarmStore.pendingNotifications.map((n) => n.message)
  return messages.join(' · ')
})

// Collect all detail strings across all notifications
const allDetails = computed<string[]>(() => {
  const seen = new Set<string>()
  const result: string[] = []
  for (const n of alarmStore.pendingNotifications) {
    for (const d of n.details) {
      if (!seen.has(d)) {
        seen.add(d)
        result.push(d)
      }
    }
  }
  return result
})
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="alarmStore.showModal && count > 0"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
        role="dialog"
        aria-modal="true"
        :aria-label="t('deadlineAlarm.notificationTitle')"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
          <!-- Header -->
          <div class="flex items-center gap-3 px-6 py-4 border-b border-gray-200 bg-amber-50">
            <Bell class="w-5 h-5 text-amber-500 flex-shrink-0" />
            <h2 class="text-base font-semibold text-gray-900">
              {{ t('deadlineAlarm.notificationTitle') }}
            </h2>
          </div>

          <!-- Body -->
          <div class="px-6 py-4 space-y-3 max-h-72 overflow-y-auto">
            <p class="text-sm font-medium text-gray-800">
              {{ summaryMessage }}
            </p>
            <ul v-if="allDetails.length > 0" class="space-y-1">
              <li
                v-for="(detail, idx) in allDetails"
                :key="idx"
                class="text-sm text-gray-600 flex items-start gap-2"
              >
                <span class="mt-1 text-amber-400 flex-shrink-0">•</span>
                <span>{{ detail }}</span>
              </li>
            </ul>
          </div>

          <!-- Footer -->
          <div class="px-6 py-4 border-t border-gray-100 flex justify-end">
            <button
              type="button"
              class="px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              @click="alarmStore.ackAll()"
            >
              {{ t('deadlineAlarm.dismiss') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
