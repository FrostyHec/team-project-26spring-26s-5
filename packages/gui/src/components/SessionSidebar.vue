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
</script>

<template>
  <aside class="flex flex-col h-full w-64 bg-gray-50 border-r border-gray-200">
    <!-- Header -->
    <div class="p-3">
      <button
        class="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium shadow-sm"
        @click="handleNewChat"
      >
        <Plus class="w-4 h-4" />
        New Chat
      </button>
    </div>

    <!-- Session list -->
    <div class="flex-1 overflow-y-auto px-2 pb-2">
      <div v-if="groupedSessions.length === 0" class="text-center text-gray-400 text-xs mt-8">
        No conversations yet
      </div>

      <div v-for="group in groupedSessions" :key="group.label" class="mb-3">
        <h4 class="px-2 py-1 text-xs font-medium text-gray-400 uppercase tracking-wider">
          {{ group.label }}
        </h4>
        <div class="space-y-0.5">
          <button
            v-for="session in group.sessions"
            :key="session.id"
            class="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left text-sm transition-all group"
            :class="
              chatStore.activeSessionId === session.id
                ? 'bg-white shadow-sm border border-gray-200 text-blue-600'
                : 'text-gray-700 hover:bg-gray-100'
            "
            @click="handleSelectSession(session.id)"
          >
            <MessageSquare class="w-4 h-4 flex-shrink-0 opacity-60" />
            <span class="flex-1 truncate">{{ session.title || 'New Chat' }}</span>
            <button
              class="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-red-100 hover:text-red-600 transition-all"
              @click="handleDeleteSession(session.id, $event)"
            >
              <Trash2 class="w-3.5 h-3.5" />
            </button>
          </button>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <div class="p-3 border-t border-gray-200">
      <div class="flex items-center gap-3 px-2 py-1">
        <div
          class="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center text-sm font-medium"
        >
          U
        </div>
        <span class="text-sm text-gray-700 flex-1">User Profile</span>
        <Settings class="w-4 h-4 text-gray-400 cursor-pointer hover:text-gray-600" />
      </div>
    </div>
  </aside>
</template>
