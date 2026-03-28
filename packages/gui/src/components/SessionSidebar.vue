<script setup lang="ts">
import { computed } from 'vue'
import { Plus, MessageSquare, Settings, Trash2 } from 'lucide-vue-next'
import { useChatStore, type ChatSession } from '@/stores/chat'

const chatStore = useChatStore()

const emit = defineEmits<{
  (e: 'newChat'): void
}>()

/** Group sessions by date. */
const groupedSessions = computed(() => {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 86400000)
  const weekAgo = new Date(today.getTime() - 7 * 86400000)

  const groups: { label: string; sessions: ChatSession[] }[] = [
    { label: 'Today', sessions: [] },
    { label: 'Yesterday', sessions: [] },
    { label: 'Previous 7 Days', sessions: [] },
    { label: 'Older', sessions: [] },
  ]

  for (const s of chatStore.sessions) {
    const date = new Date(s.updatedAt)
    if (date >= today) {
      groups[0]!.sessions.push(s)
    } else if (date >= yesterday) {
      groups[1]!.sessions.push(s)
    } else if (date >= weekAgo) {
      groups[2]!.sessions.push(s)
    } else {
      groups[3]!.sessions.push(s)
    }
  }

  return groups.filter((g) => g.sessions.length > 0)
})

function handleNewChat() {
  emit('newChat')
}

function handleSelectSession(id: string) {
  chatStore.switchSession(id)
}

function handleDeleteSession(id: string, event: Event) {
  event.stopPropagation()
  chatStore.removeSession(id)
}

function openSettings() {
  alert('Settings panel coming soon! Stay tuned.')
}
</script>

<template>
  <aside class="flex flex-col h-full w-64 bg-gray-50 border-r border-gray-200 flex-shrink-0">
    <!-- New Chat Button -->
    <div class="p-4">
      <button
        class="w-full flex items-center justify-center gap-2 bg-blue-600 text-white rounded-lg py-2.5 px-4 text-sm font-medium shadow-sm hover:bg-blue-700 transition-colors duration-150 cursor-pointer"
        @click="handleNewChat"
      >
        <Plus class="w-4 h-4" />
        New Chat
      </button>
    </div>

    <!-- Session list -->
    <div class="flex-1 overflow-y-auto px-3 pb-4">
      <div v-if="groupedSessions.length === 0" class="text-center text-gray-400 text-sm mt-8">
        No conversations yet
      </div>

      <div v-for="group in groupedSessions" :key="group.label" class="mb-4">
        <p
          class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 px-2"
        >
          {{ group.label }}
        </p>
        <div class="space-y-1">
          <div
            v-for="session in group.sessions"
            :key="session.id"
            class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left text-sm transition-all duration-150 group cursor-pointer"
            :class="
              chatStore.activeSessionId === session.id
                ? 'bg-white shadow-sm border border-gray-200 text-blue-600 font-medium'
                : 'text-gray-600 hover:bg-gray-100 border border-transparent'
            "
            @click="handleSelectSession(session.id)"
          >
            <MessageSquare
              class="w-[18px] h-[18px] flex-shrink-0"
              :class="
                chatStore.activeSessionId === session.id
                  ? 'text-blue-500'
                  : 'text-gray-400'
              "
            />
            <span class="flex-1 truncate font-medium text-sm">{{
              session.title || 'New Chat'
            }}</span>
            <button
              type="button"
              class="opacity-0 group-hover:opacity-100 p-1 rounded-md hover:bg-red-100 hover:text-red-600 transition-all"
              @click="handleDeleteSession(session.id, $event)"
              title="Delete Chat"
            >
              <Trash2 class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- User Info Footer -->
    <div class="p-4 border-t border-gray-200">
      <div class="flex items-center gap-3">
        <div
          class="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center font-bold text-sm text-gray-500 flex-shrink-0"
        >
          U
        </div>
        <span class="text-sm font-medium text-gray-700 flex-1">User Profile</span>
        <button
          @click="openSettings"
          class="text-gray-400 hover:text-gray-600 transition-colors duration-150 cursor-pointer"
        >
          <Settings class="w-[18px] h-[18px]" />
        </button>
      </div>
    </div>
  </aside>
</template>
