<script setup lang="ts">
/**
 * SyncPanel — modal overlay for reviewing sync preview results.
 *
 * Shows two columns:
 * - Left: new tasks to be added
 * - Right: duplicate tasks (with annotation of existing_id)
 *
 * Users can drag items from duplicates → new tasks to force-keep them.
 * Confirm commits the final "new tasks" list; Cancel discards all.
 */
import { ref, computed } from 'vue'
import {
  syncPreview,
  syncCommit,
  fetchDeadlines,
  type DeadlineInfo,
  type DuplicateEntry,
} from '@/api/agent'
import { ID_PREVIEW_LENGTH } from './deadlineConstants'

const emit = defineEmits<{
  close: []
  'sync-complete': []
}>()

const newTasks = ref<DeadlineInfo[]>([])
const duplicateTasks = ref<DuplicateEntry[]>([])
const loading = ref(false)
const committing = ref(false)
const errorMsg = ref('')
const previewLoaded = ref(false)

/**
 * Start the sync preview by fetching all deadlines and sending them
 * through the preview endpoint.  In a real flow the candidate list
 * would come from an agent sync operation; here we demonstrate the
 * preview/commit flow.
 */
async function loadPreview() {
  loading.value = true
  errorMsg.value = ''
  try {
    // The sync preview is typically triggered by the agent after
    // collecting tasks.  For the manual panel we just preview the
    // current store (useful for future drag-in scenarios).
    const all = await fetchDeadlines()
    const result = await syncPreview(all)
    newTasks.value = result.new_tasks
    duplicateTasks.value = result.duplicate_tasks
    previewLoaded.value = true
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : 'Sync preview failed'
  } finally {
    loading.value = false
  }
}

/** Move a duplicate entry into the new tasks list. */
function moveToNew(index: number) {
  const entry = duplicateTasks.value[index]
  if (!entry) return
  duplicateTasks.value.splice(index, 1)
  newTasks.value.push(entry.candidate)
}

/** Confirm and commit the new tasks. */
async function confirmSync() {
  committing.value = true
  errorMsg.value = ''
  try {
    await syncCommit(newTasks.value)
    emit('sync-complete')
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : 'Sync commit failed'
  } finally {
    committing.value = false
  }
}

// Load preview on mount-like trigger
loadPreview()
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
    <div class="mx-4 max-h-[80vh] w-full max-w-2xl overflow-hidden rounded-lg bg-white shadow-xl">
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-gray-200 px-4 py-3">
        <h3 class="text-sm font-semibold text-gray-700">Sync Preview</h3>
        <button class="text-gray-400 hover:text-gray-600" @click="emit('close')">✕</button>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="flex items-center justify-center py-12">
        <span class="text-sm text-gray-400">Loading preview...</span>
      </div>

      <!-- Error -->
      <div v-else-if="errorMsg" class="px-4 py-6 text-center text-sm text-red-500">
        {{ errorMsg }}
      </div>

      <!-- Preview content -->
      <div v-else-if="previewLoaded" class="flex max-h-[60vh] overflow-hidden">
        <!-- New tasks -->
        <div class="flex-1 overflow-y-auto border-r border-gray-200 p-3">
          <div class="mb-2 text-xs font-semibold text-green-600">
            New Tasks ({{ newTasks.length }})
          </div>
          <div v-if="newTasks.length === 0" class="text-xs text-gray-400">No new tasks to add.</div>
          <div class="space-y-2">
            <div
              v-for="(task, i) in newTasks"
              :key="task.id || i"
              class="rounded border border-green-200 bg-green-50/50 p-2 text-xs"
            >
              <div class="font-medium text-gray-700">{{ task.title }}</div>
              <div v-if="task.due_date" class="text-gray-500">Due: {{ task.due_date }}</div>
            </div>
          </div>
        </div>

        <!-- Duplicate tasks -->
        <div class="flex-1 overflow-y-auto p-3">
          <div class="mb-2 text-xs font-semibold text-amber-600">
            Duplicates ({{ duplicateTasks.length }})
          </div>
          <div v-if="duplicateTasks.length === 0" class="text-xs text-gray-400">
            No duplicates found.
          </div>
          <div class="space-y-2">
            <div
              v-for="(entry, i) in duplicateTasks"
              :key="entry.existing_id"
              class="rounded border border-amber-200 bg-amber-50/50 p-2 text-xs"
            >
              <div class="flex items-start justify-between">
                <div>
                  <div class="font-medium text-gray-700">{{ entry.candidate.title }}</div>
                  <div class="text-gray-400">
                    Duplicate of #{{ entry.existing_id.slice(0, ID_PREVIEW_LENGTH) }}
                  </div>
                </div>
                <button
                  class="rounded bg-blue-100 px-2 py-0.5 text-[10px] font-medium text-blue-600 hover:bg-blue-200"
                  title="Move to new tasks"
                  @click="moveToNew(i)"
                >
                  Keep →
                </button>
              </div>
            </div>
          </div>
        </div>
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
          :disabled="committing || newTasks.length === 0"
          @click="confirmSync"
        >
          {{ committing ? 'Syncing...' : `Confirm (${newTasks.length})` }}
        </button>
      </div>
    </div>
  </div>
</template>
