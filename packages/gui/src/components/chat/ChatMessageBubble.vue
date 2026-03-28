<script setup lang="ts">
import { computed } from 'vue'
import { Bot, User } from 'lucide-vue-next'
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
  <div class="flex gap-4 w-full" :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
    <!-- Assistant avatar -->
    <div
      v-if="msg.role === 'assistant'"
      class="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 bg-gradient-to-br from-blue-100 to-blue-50 border border-blue-200 shadow-sm"
    >
      <Bot class="w-5 h-5 text-blue-600" />
    </div>

    <div
      class="flex flex-col gap-2 w-full"
      :class="msg.role === 'user' ? 'items-end' : 'max-w-[85%]'"
    >
      <!-- Tool call badges -->
      <ChatToolBadges
        v-if="msg.toolCalls && msg.toolCalls.length > 0 && msg.role === 'assistant'"
        :tool-calls="msg.toolCalls"
      />

      <!-- ReAct trace block -->
      <ChatTraceBlock
        v-if="msg.traceSteps && msg.traceSteps.length > 0 && msg.role === 'assistant'"
        :steps="msg.traceSteps"
        :loop-active="!!msg.loopActive"
      />

      <!-- Message bubble -->
      <div
        class="relative rounded-2xl text-[15px] leading-relaxed break-words shadow-sm"
        :class="
          msg.role === 'user'
            ? 'px-5 py-3.5 bg-blue-600 text-white rounded-tr-sm self-end'
            : 'px-5 py-4 bg-white border border-gray-200 text-gray-800 rounded-tl-sm w-full'
        "
      >
        <template v-if="msg.role === 'user'">
          <div class="whitespace-pre-wrap">{{ msg.content }}</div>
        </template>
        <template v-else>
          <div
            v-if="renderedContent"
            class="prose prose-slate prose-blue max-w-none text-[15px] prose-p:my-2 prose-ul:my-2"
            v-html="renderedContent"
          />
          <!-- Typing dots when empty and loading -->
          <span v-if="showTypingDots" class="inline-flex gap-1 items-center h-6">
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
            class="inline-block w-1.5 h-[1.1em] bg-blue-500 animate-pulse ml-1 align-middle translate-y-[-1px]"
          />
        </template>
      </div>
    </div>

    <!-- User avatar -->
    <div
      v-if="msg.role === 'user'"
      class="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 bg-blue-600 shadow-sm"
    >
      <User class="w-5 h-5 text-white" />
    </div>
  </div>
</template>
