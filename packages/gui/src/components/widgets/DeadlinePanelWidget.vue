<script setup lang="ts">
/**
 * DeadlinePanelWidget — main container for the deadline panel.
 *
 * Provides a tab bar (Tasks / Week / Month), a hide-completed toggle,
 * a refresh button, and renders the active sub-view.  All deadline data
 * is fetched from the REST API and managed locally.
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { fetchDeadlines, toggleDeadlineComplete, type DeadlineInfo } from '@/api/agent'
import { useChatStore } from '@/stores/chat'
import {
  PANEL_VIEWS,
  PANEL_VIEW_TABS,
  PRIORITY_FILTER_OPTIONS,
  type PanelView,
} from './deadlineConstants'
import TaskListView from './TaskListView.vue'
import WeekView from './WeekView.vue'
import MonthView from './MonthView.vue'
import SyncPanel from './SyncPanel.vue'
import TaskDetailModal from './TaskDetailModal.vue'

defineProps<{ data?: Record<string, unknown> }>()

const { t } = useI18n()
const chatStore = useChatStore()
const deadlines = ref<DeadlineInfo[]>([])
const activeView = ref<PanelView>(PANEL_VIEWS.TASKS)
const hideCompleted = ref(false)
const filterCourse = ref<string>('')
const filterPriority = ref<string>('')
const loading = ref(false)
const errorMsg = ref('')
const showSyncPanel = ref(false)
const detailTask = ref<DeadlineInfo | null>(null)
const showCreateModal = ref(false)

// Increments every 60 s so that computed properties that read it
// (e.g. filteredDeadlines) are invalidated and overdue statuses recompute.
const tickNow = ref(Date.now())
let _tickTimer: ReturnType<typeof setInterval> | null = null

const uniqueCourses = computed<string[]>(() => {
  const courses = new Set(deadlines.value.map((d) => d.course).filter(Boolean))
  return [...courses].sort()
})

// Reset course filter if the selected course disappears after a data refresh.
watch(uniqueCourses, (courses) => {
  if (filterCourse.value && !courses.includes(filterCourse.value)) {
    filterCourse.value = ''
  }
})

const filteredDeadlines = computed(() => {
  // Depend on tickNow so Vue recomputes statuses every minute even if data is unchanged.
  tickNow.value
  let result = deadlines.value
  if (hideCompleted.value) result = result.filter((d) => !d.completed)
  if (filterCourse.value) result = result.filter((d) => d.course === filterCourse.value)
  if (filterPriority.value) result = result.filter((d) => d.priority === filterPriority.value)
  return result
})

async function loadDeadlines() {
  loading.value = true
  errorMsg.value = ''
  try {
    deadlines.value = await fetchDeadlines()
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : 'Failed to load deadlines'
  } finally {
    loading.value = false
  }
}

async function handleToggleComplete(id: string, completed: boolean) {
  try {
    await toggleDeadlineComplete(id, completed)
    // Optimistic update
    const idx = deadlines.value.findIndex((d) => d.id === id)
    if (idx !== -1) {
      const existing = deadlines.value[idx]
      deadlines.value[idx] = Object.assign({}, existing, { completed })
    }
  } catch {
    // Revert on error — just re-fetch
    await loadDeadlines()
  }
}

function handleSyncComplete() {
  showSyncPanel.value = false
  loadDeadlines()
}

function openDetail(task: DeadlineInfo) {
  detailTask.value = task
}

function handleDetailSaved() {
  detailTask.value = null
  showCreateModal.value = false
  loadDeadlines()
}

function handleCreateSaved() {
  showCreateModal.value = false
  loadDeadlines()
}

onMounted(() => {
  loadDeadlines()
  _tickTimer = setInterval(() => {
    tickNow.value = Date.now()
  }, 60_000)
})

onUnmounted(() => {
  if (_tickTimer !== null) {
    clearInterval(_tickTimer)
    _tickTimer = null
  }
})

// Auto-refresh when a deadline-mutating tool completes in the chat.
watch(() => chatStore.deadlineVersion, loadDeadlines)
</script>

<template>
  <div class="flex h-full flex-col bg-gray-50">
    <!-- Toolbar -->
    <div class="flex flex-shrink-0 items-center gap-2 border-b border-gray-200 bg-white px-3 py-2">
      <!-- View tabs -->
      <div class="flex gap-1">
        <button
          v-for="tab in PANEL_VIEW_TABS"
          :key="tab.key"
          class="rounded-md px-3 py-1.5 text-xs font-medium transition-colors"
          :class="
            activeView === tab.key
              ? 'bg-blue-100 text-blue-700'
              : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700'
          "
          @click="activeView = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Course filter -->
      <select
        v-model="filterCourse"
        aria-label="Course filter"
        data-testid="filter-course"
        class="rounded-md border border-gray-200 bg-white px-2 py-1 text-xs text-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-300"
      >
        <option value="">{{ t('deadlines.filterAllCourses') }}</option>
        <option v-for="c in uniqueCourses" :key="c" :value="c">{{ c }}</option>
      </select>

      <!-- Priority filter -->
      <select
        v-model="filterPriority"
        aria-label="Priority filter"
        data-testid="filter-priority"
        class="rounded-md border border-gray-200 bg-white px-2 py-1 text-xs text-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-300"
      >
        <option v-for="opt in PRIORITY_FILTER_OPTIONS" :key="opt.value" :value="opt.value">
          {{ t(opt.labelKey) }}
        </option>
      </select>

      <!-- New Task button -->
      <button
        class="rounded-md px-2 py-1.5 text-xs font-medium text-blue-600 hover:bg-blue-50"
        title="Create new task"
        @click="showCreateModal = true"
      >
        + New
      </button>

      <div class="flex-1" />

      <!-- Hide completed toggle -->
      <label class="flex cursor-pointer items-center gap-1.5 text-xs text-gray-500">
        <input
          v-model="hideCompleted"
          type="checkbox"
          class="h-3.5 w-3.5 rounded border-gray-300"
        />
        Hide done
      </label>

      <!-- Refresh -->
      <button
        class="rounded p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
        title="Refresh"
        @click="loadDeadlines"
      >
        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
          />
        </svg>
      </button>
    </div>

    <!-- Loading / Error states -->
    <div v-if="loading && deadlines.length === 0" class="flex flex-1 items-center justify-center">
      <div class="text-sm text-gray-400">Loading deadlines...</div>
    </div>

    <div v-else-if="errorMsg" class="flex flex-1 items-center justify-center">
      <div class="text-sm text-red-500">{{ errorMsg }}</div>
    </div>

    <!-- Active view -->
    <div v-else class="flex-1 overflow-y-auto">
      <!-- Filter no-match state (filter active but nothing passes) -->
      <div
        v-if="filteredDeadlines.length === 0 && deadlines.length > 0"
        class="py-12 text-center text-sm text-gray-400"
        data-testid="filter-no-match"
      >
        {{ t('deadlines.filterNoMatch') }}
      </div>

      <template v-else>
        <TaskListView
          v-if="activeView === PANEL_VIEWS.TASKS"
          :deadlines="filteredDeadlines"
          @toggle-complete="handleToggleComplete"
          @open-detail="openDetail"
        />
        <WeekView
          v-else-if="activeView === PANEL_VIEWS.WEEK"
          :deadlines="filteredDeadlines"
          @toggle-complete="handleToggleComplete"
          @open-detail="openDetail"
        />
        <MonthView
          v-else-if="activeView === PANEL_VIEWS.MONTH"
          :deadlines="filteredDeadlines"
          @toggle-complete="handleToggleComplete"
          @open-detail="openDetail"
        />
      </template>
    </div>

    <!-- Task detail modal (edit mode) -->
    <TaskDetailModal
      v-if="detailTask"
      :task="detailTask"
      @close="detailTask = null"
      @saved="handleDetailSaved"
      @toggle-complete="handleToggleComplete"
    />

    <!-- Task create modal (create mode) -->
    <TaskDetailModal
      v-if="showCreateModal"
      :task="null"
      @close="showCreateModal = false"
      @saved="handleCreateSaved"
    />

    <!-- Sync panel modal -->
    <SyncPanel
      v-if="showSyncPanel"
      @close="showSyncPanel = false"
      @sync-complete="handleSyncComplete"
    />
  </div>
</template>
