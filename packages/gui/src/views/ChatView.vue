<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useEventListener } from '@vueuse/core'
import SessionSidebar from '@/components/SessionSidebar.vue'
import ChatPanel from '@/components/ChatPanel.vue'
import WorkspacePanel from '@/components/WorkspacePanel.vue'

const chatStore = useChatStore()
const isDragging = ref(false)
const workspaceWidth = ref(400) // Default right panel width

useEventListener(window, 'mousemove', (e) => {
  if (!isDragging.value) return
  const newWidth = window.innerWidth - e.clientX
  if (newWidth > 300 && newWidth < 800) {
    workspaceWidth.value = newWidth
  }
})

useEventListener(window, 'mouseup', () => {
  if (isDragging.value) {
    isDragging.value = false
    document.body.style.cursor = ''
  }
})

function startDragging(e: MouseEvent) {
  isDragging.value = true
  document.body.style.cursor = 'col-resize'
  e.preventDefault()
}

onMounted(async () => {
  await chatStore.checkConnection()
  await chatStore.loadSessions()
  await chatStore.loadSkills()
})

async function handleNewChat() {
  await chatStore.newSession()
}
</script>

<template>
  <div class="flex w-full h-screen bg-[#f8fafc] text-slate-800 font-sans overflow-hidden">
    <!-- Left sidebar: sessions -->
    <SessionSidebar @new-chat="handleNewChat" />

    <!-- Center: chat panel -->
    <div class="flex-1 flex flex-col min-w-[400px] shadow-2xl z-10 bg-white relative">
      <ChatPanel @toggle-workspace="chatStore.toggleWorkspace" />
    </div>

    <!-- Right: workspace panel with resizer -->
    <Transition name="slide">
      <div
        v-if="chatStore.isWorkspaceOpen"
        class="flex flex-shrink-0 relative bg-slate-50 border-l border-slate-200"
        :style="{ width: `${workspaceWidth}px` }"
      >
        <!-- Resizer handle -->
        <div
          class="absolute left-0 top-0 bottom-0 w-2.5 -ml-1.5 cursor-col-resize hover:bg-blue-400/20 active:bg-blue-400/40 z-20 transition-colors"
          @mousedown="startDragging"
        />
        <div class="w-full h-full overflow-hidden">
          <WorkspacePanel @close="chatStore.toggleWorkspace" />
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}
.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}
</style>
