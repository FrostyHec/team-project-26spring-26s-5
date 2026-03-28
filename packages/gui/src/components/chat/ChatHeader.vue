<script setup lang="ts">
import { Bot, PanelRightOpen, PanelRightClose } from 'lucide-vue-next'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()

const emit = defineEmits<{
  (e: 'toggleWorkspace'): void
}>()
</script>

<template>
  <div
    class="flex items-center justify-between px-6 py-3.5 border-b border-slate-200 bg-white/90 backdrop-blur-md sticky top-0 z-10 shadow-sm"
  >
    <div class="flex items-center gap-3">
      <div class="w-8 h-8 rounded-xl bg-blue-600 flex items-center justify-center shadow-md">
        <Bot class="w-5 h-5 text-white" />
      </div>
      <div>
        <h2 class="text-[15px] font-bold text-slate-800 tracking-tight leading-tight">
          Student Management Agent
        </h2>
        <div class="flex items-center gap-1.5 mt-0.5">
          <span
            class="w-2 h-2 rounded-full"
            :class="chatStore.isConnected ? 'bg-emerald-500' : 'bg-rose-500'"
          />
          <span
            class="text-[11px] font-medium"
            :class="chatStore.isConnected ? 'text-emerald-600' : 'text-rose-600'"
          >
            {{ chatStore.isConnected ? 'Online' : 'Offline' }}
          </span>
        </div>
      </div>
    </div>
    <button
      class="p-2 rounded-xl hover:bg-slate-100 text-slate-400 hover:text-blue-600 transition-all active:scale-95"
      title="Toggle Workspace"
      @click="emit('toggleWorkspace')"
    >
      <PanelRightClose v-if="chatStore.isWorkspaceOpen" class="w-5 h-5" />
      <PanelRightOpen v-else class="w-5 h-5" />
    </button>
  </div>
</template>
