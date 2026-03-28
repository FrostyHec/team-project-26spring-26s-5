<script setup lang="ts">
import { FileText, ExternalLink } from 'lucide-vue-next'

const props = defineProps<{
  data: Record<string, unknown>
}>()

const title = (props.data.title as string) || 'Document'
const content = (props.data.content as string) || ''
const docType = (props.data.doc_type as string) || 'text'
const url = props.data.url as string | undefined
const pages = (props.data.pages as number) || 1
const currentPage = (props.data.current_page as number) || 1

const highlights: string[] = Array.isArray(props.data.highlights)
  ? (props.data.highlights as string[])
  : []
</script>

<template>
  <div class="p-4">
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center gap-2">
        <FileText class="w-5 h-5 text-purple-600" />
        <h3 class="font-semibold text-gray-800 truncate">{{ title }}</h3>
      </div>
      <div class="flex items-center gap-2">
        <span v-if="pages > 1" class="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">
          {{ currentPage }} / {{ pages }}
        </span>
        <span class="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded uppercase">
          {{ docType }}
        </span>
      </div>
    </div>

    <!-- Highlighted quotes -->
    <div v-if="highlights.length > 0" class="space-y-2 mb-4">
      <div
        v-for="(h, i) in highlights"
        :key="i"
        class="p-3 bg-purple-50 border-l-3 border-purple-400 rounded-r-lg text-sm text-gray-700"
      >
        <mark class="bg-yellow-200 px-0.5 rounded">{{ h }}</mark>
      </div>
    </div>

    <!-- Content preview -->
    <div
      v-if="content"
      class="prose prose-sm max-w-none text-gray-700 bg-gray-50 rounded-lg p-4 max-h-64 overflow-y-auto"
    >
      <p class="whitespace-pre-wrap">{{ content }}</p>
    </div>

    <!-- Document placeholder (PDF-like) -->
    <div
      v-else
      class="flex flex-col items-center justify-center py-12 bg-gray-50 rounded-lg border-2 border-dashed border-gray-200"
    >
      <FileText class="w-12 h-12 text-gray-300 mb-2" />
      <p class="text-sm text-gray-400">Document Preview</p>
    </div>

    <a
      v-if="url"
      :href="url"
      target="_blank"
      class="mt-3 inline-flex items-center gap-1 text-sm text-purple-600 hover:text-purple-800"
    >
      View Full Document <ExternalLink class="w-3.5 h-3.5" />
    </a>
  </div>
</template>
