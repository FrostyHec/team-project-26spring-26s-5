<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { X, ChevronDown } from 'lucide-vue-next'
import { useChatStore } from '@/stores/chat'
import { WIDGET_COMPONENTS, WIDGET_TITLES, SELECTABLE_WIDGETS } from './widgets/index'
import type { WidgetType } from '@/stores/chatConstants'
import EmptyWidget from './widgets/EmptyWidget.vue'

const chatStore = useChatStore()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const dropdownOpen = ref(false)
const dropdownRef = ref<HTMLElement | null>(null)

const widgetComponent = computed(() => {
  const wt = chatStore.activeWidget.type as WidgetType
  return WIDGET_COMPONENTS[wt] ?? EmptyWidget
})

const widgetTitle = computed(() => {
  const wt = chatStore.activeWidget.type as WidgetType
  return WIDGET_TITLES[wt] ?? 'Workspace'
})

function selectWidget(type: WidgetType): void {
  chatStore.setWidget(type)
  dropdownOpen.value = false
}

function toggleDropdown(): void {
  dropdownOpen.value = !dropdownOpen.value
}

function onClickOutside(event: MouseEvent): void {
  const target = event.target
  if (!(target instanceof Node)) return
  if (dropdownRef.value && !dropdownRef.value.contains(target)) {
    dropdownOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', onClickOutside, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onClickOutside, true)
})
</script>

<template>
  <aside class="flex flex-col h-full w-full bg-white relative z-10">
    <!-- Header -->
    <div
      class="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-white flex-shrink-0"
    >
      <!-- Widget selector dropdown -->
      <div ref="dropdownRef" class="relative">
        <button
          class="flex items-center gap-1 text-sm font-semibold text-gray-800 hover:text-blue-600 transition-colors"
          @click="toggleDropdown"
        >
          {{ widgetTitle }}
          <ChevronDown
            class="w-4 h-4 transition-transform"
            :class="{ 'rotate-180': dropdownOpen }"
          />
        </button>

        <!-- Dropdown menu -->
        <div
          v-show="dropdownOpen"
          class="absolute left-0 top-full mt-1 w-44 bg-white border border-gray-200 rounded-lg shadow-lg py-1 z-20"
        >
          <button
            v-for="w in SELECTABLE_WIDGETS"
            :key="w.type"
            class="w-full text-left px-3 py-2 text-sm transition-colors"
            :class="
              chatStore.activeWidget.type === w.type
                ? 'bg-blue-50 text-blue-600 font-medium'
                : 'text-gray-700 hover:bg-gray-50'
            "
            @click="selectWidget(w.type)"
          >
            {{ w.title }}
          </button>
        </div>
      </div>

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
