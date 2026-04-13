<script setup lang="ts">
/**
 * TaskListView — Panel A: vertical timeline with NOW indicator.
 *
 * Layout:
 * - Overdue tasks (red tint)
 * - NOW indicator line (today's date)
 * - Future tasks grouped by date with date separators
 * - Backlog section at bottom (NO_DATE tasks)
 */
import { computed } from 'vue'
import { DateType, type DeadlineInfo } from '@/api/agent'
import { TASK_STATUS } from './deadlineConstants'
import { computeTaskStatus, groupByDate, todayDateStr, toDateOnly } from './deadlineUtils'
import TimelineCard from './TimelineCard.vue'

const props = defineProps<{ deadlines: DeadlineInfo[] }>()
const emit = defineEmits<{
  'toggle-complete': [id: string, completed: boolean]
  'open-detail': [task: DeadlineInfo]
}>()

const today = computed(() => todayDateStr())

/** Tasks with a date that are overdue. */
const overdueTasks = computed(() =>
  props.deadlines.filter((t) => computeTaskStatus(t) === TASK_STATUS.OVERDUE),
)

/** Tasks due today or in the future (not overdue, not no-date, not completed-but-visible). */
const futureTasks = computed(() =>
  props.deadlines
    .filter((t) => {
      const s = computeTaskStatus(t)
      return s === TASK_STATUS.TODAY || s === TASK_STATUS.UPCOMING || s === TASK_STATUS.COMPLETED
    })
    .filter((t) => t.date_type !== DateType.NO_DATE && t.due_date),
)

/** Group future tasks by date. */
const futureGrouped = computed(() => groupByDate(futureTasks.value))

/** Tasks with no date (backlog). */
const backlogTasks = computed(() =>
  props.deadlines.filter((t) => t.date_type === DateType.NO_DATE || !t.due_date),
)

function formatDateSeparator(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00')
  const month = d.getMonth() + 1
  const day = d.getDate()
  if (dateStr === today.value) return `Today (${month}/${day})`
  // Check tomorrow
  const tom = new Date()
  tom.setDate(tom.getDate() + 1)
  const tomStr = tom.toISOString().slice(0, 10)
  if (dateStr === tomStr) return `Tomorrow (${month}/${day})`
  return `${month}/${day}`
}
</script>

<template>
  <div class="relative px-4 py-4">
    <!-- Vertical timeline line -->
    <div class="absolute bottom-0 left-[23px] top-4 w-0.5 bg-gray-200" />

    <!-- Empty state -->
    <div
      v-if="overdueTasks.length === 0 && futureTasks.length === 0 && backlogTasks.length === 0"
      class="py-12 text-center text-sm text-gray-400"
    >
      No deadlines yet. Chat with the agent to sync your tasks.
    </div>

    <div class="relative space-y-3">
      <!-- Overdue section -->
      <template v-if="overdueTasks.length > 0">
        <div class="ml-7 mb-1 text-xs font-semibold text-red-500">Overdue</div>
        <div v-for="task in overdueTasks" :key="task.id" class="relative ml-7">
          <!-- Timeline dot -->
          <div
            class="absolute -left-[22px] top-4 h-3 w-3 rounded-full border-2 border-white bg-red-500 shadow-sm"
          />
          <TimelineCard
            :task="task"
            @toggle-complete="(id, c) => emit('toggle-complete', id, c)"
            @click="emit('open-detail', task)"
          />
        </div>
      </template>

      <!-- NOW indicator -->
      <div class="relative my-4 flex items-center">
        <div class="absolute left-[3px] h-3 w-3 animate-pulse rounded-full bg-red-500" />
        <div class="ml-7 h-px flex-1 border-t border-dashed border-red-400" />
        <span
          class="ml-2 rounded border border-red-200 bg-red-100 px-2 py-0.5 text-xs font-bold text-red-700"
        >
          NOW
        </span>
      </div>

      <!-- Future tasks, grouped by date -->
      <template v-for="[dateKey, tasks] in futureGrouped" :key="dateKey">
        <!-- Date separator -->
        <div class="ml-7 flex items-center gap-2">
          <span class="rounded bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-500">
            {{ formatDateSeparator(dateKey) }}
          </span>
          <div class="h-px flex-1 bg-gray-200" />
        </div>

        <div v-for="task in tasks" :key="task.id" class="relative ml-7">
          <div
            class="absolute -left-[22px] top-4 h-3 w-3 rounded-full border-2 border-white shadow-sm"
            :class="toDateOnly(task.due_date) === today ? 'bg-blue-500' : 'bg-gray-400'"
          />
          <TimelineCard
            :task="task"
            @toggle-complete="(id, c) => emit('toggle-complete', id, c)"
            @click="emit('open-detail', task)"
          />
        </div>
      </template>
    </div>

    <!-- Backlog section -->
    <div v-if="backlogTasks.length > 0" class="mt-6 border-t-2 border-dashed border-gray-300 pt-4">
      <div class="mb-3 flex items-center gap-2 text-sm font-medium text-gray-500">
        📥 No Date / Backlog
      </div>
      <div class="space-y-2">
        <div
          v-for="task in backlogTasks"
          :key="task.id"
          class="flex items-center gap-2 rounded border border-gray-200 bg-white p-2.5 text-sm text-gray-600 transition-colors hover:bg-gray-50"
        >
          <input
            type="checkbox"
            :checked="task.completed"
            class="h-3.5 w-3.5 cursor-pointer rounded border-gray-300"
            @change="emit('toggle-complete', task.id, !task.completed)"
          />
          <div class="h-2 w-2 rounded-full bg-gray-300" />
          <span :class="task.completed ? 'text-gray-400 line-through' : ''">
            {{ task.title }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
