<script setup lang="ts">
/**
 * WeekView — Panel B: 7-row week layout with horizontal scrolling.
 *
 * Shows Mon–Sun as rows. Each row has a day header on the left and
 * tasks flowing horizontally to the right (queue style).
 * Today's row is highlighted.
 */
import { ref, computed } from 'vue'
import type { DeadlineInfo } from '@/api/agent'
import {
  getWeekStart,
  getWeekDays,
  dateToStr,
  tasksForDate,
  todayDateStr,
  WEEKDAY_LABELS,
} from './deadlineUtils'
import TimelineCard from './TimelineCard.vue'

const props = defineProps<{ deadlines: DeadlineInfo[] }>()
const emit = defineEmits<{
  'toggle-complete': [id: string, completed: boolean]
  'open-detail': [task: DeadlineInfo]
}>()

const weekOffset = ref(0)

const weekStart = computed(() => {
  const base = getWeekStart(new Date())
  const d = new Date(base)
  d.setDate(d.getDate() + weekOffset.value * 7)
  return d
})

const weekDays = computed(() => getWeekDays(weekStart.value))
const today = computed(() => todayDateStr())

function tasksFor(day: Date): DeadlineInfo[] {
  return tasksForDate(props.deadlines, dateToStr(day))
}

function prevWeek() {
  weekOffset.value--
}
function nextWeek() {
  weekOffset.value++
}
function goToday() {
  weekOffset.value = 0
}

function formatDayHeader(d: Date): string {
  return `${d.getMonth() + 1}/${d.getDate()}`
}
</script>

<template>
  <div class="flex h-full flex-col">
    <!-- Week navigation -->
    <div class="flex items-center justify-between border-b border-gray-200 px-3 py-2">
      <button class="rounded px-2 py-1 text-xs text-gray-500 hover:bg-gray-100" @click="prevWeek">
        ← Prev
      </button>
      <button
        class="rounded px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50"
        @click="goToday"
      >
        Today
      </button>
      <button class="rounded px-2 py-1 text-xs text-gray-500 hover:bg-gray-100" @click="nextWeek">
        Next →
      </button>
    </div>

    <!-- Day rows -->
    <div class="flex-1 overflow-y-auto">
      <div
        v-for="(day, i) in weekDays"
        :key="i"
        class="flex border-b border-gray-100"
        :class="dateToStr(day) === today ? 'bg-blue-50/30' : ''"
      >
        <!-- Day header (fixed left column) -->
        <div
          class="flex w-20 flex-shrink-0 flex-col items-center justify-center border-r border-gray-200 py-2"
          :class="dateToStr(day) === today ? 'bg-blue-50 font-bold text-blue-700' : 'text-gray-500'"
        >
          <div class="text-[10px]">{{ WEEKDAY_LABELS[i] }}</div>
          <div class="text-xs font-medium">{{ formatDayHeader(day) }}</div>
        </div>

        <!-- Horizontal task queue -->
        <div class="flex min-h-[56px] flex-1 items-start gap-2 overflow-x-auto p-2">
          <div v-for="task in tasksFor(day)" :key="task.id" class="w-52 flex-shrink-0">
            <TimelineCard
              :task="task"
              @toggle-complete="(id, c) => emit('toggle-complete', id, c)"
              @click="emit('open-detail', task)"
            />
          </div>
          <div
            v-if="tasksFor(day).length === 0"
            class="flex items-center text-[10px] text-gray-300"
          >
            No tasks
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
