<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Calendar, Clock, AlertCircle, Loader2, RefreshCw } from 'lucide-vue-next'
import { fetchDeadlines, type DeadlineInfo } from '@/api/agent'

const { t } = useI18n()

// Accept (and ignore) the generic :data prop passed by WorkspacePanel so
// Vue does not fall back to setting a raw DOM attribute on the root element.
defineProps<{ data?: unknown }>()

const deadlines = ref<DeadlineInfo[]>([])
const isLoading = ref(false)
const errorMsg = ref('')

async function loadDeadlines(): Promise<void> {
  isLoading.value = true
  errorMsg.value = ''
  try {
    deadlines.value = await fetchDeadlines()
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : t('errors.loadDeadlines')
  } finally {
    isLoading.value = false
  }
}

function priorityDot(priority?: string): string {
  switch (priority) {
    case 'high':
      return 'bg-red-500'
    case 'medium':
      return 'bg-yellow-500'
    default:
      return 'bg-green-500'
  }
}

onMounted(loadDeadlines)
</script>

<template>
  <div class="p-4">
    <div class="flex items-center gap-2 mb-4">
      <Calendar class="w-5 h-5 text-blue-600" />
      <h3 class="font-semibold text-slate-800">{{ t('widgets.calendarUpcoming') }}</h3>
      <button
        class="ml-auto p-1 rounded hover:bg-slate-200 text-slate-400 hover:text-slate-600 transition-colors"
        :title="t('workspace.refresh')"
        @click="loadDeadlines"
      >
        <RefreshCw class="w-4 h-4" />
      </button>
    </div>

    <!-- Loading state -->
    <div v-if="isLoading" class="flex items-center justify-center py-8 text-slate-400">
      <Loader2 class="w-6 h-6 animate-spin" />
      <span class="ml-2 text-sm">{{ t('widgets.calendarLoading') }}</span>
    </div>

    <!-- Error state -->
    <div v-else-if="errorMsg" class="text-center py-8">
      <AlertCircle class="w-8 h-8 mx-auto mb-2 text-red-400" />
      <p class="text-sm text-red-500">{{ errorMsg }}</p>
      <button class="mt-2 text-xs text-blue-500 hover:underline" @click="loadDeadlines">
        {{ t('common.retry') }}
      </button>
    </div>

    <!-- Empty state -->
    <div v-else-if="deadlines.length === 0" class="text-center py-8 text-slate-400">
      <Calendar class="w-10 h-10 mx-auto mb-2 opacity-50" />
      <p class="text-sm">{{ t('widgets.calendarEmpty') }}</p>
    </div>

    <!-- Deadline list -->
    <div v-else class="space-y-3">
      <div
        v-for="(dl, i) in deadlines"
        :key="dl.id"
        class="flex items-start gap-3 p-3 bg-white rounded-lg border border-slate-100 shadow-sm hover:shadow-md transition-shadow"
      >
        <!-- Priority indicator -->
        <div class="flex flex-col items-center pt-1">
          <span class="w-2.5 h-2.5 rounded-full" :class="priorityDot(dl.priority)" />
          <div v-if="i < deadlines.length - 1" class="w-px h-6 bg-slate-200 mt-1" />
        </div>

        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium text-slate-800 truncate">{{ dl.title }}</p>
          <div class="flex items-center gap-3 mt-1 text-xs text-slate-500">
            <span v-if="dl.due_date" class="flex items-center gap-1">
              <Calendar class="w-3 h-3" />
              {{ dl.due_date }}
            </span>
            <span v-if="dl.description" class="flex items-center gap-1">
              <Clock class="w-3 h-3" />
              {{ dl.description }}
            </span>
          </div>
          <span
            v-if="dl.course"
            class="inline-block mt-1 px-2 py-0.5 bg-blue-50 text-blue-600 text-xs rounded-full"
          >
            {{ dl.course }}
          </span>
        </div>

        <AlertCircle
          v-if="dl.priority === 'high'"
          class="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5"
        />
      </div>
    </div>
  </div>
</template>
