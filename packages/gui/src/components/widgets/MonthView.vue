<script setup lang="ts">
/**
 * MonthView — Panel C: monthly calendar grid.
 *
 * Shows a 6-row × 7-column grid (Mon–Sun). Each cell displays the
 * date and task-count dots.  Clicking a cell expands it to show the
 * full task list for that day.
 */
import { ref, computed } from 'vue'
import type { DeadlineInfo } from '@/api/agent'
import { PRIORITY_COLORS, MAX_DOTS_PER_CELL } from './deadlineConstants'
import {
  getMonthGrid,
  dateToStr,
  tasksForDate,
  todayDateStr,
  WEEKDAY_LABELS,
  MONTH_LABELS,
} from './deadlineUtils'
import TimelineCard from './TimelineCard.vue'

const props = defineProps<{ deadlines: DeadlineInfo[] }>()
const emit = defineEmits<{
  'toggle-complete': [id: string, completed: boolean]
  'open-detail': [task: DeadlineInfo]
}>()

const now = new Date()
const viewYear = ref(now.getFullYear())
const viewMonth = ref(now.getMonth()) // 0-based

const expandedDate = ref<string | null>(null)
const today = computed(() => todayDateStr())

const grid = computed(() => getMonthGrid(viewYear.value, viewMonth.value))

const monthLabel = computed(() => `${MONTH_LABELS[viewMonth.value]} ${viewYear.value}`)

function tasksFor(dateStr: string): DeadlineInfo[] {
  return tasksForDate(props.deadlines, dateStr)
}

function prevMonth() {
  if (viewMonth.value === 0) {
    viewMonth.value = 11
    viewYear.value--
  } else {
    viewMonth.value--
  }
  expandedDate.value = null
}

function nextMonth() {
  if (viewMonth.value === 11) {
    viewMonth.value = 0
    viewYear.value++
  } else {
    viewMonth.value++
  }
  expandedDate.value = null
}

function goToday() {
  const n = new Date()
  viewYear.value = n.getFullYear()
  viewMonth.value = n.getMonth()
  expandedDate.value = null
}

function toggleExpand(dateStr: string) {
  expandedDate.value = expandedDate.value === dateStr ? null : dateStr
}

function isCurrentMonth(d: Date): boolean {
  return d.getMonth() === viewMonth.value
}
</script>

<template>
  <div class="flex h-full flex-col">
    <!-- Month navigation -->
    <div class="flex items-center justify-between border-b border-gray-200 px-3 py-2">
      <button class="rounded px-2 py-1 text-xs text-gray-500 hover:bg-gray-100" @click="prevMonth">
        ← Prev
      </button>
      <div class="flex items-center gap-2">
        <span class="text-sm font-semibold text-gray-700">{{ monthLabel }}</span>
        <button class="rounded px-2 py-0.5 text-xs text-blue-600 hover:bg-blue-50" @click="goToday">
          Today
        </button>
      </div>
      <button class="rounded px-2 py-1 text-xs text-gray-500 hover:bg-gray-100" @click="nextMonth">
        Next →
      </button>
    </div>

    <!-- Weekday headers -->
    <div class="grid grid-cols-7 border-b border-gray-200">
      <div
        v-for="label in WEEKDAY_LABELS"
        :key="label"
        class="border-r border-gray-100 py-1 text-center text-[10px] font-medium text-gray-500 last:border-r-0"
      >
        {{ label }}
      </div>
    </div>

    <!-- Calendar grid -->
    <div class="flex-1 overflow-y-auto">
      <div class="grid grid-cols-7">
        <div
          v-for="(day, i) in grid"
          :key="i"
          class="min-h-[52px] cursor-pointer border-b border-r border-gray-100 p-1 transition-colors hover:bg-gray-50"
          :class="{
            'bg-blue-50': dateToStr(day) === today,
            'text-gray-300': !isCurrentMonth(day),
            'text-gray-700': isCurrentMonth(day),
          }"
          @click="toggleExpand(dateToStr(day))"
        >
          <div class="text-xs font-medium">{{ day.getDate() }}</div>
          <!-- Task dots -->
          <div class="mt-0.5 flex flex-wrap gap-0.5">
            <span
              v-for="task in tasksFor(dateToStr(day)).slice(0, MAX_DOTS_PER_CELL)"
              :key="task.id"
              class="h-1.5 w-1.5 rounded-full"
              :class="PRIORITY_COLORS[task.priority] || 'bg-gray-300'"
            />
            <span
              v-if="tasksFor(dateToStr(day)).length > MAX_DOTS_PER_CELL"
              class="text-[8px] leading-none text-gray-400"
            >
              +{{ tasksFor(dateToStr(day)).length - MAX_DOTS_PER_CELL }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Expanded day detail -->
    <div
      v-if="expandedDate"
      class="max-h-[40%] flex-shrink-0 overflow-y-auto border-t border-gray-300 bg-white p-3"
    >
      <div class="mb-2 flex items-center justify-between">
        <span class="text-sm font-semibold text-gray-700">{{ expandedDate }}</span>
        <button class="text-xs text-gray-400 hover:text-gray-600" @click="expandedDate = null">
          Close
        </button>
      </div>
      <div v-if="tasksFor(expandedDate).length === 0" class="text-xs text-gray-400">
        No tasks on this day.
      </div>
      <div class="space-y-2">
        <TimelineCard
          v-for="task in tasksFor(expandedDate)"
          :key="task.id"
          :task="task"
          @toggle-complete="(id, c) => emit('toggle-complete', id, c)"
          @click="emit('open-detail', task)"
        />
      </div>
    </div>
  </div>
</template>
