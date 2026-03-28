<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import { useChatStore } from '@/stores/chat'
import type { ChatMessage } from '@/stores/chatTypes'
import ChatToolBadges from './ChatToolBadges.vue'
import ChatTraceBlock from './ChatTraceBlock.vue'

const props = defineProps<{
  msg: ChatMessage
  isLast: boolean
}>()

const chatStore = useChatStore()

const md = new MarkdownIt({ html: true, breaks: true, linkify: true })

/** Cached Markdown → safe HTML. Recalculated only when msg.content changes. */
const renderedContent = computed(() =>
  props.msg.content ? DOMPurify.sanitize(md.render(props.msg.content)) : '',
)

const showTypingDots = computed(() => !props.msg.content && chatStore.isLoading && props.isLast)

const showCursor = computed(() => !!props.msg.content && chatStore.isLoading && props.isLast)
</script>

<template>
  <div
    class="flex flex-col"
    :class="msg.role === 'user' ? 'items-end' : 'items-start'"
  >
    <!-- Tool call badges (assistant only) -->
    <ChatToolBadges
      v-if="msg.toolCalls && msg.toolCalls.length > 0 && msg.role === 'assistant'"
      :tool-calls="msg.toolCalls"
      class="mb-2 ml-1"
    />

    <!-- ReAct trace block -->
    <ChatTraceBlock
      v-if="msg.traceSteps && msg.traceSteps.length > 0 && msg.role === 'assistant'"
      :steps="msg.traceSteps"
      :loop-active="!!msg.loopActive"
      class="mb-2 w-full max-w-[80%]"
    />

    <!-- Message bubble -->
    <div
      class="max-w-[80%] px-6 py-4 text-[15px] leading-7"
      :class="
        msg.role === 'user'
          ? 'bg-blue-600 text-white rounded-2xl rounded-tr-sm shadow-sm'
          : 'bg-white border border-gray-100 shadow-sm text-gray-800 rounded-2xl rounded-tl-sm'
      "
    >
      <template v-if="msg.role === 'user'">
        <div class="whitespace-pre-wrap leading-7 [word-break:break-word]">{{ msg.content }}</div>
      </template>
      <template v-else>
        <div
          v-if="renderedContent"
          class="chat-bubble-content prose prose-sm prose-gray max-w-none prose-p:my-3 prose-ul:my-3 prose-ol:my-3 prose-li:my-1.5"
          v-html="renderedContent"
        />
        <!-- Typing dots when empty and loading -->
        <span v-if="showTypingDots" class="inline-flex gap-1 items-center h-5">
          <span
            class="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
            style="animation-delay: 0ms"
          />
          <span
            class="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
            style="animation-delay: 150ms"
          />
          <span
            class="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
            style="animation-delay: 300ms"
          />
        </span>
        <!-- Blinking cursor while streaming -->
        <span
          v-if="showCursor"
          class="inline-block w-1.5 h-[1em] bg-blue-500 animate-pulse ml-0.5 align-middle"
        />
      </template>
    </div>
  </div>
</template>

<style scoped>
.chat-bubble-content :deep(p + p) {
  margin-top: 0.65rem;
}

.chat-bubble-content :deep(ul),
.chat-bubble-content :deep(ol) {
  padding-left: 1.1rem;
}

.chat-bubble-content :deep(li) {
  line-height: 1.75;
}
</style>
