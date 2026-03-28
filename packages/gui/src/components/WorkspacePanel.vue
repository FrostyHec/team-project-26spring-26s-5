<script setup lang="ts">
import { computed } from 'vue'
import { X } from 'lucide-vue-next'
import { useChatStore, WIDGET_TYPES } from '@/stores/chat'
import CalendarWidget from './widgets/CalendarWidget.vue'
import DocumentWidget from './widgets/DocumentWidget.vue'
import CourseCardsWidget from './widgets/CourseCardsWidget.vue'
import SourcesWidget from './widgets/SourcesWidget.vue'
import WebPreviewWidget from './widgets/WebPreviewWidget.vue'
import EmptyWidget from './widgets/EmptyWidget.vue'

const chatStore = useChatStore()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const widgetComponent = computed(() => {
  switch (chatStore.activeWidget.type) {
    case WIDGET_TYPES.CALENDAR:
      return CalendarWidget
    case WIDGET_TYPES.DOCUMENT:
      return DocumentWidget
    case WIDGET_TYPES.COURSE_CARDS:
      return CourseCardsWidget
    case WIDGET_TYPES.SOURCES:
      return SourcesWidget
    case WIDGET_TYPES.WEB_PREVIEW:
      return WebPreviewWidget
    default:
      return EmptyWidget
  }
})

const widgetTitle = computed(() => {
  switch (chatStore.activeWidget.type) {
    case WIDGET_TYPES.CALENDAR:
      return 'Calendar'
    case WIDGET_TYPES.DOCUMENT:
      return 'Document'
    case WIDGET_TYPES.COURSE_CARDS:
      return 'Courses'
    case WIDGET_TYPES.SOURCES:
      return 'Sources'
    case WIDGET_TYPES.WEB_PREVIEW:
      return 'Web Preview'
    default:
      return 'Workspace'
  }
})
</script>

<template>
  <aside class="flex flex-col h-full w-full bg-white relative z-10">
    <!-- Header -->
    <div
      class="flex items-center justify-between px-4 py-3.5 border-b border-slate-200 bg-white shadow-sm z-20"
    >
      <h3 class="text-[15px] font-semibold text-slate-800 tracking-tight">{{ widgetTitle }}</h3>
      <button
        class="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors"
        @click="emit('close')"
      >
        <X class="w-4 h-4" />
      </button>
    </div>

    <!-- Widget content -->
    <div class="flex-1 overflow-y-auto bg-slate-50">
      <component :is="widgetComponent" :data="chatStore.activeWidget.data" />
    </div>
  </aside>
</template>
