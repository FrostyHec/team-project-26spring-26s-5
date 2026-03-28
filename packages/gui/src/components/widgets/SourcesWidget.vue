<script setup lang="ts">
import { computed } from 'vue'
import { Link2, ExternalLink, FileText } from 'lucide-vue-next'

interface SourceItem {
  title: string
  url?: string
  snippet?: string
  type?: string
}

const props = defineProps<{
  data: Record<string, unknown>
}>()

const sources = computed<SourceItem[]>(() =>
  Array.isArray(props.data.sources) ? (props.data.sources as SourceItem[]) : [],
)
</script>

<template>
  <div class="p-4">
    <div class="flex items-center gap-2 mb-4">
      <Link2 class="w-5 h-5 text-indigo-600" />
      <h3 class="font-semibold text-gray-800">Sources</h3>
      <span
        v-if="sources.length"
        class="ml-auto text-xs bg-indigo-100 text-indigo-600 px-2 py-0.5 rounded-full"
      >
        {{ sources.length }} found
      </span>
    </div>

    <div v-if="sources.length === 0" class="text-center py-8 text-gray-400">
      <Link2 class="w-10 h-10 mx-auto mb-2 opacity-50" />
      <p class="text-sm">No sources available</p>
    </div>

    <div v-else class="space-y-2">
      <a
        v-for="(src, i) in sources"
        :key="i"
        :href="src.url || '#'"
        target="_blank"
        class="block p-3 bg-white rounded-lg border border-gray-100 shadow-sm hover:shadow-md hover:border-indigo-200 transition-all group"
      >
        <div class="flex items-start gap-2">
          <FileText class="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-gray-800 truncate group-hover:text-indigo-600">
              {{ src.title }}
            </p>
            <p v-if="src.snippet" class="text-xs text-gray-500 mt-1 line-clamp-2">
              {{ src.snippet }}
            </p>
            <div class="flex items-center gap-2 mt-1">
              <span v-if="src.type" class="text-xs text-gray-400 bg-gray-50 px-1.5 py-0.5 rounded">
                {{ src.type }}
              </span>
            </div>
          </div>
          <ExternalLink
            class="w-3.5 h-3.5 text-gray-300 group-hover:text-indigo-400 flex-shrink-0"
          />
        </div>
      </a>
    </div>
  </div>
</template>
