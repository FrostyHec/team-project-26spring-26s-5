<!-- Deadline alarm settings section for the Settings panel.

Allows the user to enable/disable DDL reminders and configure:
  - Advance notice windows (lead_times)
  - Notification channels (channels)
  - Priority levels (enabled_priorities)

Validation: when enabled=true, all three lists must be non-empty.
The Save button is disabled when validation fails.
-->
<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Bell, CheckCircle2 } from 'lucide-vue-next'
import { useAlarmStore } from '@/stores/alarm'
import type { AlarmSettings } from '@/stores/alarm'
import {
  ALARM_LEAD_TIMES,
  ALARM_CHANNELS,
  DEADLINE_PRIORITIES,
  type AlarmLeadTime,
  type AlarmChannel,
  type DeadlinePriority,
} from '@/stores/alarmConstants'

const { t } = useI18n()
const alarmStore = useAlarmStore()

// Local editable copy of settings
const local = ref<AlarmSettings>({
  enabled: true,
  lead_times: [ALARM_LEAD_TIMES.DAY_1],
  channels: [ALARM_CHANNELS.IN_APP],
  enabled_priorities: [DEADLINE_PRIORITIES.HIGH, DEADLINE_PRIORITIES.MEDIUM],
})

// Success flash
const savedFlash = ref(false)
let flashTimer: ReturnType<typeof setTimeout> | null = null

onMounted(async () => {
  await alarmStore.fetchAlarmSettings()
  local.value = {
    ...alarmStore.settings,
    lead_times: [...alarmStore.settings.lead_times],
    channels: [...alarmStore.settings.channels],
    enabled_priorities: [...alarmStore.settings.enabled_priorities],
  }
})

onUnmounted(() => {
  if (flashTimer) clearTimeout(flashTimer)
})

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

const validationError = computed<string | null>(() => {
  if (!local.value.enabled) return null
  if (
    local.value.lead_times.length === 0 ||
    local.value.channels.length === 0 ||
    local.value.enabled_priorities.length === 0
  ) {
    return t('deadlineAlarm.validationError')
  }
  return null
})

const canSave = computed(() => !validationError.value)

// ---------------------------------------------------------------------------
// Toggle helpers
// ---------------------------------------------------------------------------

function toggleLeadTime(value: AlarmLeadTime): void {
  const idx = local.value.lead_times.indexOf(value)
  if (idx >= 0) {
    local.value.lead_times.splice(idx, 1)
  } else {
    local.value.lead_times.push(value)
  }
}

function toggleChannel(value: AlarmChannel): void {
  const idx = local.value.channels.indexOf(value)
  if (idx >= 0) {
    local.value.channels.splice(idx, 1)
  } else {
    local.value.channels.push(value)
  }
}

function togglePriority(value: DeadlinePriority): void {
  const idx = local.value.enabled_priorities.indexOf(value)
  if (idx >= 0) {
    local.value.enabled_priorities.splice(idx, 1)
  } else {
    local.value.enabled_priorities.push(value)
  }
}

// ---------------------------------------------------------------------------
// Save
// ---------------------------------------------------------------------------

async function save(): Promise<void> {
  if (!canSave.value) return
  const ok = await alarmStore.saveAlarmSettings({ ...local.value })
  if (ok) {
    if (flashTimer) clearTimeout(flashTimer)
    savedFlash.value = true
    flashTimer = setTimeout(() => {
      savedFlash.value = false
    }, 3000)
  }
}

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

const LEAD_TIME_OPTIONS: { value: AlarmLeadTime; labelKey: string; hourOnly: boolean }[] = [
  { value: ALARM_LEAD_TIMES.HOUR_1, labelKey: 'deadlineAlarm.hour1', hourOnly: true },
  { value: ALARM_LEAD_TIMES.HOUR_3, labelKey: 'deadlineAlarm.hour3', hourOnly: true },
  { value: ALARM_LEAD_TIMES.HOUR_6, labelKey: 'deadlineAlarm.hour6', hourOnly: true },
  { value: ALARM_LEAD_TIMES.HOUR_12, labelKey: 'deadlineAlarm.hour12', hourOnly: true },
  { value: ALARM_LEAD_TIMES.DAY_1, labelKey: 'deadlineAlarm.day1', hourOnly: false },
  { value: ALARM_LEAD_TIMES.DAY_3, labelKey: 'deadlineAlarm.day3', hourOnly: false },
  { value: ALARM_LEAD_TIMES.WEEK_1, labelKey: 'deadlineAlarm.week1', hourOnly: false },
]

const CHANNEL_OPTIONS: { value: AlarmChannel; labelKey: string; noteKey: string | null }[] = [
  { value: ALARM_CHANNELS.IN_APP, labelKey: 'deadlineAlarm.inApp', noteKey: null },
  {
    value: ALARM_CHANNELS.EMAIL,
    labelKey: 'deadlineAlarm.emailChannel',
    noteKey: 'deadlineAlarm.emailRequiresConfig',
  },
]

