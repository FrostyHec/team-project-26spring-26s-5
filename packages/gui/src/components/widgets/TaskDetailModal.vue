<script setup lang="ts">
/**
 * TaskDetailModal — overlay showing full task details with inline editing.
 *
 * Opened when the user clicks a task card (edit mode) or the "New Task"
 * button (create mode).  All fields are editable.  Save persists via
 * PATCH (edit) or POST (create) and emits "saved" so the parent refreshes.
 */
import { ref, computed, watch } from 'vue'
import {
  DateType,
  type DeadlineInfo,
  type DateTypeValue,
  updateDeadline,
  createDeadline,
} from '@/api/agent'
import { PRIORITY_COLORS } from './deadlineConstants'

const props = defineProps<{ task: DeadlineInfo | null }>()
const emit = defineEmits<{
  close: []
  saved: []
  'toggle-complete': [id: string, completed: boolean]
}>()

const isCreateMode = computed(() => props.task === null)

// Editable form state — initialised from the task prop (or empty for create).
const title = ref('')
const course = ref('')
const dueDate = ref('')
const priority = ref('medium')
const description = ref('')
const dateType = ref<DateTypeValue>(DateType.MOMENT_DAY)
const startDate = ref('')
const saving = ref(false)
const errorMsg = ref('')

/** Populate form from the task prop (or reset for create mode). */
function resetForm() {
  if (props.task) {
    title.value = props.task.title
    course.value = props.task.course
    dueDate.value = props.task.due_date
    priority.value = props.task.priority
    description.value = props.task.description
    dateType.value = props.task.date_type
    startDate.value = props.task.start_date
  } else {
    title.value = ''
    course.value = ''
    dueDate.value = ''
    priority.value = 'medium'
    description.value = ''
    dateType.value = DateType.MOMENT_DAY
    startDate.value = ''
  }
}
resetForm()
watch(() => props.task, resetForm)

const DATE_TYPE_OPTIONS: ReadonlyArray<{ value: DateTypeValue; label: string }> = [
  { value: DateType.NO_DATE, label: 'No Date' },
  { value: DateType.MOMENT_DAY, label: 'Date (day)' },
  { value: DateType.MOMENT_HM, label: 'Date (hour:min)' },
  { value: DateType.PERIOD_DAY, label: 'Period (day)' },
  { value: DateType.PERIOD_HM, label: 'Period (hour:min)' },
] as const

const PRIORITY_OPTIONS = ['high', 'medium', 'low'] as const

const isPeriod = (dt: DateTypeValue) => dt === DateType.PERIOD_DAY || dt === DateType.PERIOD_HM

