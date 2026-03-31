<script setup lang="ts">
import { computed } from 'vue'
import { X } from 'lucide-vue-next'
import { useChatStore } from '@/stores/chat'
import { WIDGET_COMPONENTS, WIDGET_TITLES } from './widgets/index'
import type { WidgetType } from '@/stores/chatConstants'
import EmptyWidget from './widgets/EmptyWidget.vue'

const chatStore = useChatStore()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const widgetComponent = computed(() => {
  const wt = chatStore.activeWidget.type as WidgetType
  return WIDGET_COMPONENTS[wt] ?? EmptyWidget
})

const widgetTitle = computed(() => {
  const wt = chatStore.activeWidget.type as WidgetType
  return WIDGET_TITLES[wt] ?? 'Workspace'
})
</script>

<template>
  <aside class="flex flex-col h-full w-full bg-white relative z-10">
    <!-- Header -->
    <div
      class="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-white flex-shrink-0"
    >
      <h3 class="text-sm font-semibold text-gray-800">{{ widgetTitle }}</h3>
      <button
        class="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
        @click="emit('close')"
      >
        <X class="w-4 h-4" />
      </button>
    </div>

    <!-- Widget content -->
    <div class="flex-1 overflow-y-auto bg-gray-50">
      <component :is="widgetComponent" :data="chatStore.activeWidget.data" />
    </div>
  </aside>
</template>
