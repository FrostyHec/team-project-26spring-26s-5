<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut, ExternalLink } from 'lucide-vue-next'

interface Props {
  data?: {
    src: string
    page: number
    filename: string
  }
}

const props = defineProps<Props>()

const currentPage = ref(props.data?.page || 1)
const scale = ref(1.0)
const MIN_SCALE = 0.5
const MAX_SCALE = 3.0
const SCALE_STEP = 0.3

/** Clamp page to valid range [1, totalPages]. */
const validPage = computed(() => Math.max(1, currentPage.value))

function getPdfUrl(): string {
  if (!props.data?.src) return ''
  return `${props.data.src}#page=${validPage.value}`
}

function prevPage() {
  if (currentPage.value > 1) currentPage.value--
}

function nextPage() {
  currentPage.value++
}

function zoomIn() {
  if (scale.value < MAX_SCALE) scale.value = parseFloat((scale.value + SCALE_STEP).toFixed(1))
}

function zoomOut() {
  if (scale.value > MIN_SCALE) scale.value = parseFloat((scale.value - SCALE_STEP).toFixed(1))
}

function openInNewTab() {
  if (!props.data?.src) return
  window.open(props.data.src, '_blank', 'noopener,noreferrer')
}

/** Clamp currentPage to >= 1 on manual input to prevent invalid URLs. */
function clampPage() {
  if (currentPage.value < 1 || !Number.isInteger(currentPage.value)) {
    currentPage.value = Math.max(1, Math.round(currentPage.value))
  }
}

// Watch for page changes to reload iframe
watch(currentPage, () => {
  iframeKey.value++
})

watch(
  () => props.data,
  (newData) => {
    if (newData?.page) currentPage.value = newData.page || 1
  },
  { deep: true },
)

const iframeKey = ref(0)
</script>

<template>
  <div class="flex flex-col h-full bg-gray-100">
    <!-- Toolbar -->
    <div class="flex items-center justify-between px-3 py-2 bg-white border-b border-gray-200">
      <div class="flex items-center gap-2 min-w-0">
        <ExternalLink class="w-4 h-4 text-gray-400 flex-shrink-0" />
        <span class="text-sm font-medium text-gray-600 truncate">
          {{ props.data?.filename || 'PDF Viewer' }}
        </span>
      </div>
      <div class="flex items-center gap-1">
        <button
          @click="prevPage"
          :disabled="currentPage <= 1"
          class="p-1.5 rounded hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
          title="Previous page"
        >
          <ChevronLeft class="w-4 h-4 text-gray-600" />
        </button>
        <input
          v-model.number="currentPage"
          type="number"
          min="1"
          class="w-12 text-xs text-center border border-gray-200 rounded px-1 py-0.5"
          title="Page number"
          @input="clampPage"
        />
        <button @click="nextPage" class="p-1.5 rounded hover:bg-gray-100" title="Next page">
          <ChevronRight class="w-4 h-4 text-gray-600" />
        </button>
        <div class="w-px h-4 bg-gray-200 mx-1" />
        <button
          @click="zoomOut"
          :disabled="scale <= MIN_SCALE"
          class="p-1.5 rounded hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
          title="Zoom out"
        >
          <ZoomOut class="w-4 h-4 text-gray-600" />
        </button>
        <span class="text-xs text-gray-500 min-w-[40px] text-center">
          {{ Math.round(scale * 100) }}%
        </span>
        <button
          @click="zoomIn"
          :disabled="scale >= MAX_SCALE"
          class="p-1.5 rounded hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
          title="Zoom in"
        >
          <ZoomIn class="w-4 h-4 text-gray-600" />
        </button>
        <div class="w-px h-4 bg-gray-200 mx-1" />
        <button
          @click="openInNewTab"
          class="p-1.5 rounded hover:bg-gray-100"
          title="Open in new tab"
        >
          <ExternalLink class="w-4 h-4 text-gray-600" />
        </button>
      </div>
    </div>

    <!-- PDF iframe -->
    <div class="flex-1 overflow-auto bg-gray-200">
      <iframe
        v-if="props.data?.src"
        :key="iframeKey"
        :src="getPdfUrl()"
        class="w-full h-full border-0"
        :style="{ transform: `scale(${scale})`, transformOrigin: 'top left' }"
        title="PDF viewer"
      />
      <div v-else class="flex items-center justify-center h-full text-gray-400 text-sm">
        No PDF selected
      </div>
    </div>
  </div>
</template>
