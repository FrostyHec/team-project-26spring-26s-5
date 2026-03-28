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
  <aside class="flex flex-col h-full w-72 bg-[#f8fafc] border-r border-[#e2e8f0] flex-shrink-0">
    <!-- Header -->
    <div class="p-4">
      <button
        class="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors text-[15px] font-medium shadow-sm hover:shadow-md"
        @click="handleNewChat"
      >
        <Plus class="w-5 h-5" />
        New Chat
      </button>
    </div>

    <!-- Session list -->
    <div class="flex-1 overflow-y-auto px-3 pb-4">
      <div v-if="groupedSessions.length === 0" class="text-center text-slate-400 text-sm mt-8">
        No conversations yet
      </div>

      <div v-for="group in groupedSessions" :key="group.label" class="mb-4">
        <h4 class="px-3 py-1 mb-1 text-xs font-semibold text-slate-400 uppercase tracking-widest">
          {{ group.label }}
        </h4>
        <div class="space-y-1">
          <button
            v-for="session in group.sessions"
            :key="session.id"
            class="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-left text-[14px] transition-all group"
            :class="
              chatStore.activeSessionId === session.id
                ? 'bg-blue-50/80 shadow-sm border border-blue-100 text-blue-700 font-medium'
                : 'text-slate-600 hover:bg-slate-100 border border-transparent'
            "
            @click="handleSelectSession(session.id)"
          >
            <MessageSquare class="w-4 h-4 flex-shrink-0 opacity-70" />
            <span class="flex-1 truncate">{{ session.title || 'New Chat' }}</span>
            <button
              class="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg hover:bg-red-100 hover:text-red-700 transition-all ml-1"
              @click="handleDeleteSession(session.id, $event)"
              title="Delete Chat"
            >
              <Trash2 class="w-4 h-4" />
            </button>
          </button>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <div class="p-4 border-t border-slate-200 bg-white">
      <div class="flex items-center gap-3 px-2 py-1">
        <div
          class="w-9 h-9 rounded-full bg-gradient-to-br from-blue-600 to-indigo-700 shadow-sm text-white flex items-center justify-center text-sm font-semibold"
        >
          U
        </div>
        <span class="text-[15px] font-medium text-slate-700 flex-1">User Profile</span>
        <button
          @click="openSettings"
          class="p-2 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors"
        >
          <Settings class="w-5 h-5" />
        </button>
      </div>
    </div>
  </aside>
</template>
