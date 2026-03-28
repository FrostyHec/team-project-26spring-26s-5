<script setup lang="ts">
import { AlertCircle } from 'lucide-vue-next'
import { useChatStore } from '@/stores/chat'
import ChatHeader from './chat/ChatHeader.vue'
import ChatMessageList from './chat/ChatMessageList.vue'
import ChatApprovalBanner from './chat/ChatApprovalBanner.vue'
import ChatInputBox from './chat/ChatInputBox.vue'

const chatStore = useChatStore()

const emit = defineEmits<{
  (e: 'toggleWorkspace'): void
  (e: 'toggleSidebar'): void
}>()
</script>

<template>
  <div class="flex flex-col h-full w-full relative z-0">
    <!-- Header -->
    <ChatHeader
      @toggle-workspace="emit('toggleWorkspace')"
      @toggle-sidebar="emit('toggleSidebar')"
    />

    <!-- Messages -->
    <ChatMessageList />

    <!-- Approval dialog -->
    <ChatApprovalBanner />

    <!-- Error bar -->
    <div
      v-if="chatStore.error"
      class="mx-4 mb-2 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-center gap-2"
    >
      <AlertCircle class="w-4 h-4 flex-shrink-0" />
      {{ chatStore.error }}
    </div>

    <!-- Input area -->
    <ChatInputBox />
  </div>
</template>
