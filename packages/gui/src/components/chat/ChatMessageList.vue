<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { Bot } from 'lucide-vue-next'
import { useChatStore } from '@/stores/chat'
import ChatMessageBubble from './ChatMessageBubble.vue'

const chatStore = useChatStore()

const scrollContainer = ref<HTMLElement | null>(null)
/** True while the user has scrolled upward and is reading history. */
const userHasScrolledUp = ref(false)

function onScroll() {
  const el = scrollContainer.value
  if (!el) return
  // Consider "at bottom" if within 80px of the bottom
  const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
  userHasScrolledUp.value = distFromBottom > 80
}

/** Scroll to bottom using instant (non-smooth) behavior to avoid jitter. */
function scrollToBottom() {
  if (userHasScrolledUp.value) return
  nextTick(() => {
    const el = scrollContainer.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  })
}

// Watch for new messages only (length change), not every deep mutation
watch(
  () => chatStore.messages.length,
  () => {
    userHasScrolledUp.value = false
    scrollToBottom()
  },
)

// Also watch the last message's content for streaming updates
watch(
  () => {
    const msgs = chatStore.messages
    return msgs.length > 0 ? msgs[msgs.length - 1]?.content : ''
  },
  () => {
    scrollToBottom()
  },
)

onMounted(() => {
  scrollContainer.value?.addEventListener('scroll', onScroll, { passive: true })
})

onUnmounted(() => {
  scrollContainer.value?.removeEventListener('scroll', onScroll)
})
</script>

<template>
  <div
    ref="scrollContainer"
    class="flex-1 overflow-y-auto px-5 py-6 bg-gray-50/30"
  >
    <div class="mx-auto w-full max-w-[920px]">
      <!-- Empty state -->
      <div
        v-if="chatStore.messages.length === 0"
        class="flex flex-col items-center justify-center h-full min-h-[46vh] text-gray-400"
      >
        <div
          class="w-16 h-16 rounded-2xl bg-blue-50 flex items-center justify-center mb-6 border border-blue-100"
        >
          <Bot class="w-8 h-8 text-blue-400" />
        </div>
        <h3 class="text-lg font-semibold text-gray-600 mb-2">How can I help you today?</h3>
        <p class="text-sm text-center max-w-sm text-gray-400 leading-relaxed">
          Ask about courses, deadlines, campus policies, or type
          <strong class="text-blue-500 bg-blue-50 px-1.5 py-0.5 rounded text-xs">@</strong> to select
          a specific AI skill.
        </p>
      </div>

      <!-- Message list -->
      <div v-else class="space-y-6">
        <ChatMessageBubble
          v-for="(msg, i) in chatStore.messages"
          :key="msg.id"
          :msg="msg"
          :is-last="i === chatStore.messages.length - 1"
        />
      </div>
    </div>
  </div>
</template>
