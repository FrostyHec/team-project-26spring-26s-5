<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useSettingsStore } from '@/stores/settings'
import { useEventListener } from '@vueuse/core'
import SessionSidebar from '@/components/SessionSidebar.vue'
import ChatPanel from '@/components/ChatPanel.vue'
import WorkspacePanel from '@/components/WorkspacePanel.vue'
import SettingsPanel from '@/components/settings/SettingsPanel.vue'

const chatStore = useChatStore()
const settingsStore = useSettingsStore()
const isDragging = ref(false)
const workspaceWidth = ref(320) // Default right panel width

/** Right panel can be dragged up to 75% of window width. */
const MAX_PANEL_RATIO = 0.75
const MIN_PANEL_WIDTH = 300

useEventListener(window, 'mousemove', (e) => {
  if (!isDragging.value) return
  const newWidth = window.innerWidth - e.clientX
  if (newWidth > MIN_PANEL_WIDTH && newWidth < window.innerWidth * MAX_PANEL_RATIO) {
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
  await settingsStore.loadLlmSettings()
})

async function handleNewChat() {
  await chatStore.newSession()
}
</script>

<template>
  <div class="flex w-full h-screen bg-white text-gray-800 overflow-hidden">
    <!-- Left sidebar: sessions -->
    <SessionSidebar :collapsed="chatStore.isSidebarCollapsed" @new-chat="handleNewChat" />

    <!-- Center: chat panel -->
    <main class="flex-1 flex flex-col min-w-[320px] bg-white relative">
      <ChatPanel @toggle-workspace="chatStore.toggleWorkspace" />
    </main>

    <!-- Right: workspace panel with resizer -->
    <Transition name="slide">
      <aside
        v-if="chatStore.isWorkspaceOpen"
        class="flex flex-shrink-0 relative border-l border-gray-200 bg-white"
        :style="{ width: `${workspaceWidth}px` }"
        style="box-shadow: -4px 0 15px -3px rgba(0, 0, 0, 0.05)"
      >
        <!-- Resizer handle -->
        <div
          class="absolute left-0 top-0 bottom-0 w-2 -ml-1 cursor-col-resize hover:bg-blue-400/20 active:bg-blue-400/40 z-20 transition-colors"
          @mousedown="startDragging"
        />
        <div class="w-full h-full overflow-hidden">
          <WorkspacePanel @close="chatStore.toggleWorkspace" />
        </div>
      </aside>
    </Transition>
  </div>

  <!-- Settings panel overlay -->
  <Transition name="settings-fade">
    <div v-if="settingsStore.isOpen" class="fixed inset-0 z-50 flex">
      <!-- Backdrop -->
      <div class="absolute inset-0 bg-black/20" @click="settingsStore.closeSettings" />
      <!-- Panel -->
      <div
        class="relative z-10 m-auto w-full max-w-3xl h-[80vh] bg-white rounded-2xl shadow-2xl overflow-hidden border border-gray-200"
      >
        <SettingsPanel />
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}
.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

.settings-fade-enter-active,
.settings-fade-leave-active {
  transition: all 0.2s ease;
}
.settings-fade-enter-from,
.settings-fade-leave-to {
  opacity: 0;
}
.settings-fade-enter-from .relative,
.settings-fade-leave-to .relative {
  transform: scale(0.96);
}
</style>