const PRIORITY_OPTIONS = [
  { value: DEADLINE_PRIORITIES.HIGH, labelKey: 'deadlineAlarm.priorityHigh' },
  { value: DEADLINE_PRIORITIES.MEDIUM, labelKey: 'deadlineAlarm.priorityMedium' },
  { value: DEADLINE_PRIORITIES.LOW, labelKey: 'deadlineAlarm.priorityLow' },
]
</script>

<template>
  <div class="space-y-6">
    <!-- Title -->
    <div>
      <div class="flex items-center gap-2 mb-1">
        <Bell class="w-5 h-5 text-gray-500" />
        <h2 class="text-base font-semibold text-gray-900">{{ t('deadlineAlarm.title') }}</h2>
      </div>
      <p class="text-sm text-gray-500">{{ t('deadlineAlarm.description') }}</p>
    </div>

    <!-- Master toggle -->
    <div class="flex items-center justify-between p-3 rounded-lg border border-gray-200">
      <span class="text-sm font-medium text-gray-700">{{ t('deadlineAlarm.enabled') }}</span>
      <button
        type="button"
        role="switch"
        :aria-checked="local.enabled"
        class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        :class="local.enabled ? 'bg-blue-600' : 'bg-gray-200'"
        @click="local.enabled = !local.enabled"
      >
        <span
          class="inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform"
          :class="local.enabled ? 'translate-x-6' : 'translate-x-1'"
        />
      </button>
    </div>

    <!-- Sub-settings (grayed when disabled) -->
    <div :class="{ 'opacity-40 pointer-events-none': !local.enabled }" class="space-y-5">
      <!-- Lead times -->
      <fieldset>
        <legend class="text-sm font-medium text-gray-700 mb-2">
          {{ t('deadlineAlarm.leadTimes') }}
        </legend>
        <div class="space-y-1.5">
          <label
            v-for="opt in LEAD_TIME_OPTIONS"
            :key="opt.value"
            class="flex items-center gap-2.5 cursor-pointer"
          >
            <input
              type="checkbox"
              class="rounded text-blue-600 focus:ring-blue-500"
              :checked="local.lead_times.includes(opt.value)"
              @change="toggleLeadTime(opt.value)"
            />
            <span class="text-sm text-gray-700">{{ t(opt.labelKey) }}</span>
            <span v-if="opt.hourOnly" class="text-xs text-gray-400">
              {{ t('deadlineAlarm.hourOnlyHint') }}
            </span>
          </label>
        </div>
      </fieldset>

      <!-- Channels -->
      <fieldset>
        <legend class="text-sm font-medium text-gray-700 mb-2">
          {{ t('deadlineAlarm.channels') }}
        </legend>
        <div class="space-y-1.5">
          <label
            v-for="opt in CHANNEL_OPTIONS"
            :key="opt.value"
            class="flex items-center gap-2.5 cursor-pointer"
          >
            <input
              type="checkbox"
              class="rounded text-blue-600 focus:ring-blue-500"
              :checked="local.channels.includes(opt.value)"
              @change="toggleChannel(opt.value)"
            />
            <span class="text-sm text-gray-700">{{ t(opt.labelKey) }}</span>
            <span v-if="opt.noteKey" class="text-xs text-gray-400">{{ t(opt.noteKey) }}</span>
          </label>
        </div>
      </fieldset>

      <!-- Priority levels -->
      <fieldset>
        <legend class="text-sm font-medium text-gray-700 mb-2">
          {{ t('deadlineAlarm.enabledPriorities') }}
        </legend>
        <div class="space-y-1.5">
          <label
            v-for="opt in PRIORITY_OPTIONS"
            :key="opt.value"
            class="flex items-center gap-2.5 cursor-pointer"
          >
            <input
              type="checkbox"
              class="rounded text-blue-600 focus:ring-blue-500"
              :checked="local.enabled_priorities.includes(opt.value)"
              @change="togglePriority(opt.value)"
            />
            <span class="text-sm text-gray-700">{{ t(opt.labelKey) }}</span>
          </label>
        </div>
      </fieldset>
    </div>

    <!-- Validation error -->
    <p v-if="validationError" class="text-sm text-red-600">{{ validationError }}</p>

    <!-- Error from store -->
    <p v-if="alarmStore.error" class="text-sm text-red-600">{{ alarmStore.error }}</p>

    <!-- Success flash -->
    <div v-if="savedFlash" class="flex items-center gap-1.5 text-sm text-green-600">
      <CheckCircle2 class="w-4 h-4" />
      <span>{{ t('deadlineAlarm.settingsSaved') }}</span>
    </div>

    <!-- Save button -->
    <div>
      <button
        type="button"
        class="px-4 py-2 text-sm font-medium rounded-lg transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        :class="
          canSave && !alarmStore.isSaving
            ? 'bg-blue-600 text-white hover:bg-blue-700'
            : 'bg-gray-100 text-gray-400 cursor-not-allowed'
        "
        :disabled="!canSave || alarmStore.isSaving"
        @click="save"
      >
        {{ alarmStore.isSaving ? t('common.saving') : t('common.save') }}
      </button>
    </div>
  </div>
</template>
