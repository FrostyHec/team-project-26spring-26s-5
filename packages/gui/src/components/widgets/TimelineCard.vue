<script setup lang="ts">
/**
 * TimelineCard — a single task card in the timeline view.
 *
 * Shows: checkbox, title, date info (type-specific), priority dot,
 * course badge.  Period tasks display a progress bar.
 */
import { computed } from 'vue'
import { DateType, type DeadlineInfo } from '@/api/agent'
import { TASK_STATUS, PRIORITY_COLORS } from './deadlineConstants'
import {
  computeTaskStatus,
  computePeriodProgress,
  formatDueDate,
  formatStartDate,
  isPeriodType,
} from './deadlineUtils'

const props = defineProps<{ task: DeadlineInfo }>()
const emit = defineEmits<{ 'toggle-complete': [id: string, completed: boolean] }>()

const status = computed(() => computeTaskStatus(props.task))
const progress = computed(() => computePeriodProgress(props.task))
const dueDateText = computed(() => formatDueDate(props.task))
const startDateText = computed(() => formatStartDate(props.task))
const isPeriod = computed(() => isPeriodType(props.task.date_type))

const statusBorder: Record<string, string> = {
  [TASK_STATUS.OVERDUE]: 'border-red-200 bg-red-50/40',
  [TASK_STATUS.TODAY]: 'border-blue-200 bg-blue-50/30',
  [TASK_STATUS.UPCOMING]: 'border-gray-200 bg-white',
  [TASK_STATUS.COMPLETED]: 'border-gray-200 bg-gray-50 opacity-60',
  [TASK_STATUS.NO_DATE]: 'border-gray-200 bg-white',
}
</script>

<template>
  <div
    class="relative cursor-pointer rounded-lg border p-3 shadow-sm transition-colors hover:shadow-md"
    :class="statusBorder[status] || 'border-gray-200 bg-white'"
  >
    <!-- Top row: checkbox + title + priority dot -->
    <div class="flex items-start gap-2">
      <input
        type="checkbox"
        :checked="task.completed"
        class="mt-0.5 h-4 w-4 flex-shrink-0 cursor-pointer rounded border-gray-300"
        @change="emit('toggle-complete', task.id, !task.completed)"
      />

      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-1.5">
          <span
            class="h-2 w-2 flex-shrink-0 rounded-full"
            :class="PRIORITY_COLORS[task.priority] || 'bg-gray-300'"
          />
          <h4
            class="truncate text-sm font-medium"
            :class="task.completed ? 'text-gray-400 line-through' : 'text-gray-800'"
          >
            {{ task.title }}
          </h4>
        </div>

        <!-- Date info -->
        <div class="mt-1 flex items-center gap-2 text-xs">
          <!-- Overdue indicator -->
          <span v-if="status === TASK_STATUS.OVERDUE" class="font-medium text-red-600">
            Overdue
          </span>

          <!-- Moment types -->
          <template v-if="task.date_type === DateType.MOMENT_HM">
            <span class="text-blue-600">⏰ {{ dueDateText }}</span>
          </template>
          <template v-else-if="task.date_type === DateType.MOMENT_DAY">
            <span class="text-gray-600">{{ dueDateText }}</span>
          </template>

          <!-- Period types -->
          <template v-else-if="isPeriod">
            <span class="text-emerald-600">{{ startDateText }} → {{ dueDateText }}</span>
          </template>
        </div>

        <!-- Period progress bar -->
        <div v-if="isPeriod && startDateText" class="mt-1.5 flex items-center gap-2">
          <span class="w-10 text-right text-[10px] text-gray-400">{{ startDateText }}</span>
          <div class="h-1.5 flex-1 rounded-full bg-gray-200">
            <div
              class="h-1.5 rounded-full bg-emerald-500 transition-all"
              :style="{ width: `${progress}%` }"
            />
          </div>
          <span class="w-10 text-[10px] text-gray-400">{{ dueDateText }}</span>
        </div>

        <!-- Course badge -->
        <div v-if="task.course" class="mt-1.5">
          <span class="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-500">
            {{ task.course }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
