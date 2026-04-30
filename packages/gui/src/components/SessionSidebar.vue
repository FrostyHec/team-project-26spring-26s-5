<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  MessageSquare,
  Settings,
  Trash2,
} from 'lucide-vue-next'
import { useChatStore, type ChatSession } from '@/stores/chat'
import { useSettingsStore } from '@/stores/settings'

const { t } = useI18n()
const chatStore = useChatStore()
const settingsStore = useSettingsStore()

const props = withDefaults(
  defineProps<{
    collapsed?: boolean
  }>(),
  {
    collapsed: false,
  },
)

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
    { label: t('sidebar.dateGroups.today'), sessions: [] },
    { label: t('sidebar.dateGroups.yesterday'), sessions: [] },
    { label: t('sidebar.dateGroups.previous7Days'), sessions: [] },
    { label: t('sidebar.dateGroups.older'), sessions: [] },
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
  settingsStore.openSettings()
}

function toggleSidebar() {
  chatStore.toggleSidebar()
}
</script>

<template>
  <aside
    class="flex flex-col h-full bg-gray-50 border-r border-gray-200 flex-shrink-0 transition-[width] duration-200"
    :class="props.collapsed ? 'w-16' : 'w-64'"
  >
    <!-- Session actions -->
    <div :class="props.collapsed ? 'p-2.5 space-y-2' : 'p-4 space-y-3'">
      <div class="flex items-center justify-between gap-2">
        <button
          data-testid="sidebar-toggle-btn"
          class="inline-flex items-center justify-center rounded-lg border shadow-sm transition-colors duration-150 cursor-pointer"
          :class="
            props.collapsed
              ? 'h-10 w-full border-blue-200 bg-blue-50 text-blue-600 hover:bg-blue-100'
              : 'h-9 w-9 border-gray-200 bg-white text-gray-500 hover:border-blue-200 hover:bg-blue-50 hover:text-blue-600'
          "
          :title="t('chat.toggleSidebar')"
          @click="toggleSidebar"
        >
          <PanelLeftOpen v-if="props.collapsed" class="w-4 h-4" />
          <PanelLeftClose v-else class="w-4 h-4" />
        </button>
        <span
          v-if="!props.collapsed"
          class="flex-1 text-xs font-semibold uppercase tracking-wider text-gray-400"
        >
          {{ t('sidebar.newChat') }}
        </span>
      </div>

      <button
        class="w-full flex items-center justify-center gap-2 bg-blue-600 text-white rounded-lg text-sm font-medium shadow-sm hover:bg-blue-700 transition-colors duration-150 cursor-pointer"
        :class="props.collapsed ? 'h-10 px-0' : 'py-2.5 px-4'"
        @click="handleNewChat"
        :title="props.collapsed ? t('sidebar.newChat') : undefined"
      >
        <Plus class="w-4 h-4" />
        <span v-if="!props.collapsed">{{ t('sidebar.newChat') }}</span>
      </button>
    </div>

    <!-- Session list -->
    <div
      :class="
        props.collapsed ? 'flex-1 overflow-y-auto px-2 pb-3' : 'flex-1 overflow-y-auto px-3 pb-4'
      "
    >
      <div v-if="groupedSessions.length === 0" class="text-center text-gray-400 text-sm mt-8">
        <span v-if="!props.collapsed">{{ t('sidebar.noConversations') }}</span>
      </div>

      <div v-for="group in groupedSessions" :key="group.label" class="mb-4">
        <p
          v-if="!props.collapsed"
          class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 px-2"
        >
          {{ group.label }}
        </p>
        <div class="space-y-1">
          <div
            v-for="session in group.sessions"
            :key="session.id"
            class="w-full flex items-center rounded-lg text-left text-sm transition-all duration-150 group cursor-pointer"
            :title="props.collapsed ? session.title || t('sidebar.newChat') : undefined"
            :class="
              chatStore.activeSessionId === session.id
                ? 'bg-white shadow-sm border border-gray-200 text-blue-600 font-medium'
                : 'text-gray-600 hover:bg-gray-100 border border-transparent'
            "
            :style="
              props.collapsed ? 'padding: 10px; justify-content: center;' : 'padding: 10px 12px;'
            "
            @click="handleSelectSession(session.id)"
          >
            <MessageSquare
              class="w-[18px] h-[18px] flex-shrink-0"
              :class="chatStore.activeSessionId === session.id ? 'text-blue-500' : 'text-gray-400'"
            />
            <span v-if="!props.collapsed" class="flex-1 truncate font-medium text-sm">{{
              session.title || t('sidebar.newChat')
            }}</span>
            <button
              v-if="!props.collapsed"
              type="button"
              class="opacity-0 group-hover:opacity-100 p-1 rounded-md hover:bg-red-100 hover:text-red-600 transition-all"
              @click="handleDeleteSession(session.id, $event)"
              :title="t('sidebar.deleteChat')"
            >
              <Trash2 class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- User Info Footer -->
    <div
      :class="props.collapsed ? 'p-2.5 border-t border-gray-200' : 'p-4 border-t border-gray-200'"
    >
      <div class="flex items-center justify-end gap-3">
        <!-- User profile block hidden until sidebar account support is implemented. -->
        <button
          data-testid="settings-btn"
          @click="openSettings"
          class="text-gray-400 hover:text-gray-600 transition-colors duration-150 cursor-pointer"
          :title="props.collapsed ? t('sidebar.settings') : undefined"
        >
          <Settings class="w-[18px] h-[18px]" />
        </button>
      </div>
    </div>
  </aside>
</template>