async function handleSave() {
  saving.value = true
  errorMsg.value = ''
  // Date range validation: start_date must be on or before due_date
  if (isPeriod(dateType.value) && startDate.value && dueDate.value) {
    if (startDate.value > dueDate.value) {
      errorMsg.value = 'Start date must be on or before due date'
      saving.value = false
      return
    }
  }
  try {
    if (isCreateMode.value) {
      await createDeadline({
        title: title.value,
        course: course.value,
        due_date: dueDate.value,
        priority: priority.value,
        description: description.value,
        date_type: dateType.value,
        start_date: startDate.value,
      })
    } else {
      await updateDeadline(props.task!.id, {
        title: title.value,
        course: course.value,
        due_date: dueDate.value,
        priority: priority.value,
        description: description.value,
        date_type: dateType.value,
        start_date: startDate.value,
      })
    }
    emit('saved')
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : 'Failed to save'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
    @click.self="emit('close')"
  >
    <div class="mx-4 w-full max-w-md rounded-lg bg-white shadow-xl">
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-gray-200 px-4 py-3">
        <div class="flex items-center gap-2">
          <span
            v-if="task"
            class="h-2.5 w-2.5 rounded-full"
            :class="PRIORITY_COLORS[task.priority] || 'bg-gray-300'"
          />
          <h3 class="text-sm font-semibold text-gray-700">
            {{ isCreateMode ? 'New Task' : 'Task Detail' }}
          </h3>
        </div>
        <div class="flex items-center gap-2">
          <label v-if="task" class="flex cursor-pointer items-center gap-1 text-xs text-gray-500">
            <input
              type="checkbox"
              :checked="task.completed"
              class="h-3.5 w-3.5 rounded border-gray-300"
              @change="emit('toggle-complete', task.id, !task.completed)"
            />
            Done
          </label>
          <button class="text-gray-400 hover:text-gray-600" @click="emit('close')">✕</button>
        </div>
      </div>

      <!-- Form -->
      <div class="max-h-[60vh] space-y-3 overflow-y-auto px-4 py-3">
        <!-- Title -->
        <div>
          <label class="mb-1 block text-[10px] font-medium text-gray-500">Title</label>
          <input
            v-model="title"
            class="w-full rounded border border-gray-200 px-2 py-1.5 text-sm focus:border-blue-400 focus:outline-none"
          />
        </div>

        <!-- Course -->
        <div>
          <label class="mb-1 block text-[10px] font-medium text-gray-500">Course</label>
          <input
            v-model="course"
            class="w-full rounded border border-gray-200 px-2 py-1.5 text-sm focus:border-blue-400 focus:outline-none"
            placeholder="e.g. CS302"
          />
        </div>

        <!-- Priority + Date Type row -->
        <div class="flex gap-3">
          <div class="flex-1">
            <label class="mb-1 block text-[10px] font-medium text-gray-500">Priority</label>
            <select
              v-model="priority"
              class="w-full rounded border border-gray-200 px-2 py-1.5 text-sm focus:border-blue-400 focus:outline-none"
            >
              <option v-for="p in PRIORITY_OPTIONS" :key="p" :value="p">
                {{ p.charAt(0).toUpperCase() + p.slice(1) }}
              </option>
            </select>
          </div>
          <div class="flex-1">
            <label class="mb-1 block text-[10px] font-medium text-gray-500">Date Type</label>
            <select
              v-model="dateType"
              class="w-full rounded border border-gray-200 px-2 py-1.5 text-sm focus:border-blue-400 focus:outline-none"
            >
              <option v-for="opt in DATE_TYPE_OPTIONS" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>
        </div>

        <!-- Start Date (period only, shown ABOVE due date for natural order) -->
        <div v-if="isPeriod(dateType)">
          <label class="mb-1 block text-[10px] font-medium text-gray-500">Start Date</label>
          <input
            v-model="startDate"
            :type="dateType === DateType.PERIOD_HM ? 'datetime-local' : 'date'"
            class="w-full rounded border border-gray-200 px-2 py-1.5 text-sm focus:border-blue-400 focus:outline-none"
          />
        </div>

        <!-- Due Date -->
        <div v-if="dateType !== DateType.NO_DATE">
          <label class="mb-1 block text-[10px] font-medium text-gray-500">Due Date</label>
          <input
            v-model="dueDate"
            :type="
              dateType === DateType.MOMENT_HM || dateType === DateType.PERIOD_HM
                ? 'datetime-local'
                : 'date'
            "
            class="w-full rounded border border-gray-200 px-2 py-1.5 text-sm focus:border-blue-400 focus:outline-none"
          />
        </div>

        <!-- Description -->
        <div>
          <label class="mb-1 block text-[10px] font-medium text-gray-500">Description</label>
          <textarea
            v-model="description"
            rows="3"
            class="w-full rounded border border-gray-200 px-2 py-1.5 text-sm focus:border-blue-400 focus:outline-none"
            placeholder="Optional notes..."
          />
        </div>

        <!-- Metadata (read-only, edit mode only) -->
        <div v-if="task" class="flex gap-4 text-[10px] text-gray-400">
          <span>ID: {{ task.id.slice(0, 8) }}…</span>
          <span>Source: {{ task.source }}</span>
        </div>

        <!-- Error -->
        <div v-if="errorMsg" class="text-xs text-red-500">{{ errorMsg }}</div>
      </div>

      <!-- Footer -->
      <div class="flex justify-end gap-2 border-t border-gray-200 px-4 py-3">
        <button
          class="rounded px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-100"
          @click="emit('close')"
        >
          Cancel
        </button>
        <button
          class="rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          :disabled="saving || !title.trim()"
          @click="handleSave"
        >
          {{ saving ? 'Saving...' : isCreateMode ? 'Create' : 'Save' }}
        </button>
      </div>
    </div>
  </div>
</template>
