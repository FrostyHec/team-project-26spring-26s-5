<script setup lang="ts">
import { onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import SessionSidebar from '@/components/SessionSidebar.vue'
import ChatPanel from '@/components/ChatPanel.vue'
import WorkspacePanel from '@/components/WorkspacePanel.vue'

const chatStore = useChatStore()

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
  <div
    class="flex w-full bg-white border rounded-xl shadow-xl overflow-hidden font-sans text-gray-800"
    style="height: 100vh; min-height: 600px"
  >
    <!-- Left sidebar: sessions -->
    <SessionSidebar @new-chat="handleNewChat" />

    <!-- Center: chat panel -->
    <div class="flex-1 flex flex-col min-w-[350px]">
      <ChatPanel @toggle-workspace="chatStore.toggleWorkspace" />
    </div>

    <!-- Right: workspace panel -->
    <Transition name="slide">
      <WorkspacePanel v-if="chatStore.isWorkspaceOpen" @close="chatStore.toggleWorkspace" />
    </Transition>
  </div>
</template>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: all 0.25s ease;
}
.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}
</style>
