<script setup lang="ts">
/**
 * FileManager — file management widget for a selected course.
 *
 * Props:
 *   courseId — ID of the course whose materials are displayed.
 *   courseName — Display name of the course (shown in header).
 *
 * Events:
 *   back — emitted when the user clicks the back button.
 */

import { ref, onMounted } from 'vue'
import {
  ArrowLeft,
  Upload,
  Download,
  Trash2,
  Pencil,
  FileText,
  CheckCircle,
  XCircle,
  Clock,
} from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import { useCourseStore } from '@/stores/courseStore'
import type { CourseMaterial } from '@/stores/courseStore'

const { t } = useI18n()
const store = useCourseStore()

const props = defineProps<{
  courseId: string
  courseName: string
}>()

const emit = defineEmits<{
  (e: 'back'): void
}>()

// ---------- File input ----------
const fileInput = ref<HTMLInputElement | null>(null)
const uploadDescription = ref('')
const uploadTags = ref('')
const editingMaterial = ref<CourseMaterial | null>(null)
const editDescription = ref('')
const editTags = ref('')

const ALLOWED_TYPES = ['.pdf', '.docx', '.pptx', '.xlsx', '.txt', '.md']
const MAX_SIZE = 10 * 1024 * 1024 // 10 MB

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

function fileTypeColor(fileType: string): string {
  switch (fileType) {
    case '.pdf':
      return '#ef4444'
    case '.docx':
      return '#3b82f6'
    case '.pptx':
      return '#f97316'
    case '.xlsx':
      return '#10b981'
    case '.txt':
    case '.md':
      return '#6b7280'
    default:
      return '#6b7280'
  }
}

// ---------- Lifecycle ----------
onMounted(() => {
  store.selectCourse(props.courseId)
})

// ---------- Upload ----------
const uploadError = ref('')
const uploadSuccess = ref(false)

function triggerFileInput() {
  fileInput.value?.click()
}

async function handleFileChange(event: Event) {
  uploadError.value = ''
  uploadSuccess.value = false
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  const ext = '.' + file.name.split('.').pop()?.toLowerCase()
  if (!ALLOWED_TYPES.includes(ext)) {
    uploadError.value = t('fileManager.fileTypeError')
    input.value = ''
    return
  }
  if (file.size > MAX_SIZE) {
    uploadError.value = t('fileManager.fileSizeError')
    input.value = ''
    return
  }

  const result = await store.addMaterial(file, uploadDescription.value, uploadTags.value)
  if (result) {
    uploadSuccess.value = true
    uploadDescription.value = ''
    uploadTags.value = ''
  }
  input.value = ''
}

// ---------- Download ----------
function handleDownload(material: CourseMaterial) {
  const url = store.getDownloadUrl(material.id)
  window.open(url, '_blank')
}

// ---------- Delete ----------
const confirmDeleteId = ref<string | null>(null)

function promptDelete(material: CourseMaterial) {
  confirmDeleteId.value = material.id
}

async function handleDelete() {
  if (!confirmDeleteId.value) return
  await store.removeMaterial(confirmDeleteId.value)
  confirmDeleteId.value = null
}

// ---------- Edit ----------
function openEditModal(material: CourseMaterial) {
  editingMaterial.value = material
  editDescription.value = material.description
  editTags.value = material.tags
}

async function saveEdit() {
  if (!editingMaterial.value) return
  await store.editMaterial(editingMaterial.value.id, {
    description: editDescription.value,
    tags: editTags.value,
  })
  editingMaterial.value = null
}
</script>

