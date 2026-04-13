<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import {
  MessageSquare,
  MoreHorizontal,
  PanelLeftOpen,
  PanelLeftClose,
  PanelRightOpen,
  PanelRightClose,
} from 'lucide-vue-next'
import { useChatStore } from '@/stores/chat'

const { t } = useI18n()
const chatStore = useChatStore()

const emit = defineEmits<{
  (e: 'toggleWorkspace'): void
  (e: 'toggleSidebar'): void
}>()
</script>

<template>
  <header
    class="h-16 border-b border-gray-200 flex items-center justify-between px-6 bg-white/90 backdrop-blur-sm flex-shrink-0 z-10"
  >
    <div class="flex items-center gap-3">
      <MessageSquare class="w-5 h-5 text-gray-400" />
      <h1 class="font-semibold text-gray-800 text-base">
        {{ chatStore.activeSession?.title || t('chat.defaultTitle') }}
      </h1>
      <span
        class="w-2 h-2 rounded-full ml-1"
        :class="chatStore.isConnected ? 'bg-emerald-500' : 'bg-rose-500'"
      />
    </div>
    <div class="flex items-center gap-2">
      <!-- Sidebar toggle -->
      <button
        class="p-2 rounded-lg transition-colors duration-150 cursor-pointer"
        :class="
          chatStore.isSidebarCollapsed
            ? 'bg-blue-50 text-blue-600'
            : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
        "
        :title="t('chat.toggleSidebar')"
        @click="emit('toggleSidebar')"
      >
        <PanelLeftOpen v-if="chatStore.isSidebarCollapsed" class="w-5 h-5" />
        <PanelLeftClose v-else class="w-5 h-5" />
      </button>
      <!-- More button -->
      <button
        class="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors duration-150 cursor-pointer"
      >
        <MoreHorizontal class="w-5 h-5" />
      </button>
      <!-- Panel toggle -->
      <button
        class="p-2 rounded-lg transition-colors duration-150 cursor-pointer"
        :class="
          chatStore.isWorkspaceOpen
            ? 'bg-blue-50 text-blue-600'
            : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
        "
        :title="t('chat.toggleWorkspace')"
        @click="emit('toggleWorkspace')"
      >
        <PanelRightClose v-if="chatStore.isWorkspaceOpen" class="w-5 h-5" />
        <PanelRightOpen v-else class="w-5 h-5" />
      </button>
    </div>
  </header>
</template>
