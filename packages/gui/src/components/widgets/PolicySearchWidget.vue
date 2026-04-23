<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { FileText, ExternalLink, Copy, FileSearch } from 'lucide-vue-next'
import PdfViewerWidget from './PdfViewerWidget.vue'

const { t } = useI18n()

interface PolicySearchResult {
  title: string
  page: number
  section: string
  snippet: string
  chunk_id: string
  source_path?: string
  score?: number
}

interface PolicySearchWidgetData {
  query: string
  results: PolicySearchResult[]
  totalCount: number
}

const props = defineProps<{
  data: Record<string, unknown>
}>()

const view = ref<'list' | 'pdf'>('list')
const selectedResult = ref<PolicySearchResult | null>(null)

const widgetData = computed<PolicySearchWidgetData>(() => ({
  query: (props.data.query as string) || '',
  results: Array.isArray(props.data.results) ? (props.data.results as PolicySearchResult[]) : [],
  totalCount: (props.data.totalCount as number) || 0,
}))

function getPdfUrl(result: PolicySearchResult): string {
  if (!result.source_path) return ''
  const filename = result.source_path.split('/').pop() || ''
  return `/files/pdfs/${encodeURIComponent(filename)}`
}

function openPdf(result: PolicySearchResult) {
  selectedResult.value = result
  view.value = 'pdf'
}

function closePdf() {
  view.value = 'list'
  selectedResult.value = null
}

function getPdfViewerData(result: PolicySearchResult) {
  const filename = result.source_path?.split('/').pop() || ''
  return {
    src: getPdfUrl(result),
    page: result.page,
    filename,
  }
}

async function copyCitation(result: PolicySearchResult) {
  const pageLabel = result.page ? `Page ${result.page}` : ''
  const sectionLabel = result.section ? ` | ${result.section}` : ''
  const citation = `[Source] ${result.title}${sectionLabel}${pageLabel ? ' | ' + pageLabel : ''}`
  try {
    await navigator.clipboard.writeText(citation)
  } catch {
    // Clipboard API may fail in non-HTTPS or if permission is denied
  }
}

function getCitationText(result: PolicySearchResult): string {
  const pageLabel = result.page ? `Page ${result.page}` : ''
  const sectionLabel = result.section ? ` | ${result.section}` : ''
  return `[Source] ${result.title}${sectionLabel}${pageLabel ? ' | ' + pageLabel : ''}`
}
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- PDF viewer mode -->
    <div v-if="view === 'pdf' && selectedResult" class="flex flex-col h-full">
      <div class="flex items-center gap-2 px-4 py-2 border-b border-gray-100">
        <button
          @click="closePdf"
          class="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 transition-colors"
        >
          <ExternalLink class="w-4 h-4 rotate-180" />
          {{ t('policySearch.back') }}
        </button>
        <span class="text-xs text-gray-400">|</span>
        <FileText class="w-4 h-4 text-gray-400" />
        <span class="text-sm font-medium text-gray-600 truncate">{{ selectedResult.title }}</span>
      </div>
      <div class="flex-1 overflow-hidden">
        <PdfViewerWidget :data="getPdfViewerData(selectedResult)" />
      </div>
    </div>

    <!-- List view -->
    <div v-else class="flex flex-col h-full overflow-hidden">
      <!-- Header -->
      <div class="px-4 py-3 border-b border-gray-100">
        <div class="flex items-center gap-2 mb-1">
          <FileSearch class="w-5 h-5 text-teal-600" />
          <h3 class="font-semibold text-gray-800">{{ t('widgets.policySearch') }}</h3>
          <span
            v-if="widgetData.totalCount > 0"
            class="ml-auto text-xs bg-teal-100 text-teal-600 px-2 py-0.5 rounded-full"
          >
            {{ widgetData.totalCount }} {{ t('policySearch.found') }}
          </span>
        </div>
        <p v-if="widgetData.query" class="text-sm text-gray-500 truncate">
          "{{ widgetData.query }}"
        </p>
      </div>

      <!-- Results list -->
      <div class="flex-1 overflow-y-auto">
        <div
          v-if="widgetData.results.length === 0"
          class="flex flex-col items-center justify-center py-12 text-gray-400"
        >
          <FileText class="w-10 h-10 mb-2 opacity-50" />
          <p class="text-sm">{{ t('policySearch.empty') }}</p>
        </div>

        <div v-else class="p-3 space-y-2">
          <div
            v-for="(result, i) in widgetData.results"
            :key="result.chunk_id || i"
            class="bg-white rounded-lg border border-gray-100 shadow-sm hover:shadow-md hover:border-teal-200 transition-all p-3"
          >
            <!-- Title row -->
            <div class="flex items-start gap-2 mb-2">
              <FileText class="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                  <p class="text-sm font-medium text-gray-800 truncate">{{ result.title }}</p>
                  <span class="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">
                    [{{ i + 1 }}]
                  </span>
                  <span v-if="result.page" class="text-xs text-gray-400">
                    Page {{ result.page }}
                  </span>
                  <span v-if="result.section" class="text-xs text-gray-400 truncate">
                    {{ result.section }}
                  </span>
                </div>
              </div>
            </div>

            <!-- Snippet -->
            <p class="text-xs text-gray-600 line-clamp-4 mb-2 pl-5">
              {{ result.snippet }}
            </p>

            <!-- Actions -->
            <div class="flex items-center gap-2 pl-5">
              <button
                @click="copyCitation(result)"
                class="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-teal-600 transition-colors"
                :title="getCitationText(result)"
              >
                <Copy class="w-3.5 h-3.5" />
                {{ t('policySearch.copy') }}
              </button>
              <button
                v-if="result.source_path"
                @click="openPdf(result)"
                class="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-teal-600 transition-colors"
              >
                <ExternalLink class="w-3.5 h-3.5" />
                {{ t('policySearch.open') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