<template>
  <div class="flex flex-col h-full bg-gray-50">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 bg-white border-b border-gray-100">
      <div class="flex items-center gap-2 min-w-0">
        <button
          class="flex-shrink-0 p-1 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
          :title="t('common.close')"
          @click="emit('back')"
        >
          <ArrowLeft class="w-4 h-4" />
        </button>
        <div class="min-w-0">
          <p class="text-sm font-semibold text-gray-700 truncate">{{ courseName }}</p>
        </div>
      </div>

      <button
        class="flex-shrink-0 flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-blue-500 rounded-md hover:bg-blue-600 transition-colors"
        @click="triggerFileInput"
      >
        <Upload class="w-3.5 h-3.5" />
        {{ t('fileManager.upload') }}
        <input
          ref="fileInput"
          type="file"
          class="hidden"
          accept=".pdf,.docx,.pptx,.xlsx,.txt,.md"
          @change="handleFileChange"
        />
      </button>
    </div>

    <!-- Upload fields (inline) -->
    <div class="px-4 py-2 bg-blue-50 border-b border-blue-100 space-y-2">
      <div class="flex gap-2">
        <input
          v-model="uploadDescription"
          type="text"
          :placeholder="t('fileManager.descriptionPlaceholder')"
          class="flex-1 px-3 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-400"
        />
        <input
          v-model="uploadTags"
          type="text"
          :placeholder="t('fileManager.tagsPlaceholder')"
          class="w-36 px-3 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-400"
        />
      </div>
      <p v-if="uploadError" class="text-xs text-red-500 flex items-center gap-1">
        <XCircle class="w-3 h-3" />
        {{ uploadError }}
      </p>
      <p
        v-if="uploadSuccess && !store.error && !uploadError"
        class="text-xs text-green-600 flex items-center gap-1"
      >
        <CheckCircle class="w-3 h-3" />
        {{ t('fileManager.uploadSuccess') }}
      </p>
      <p v-if="store.isUploading" class="text-xs text-blue-500 flex items-center gap-1">
        <Clock class="w-3 h-3 animate-pulse" />
        {{ t('fileManager.uploading') }}
      </p>
    </div>

    <!-- Loading -->
    <div v-if="store.isLoadingMaterials" class="flex items-center justify-center flex-1 py-8">
      <span class="text-sm text-gray-400">{{ t('common.loading') }}</span>
    </div>

    <!-- Empty -->
    <div
      v-else-if="store.materials.length === 0"
      class="flex flex-col items-center justify-center flex-1 py-8 text-gray-400"
    >
      <FileText class="w-10 h-10 mb-2 opacity-40" />
      <p class="text-sm">{{ t('fileManager.noFiles') }}</p>
      <p class="text-xs mt-1">{{ t('fileManager.noFilesHint') }}</p>
    </div>

    <!-- File list -->
    <div v-else class="flex-1 overflow-y-auto">
      <div
        v-for="material in store.materials"
        :key="material.id"
        class="flex items-start gap-3 px-4 py-3 bg-white border-b border-gray-50 group hover:bg-gray-50 transition-colors"
      >
        <!-- File type icon -->
        <div
          class="flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center mt-0.5"
          :style="{
            backgroundColor: fileTypeColor(material.file_type) + '18',
            color: fileTypeColor(material.file_type),
          }"
        >
          <FileText class="w-4 h-4" />
        </div>

        <!-- File info -->
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium text-gray-800 truncate">{{ material.filename }}</p>
          <p class="text-xs text-gray-400">
            {{ formatBytes(material.file_size) }}
            <span class="mx-1">·</span>
            {{ formatDate(material.created_at) }}
            <span v-if="material.description" class="mx-1">·</span>
            <span v-if="material.description" class="italic">{{ material.description }}</span>
          </p>
          <p v-if="material.tags" class="text-xs text-gray-400 mt-0.5">
            <span
              v-for="tag in material.tags
                .split(',')
                .map((t) => t.trim())
                .filter(Boolean)"
              :key="tag"
              class="inline-block px-1.5 py-0.5 mr-1 rounded bg-gray-100 text-gray-500"
            >
              {{ tag }}
            </span>
          </p>
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            class="p-1.5 rounded-md text-gray-400 hover:text-blue-500 hover:bg-blue-50 transition-colors"
            :title="t('fileManager.edit')"
            @click="openEditModal(material)"
          >
            <Pencil class="w-3.5 h-3.5" />
          </button>
          <button
            class="p-1.5 rounded-md text-gray-400 hover:text-green-600 hover:bg-green-50 transition-colors"
            :title="t('fileManager.download')"
            @click="handleDownload(material)"
          >
            <Download class="w-3.5 h-3.5" />
          </button>
          <button
            class="p-1.5 rounded-md text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
            :title="t('fileManager.delete')"
            @click="promptDelete(material)"
          >
            <Trash2 class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>

    <!-- Edit Modal -->
    <div
      v-if="editingMaterial !== null"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
      @click.self="editingMaterial = null"
    >
      <div class="w-full max-w-sm bg-white rounded-xl shadow-xl overflow-hidden p-6">
        <h3 class="text-base font-semibold text-gray-800 mb-4">{{ t('fileManager.edit') }}</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">{{
              t('fileManager.description')
            }}</label>
            <input
              v-model="editDescription"
              type="text"
              :placeholder="t('fileManager.descriptionPlaceholder')"
              class="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">{{
              t('fileManager.tags')
            }}</label>
            <input
              v-model="editTags"
              type="text"
              :placeholder="t('fileManager.tagsPlaceholder')"
              class="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        <div class="mt-4 flex justify-end gap-2">
          <button
            class="px-4 py-2 text-sm text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
            @click="editingMaterial = null"
          >
            {{ t('common.close') }}
          </button>
          <button
            class="px-4 py-2 text-sm font-medium text-white bg-blue-500 rounded-lg hover:bg-blue-600 transition-colors"
            @click="saveEdit"
          >
            {{ t('common.save') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Confirm Modal -->
    <div
      v-if="confirmDeleteId !== null"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
      @click.self="confirmDeleteId = null"
    >
      <div class="w-full max-w-sm bg-white rounded-xl shadow-xl overflow-hidden p-6">
        <h3 class="text-base font-semibold text-gray-800 mb-2">{{ t('fileManager.delete') }}</h3>
        <p class="text-sm text-gray-500 mb-5">
          {{
            t('fileManager.confirmDeleteFile', {
              filename: store.materials.find((m) => m.id === confirmDeleteId)?.filename ?? '',
            })
          }}
        </p>
        <div class="flex justify-end gap-2">
          <button
            class="px-4 py-2 text-sm text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
            @click="confirmDeleteId = null"
          >
            {{ t('common.close') }}
          </button>
          <button
            class="px-4 py-2 text-sm font-medium text-white bg-red-500 rounded-lg hover:bg-red-600 transition-colors"
            @click="handleDelete"
          >
            {{ t('fileManager.delete') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
