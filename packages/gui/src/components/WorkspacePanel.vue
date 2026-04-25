<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { X } from 'lucide-vue-next'
import { useChatStore } from '@/stores/chat'
import { WIDGET_COMPONENTS, WIDGET_TITLE_I18N_KEYS, SELECTABLE_WIDGETS } from './widgets/index'
import type { WidgetType } from '@/stores/chatConstants'
import EmptyWidget from './widgets/EmptyWidget.vue'
import MenuDropdown from './common/MenuDropdown.vue'

const { t } = useI18n()
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
  const key = WIDGET_TITLE_I18N_KEYS[wt]
  return key ? t(key) : t('workspace.title')
})

function selectWidget(type: WidgetType): void {
  chatStore.setWidget(type)
}

function handleWidgetSelection(type: WidgetType, closeDropdown: () => void): void {
  selectWidget(type)
  closeDropdown()
}
</script>

<template>
  <aside class="flex flex-col h-full w-full bg-white relative z-10">
    <!-- Header -->
    <div
      class="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-white flex-shrink-0"
    >
      <!-- Widget selector dropdown -->
      <MenuDropdown :label="widgetTitle" class="relative" button-class="px-0 py-0">
        <template #default="{ closeDropdown }">
          <button
            v-for="w in SELECTABLE_WIDGETS"
            :key="w.type"
            class="w-full text-left px-3 py-2 text-sm transition-colors"
            :class="
              chatStore.activeWidget.type === w.type
                ? 'bg-blue-50 text-blue-600 font-medium'
                : 'text-gray-700 hover:bg-gray-50'
            "
            @click="handleWidgetSelection(w.type, closeDropdown)"
          >
            {{ t(w.titleKey) }}
          </button>
        </template>
      </MenuDropdown>

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
