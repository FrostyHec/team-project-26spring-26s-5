<script setup lang="ts">
import { Globe, ExternalLink } from 'lucide-vue-next'

const props = defineProps<{
  data: Record<string, unknown>
}>()

const url = (props.data.url as string) || ''
const title = (props.data.title as string) || 'Web Preview'
</script>

<template>
  <div class="p-4 h-full flex flex-col">
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center gap-2">
        <Globe class="w-5 h-5 text-cyan-600" />
        <h3 class="font-semibold text-gray-800 truncate">{{ title }}</h3>
      </div>
      <a
        v-if="url"
        :href="url"
        target="_blank"
        class="text-gray-400 hover:text-cyan-600 transition-colors"
      >
        <ExternalLink class="w-4 h-4" />
      </a>
    </div>

    <div v-if="url" class="flex-1 rounded-lg overflow-hidden border border-gray-200 bg-white">
      <iframe
        :src="url"
        class="w-full h-full min-h-[300px]"
        sandbox="allow-scripts allow-same-origin"
      />
    </div>

    <div
      v-else
      class="flex-1 flex items-center justify-center bg-gray-50 rounded-lg border-2 border-dashed border-gray-200"
    >
      <div class="text-center text-gray-400">
        <Globe class="w-10 h-10 mx-auto mb-2 opacity-50" />
        <p class="text-sm">No URL provided</p>
      </div>
    </div>
  </div>
</template>
