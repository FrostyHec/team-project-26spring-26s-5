<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Check,
  Pencil,
  MessageSquare,
  MoreHorizontal,
  PanelRightOpen,
  PanelRightClose,
} from 'lucide-vue-next'
import { useChatStore } from '@/stores/chat'

const { t } = useI18n()
const chatStore = useChatStore()
const isEditingTitle = ref(false)
const draftTitle = ref('')

watch(
  () => chatStore.activeSession?.title,
  (title) => {
    draftTitle.value = title || ''
    isEditingTitle.value = false
  },
  { immediate: true },
)

const emit = defineEmits<{
  (e: 'toggleWorkspace'): void
}>()

function startEditingTitle(): void {
  if (!chatStore.activeSession) {
    return
  }
  draftTitle.value = chatStore.activeSession.title || ''
  isEditingTitle.value = true
}

async function saveTitle(): Promise<void> {
  if (!chatStore.activeSession) {
    return
  }
  await chatStore.renameSession(chatStore.activeSession.id, draftTitle.value)
  isEditingTitle.value = false
}
</script>

<template>
  <header
    class="h-16 border-b border-gray-200 flex items-center justify-between px-6 bg-white/90 backdrop-blur-sm flex-shrink-0 z-10"
  >
    <div class="flex items-center gap-3">
      <MessageSquare class="w-5 h-5 text-gray-400" />
      <template v-if="isEditingTitle && chatStore.activeSession">
        <input
          v-model="draftTitle"
          class="rounded-md border border-gray-300 px-2 py-1 text-sm font-semibold text-gray-800 outline-none focus:border-blue-400"
          :placeholder="t('chat.defaultTitle')"
          @keydown.enter.prevent="saveTitle"
          @blur="saveTitle"
        />
      </template>
      <h1 v-else class="font-semibold text-gray-800 text-base">
        {{ chatStore.activeSession?.title || t('chat.defaultTitle') }}
      </h1>
      <button
        v-if="chatStore.activeSession"
        class="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-md transition-colors duration-150 cursor-pointer"
        :title="t('chat.editTitle')"
        @click="isEditingTitle ? saveTitle() : startEditingTitle()"
      >
        <Check v-if="isEditingTitle" class="w-4 h-4" />
        <Pencil v-else class="w-4 h-4" />
      </button>
      <span
        class="w-2 h-2 rounded-full ml-1"
        :class="chatStore.isConnected ? 'bg-emerald-500' : 'bg-rose-500'"
      />
    </div>
    <div class="flex items-center gap-2">
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
