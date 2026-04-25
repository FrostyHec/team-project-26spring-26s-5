<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import { Check, ChevronLeft, ChevronRight, Pencil, RotateCcw, X } from 'lucide-vue-next'
import { useChatStore } from '@/stores/chat'
import { MESSAGE_STATUSES } from '@/stores/chatConstants'
import { useSettingsStore } from '@/stores/settings'
import type { ChatMessage } from '@/stores/chatTypes'
import ChatToolBadges from './ChatToolBadges.vue'
import ChatTraceBlock from './ChatTraceBlock.vue'

const props = defineProps<{
  msg: ChatMessage
  isLast: boolean
}>()

const { t, locale } = useI18n()
const chatStore = useChatStore()
const settingsStore = useSettingsStore()

const md = new MarkdownIt({ html: true, breaks: true, linkify: true })
const isEditing = ref(false)
const draftContent = ref(props.msg.content)

/** Cached Markdown → safe HTML. Recalculated only when msg.content changes. */
const renderedContent = computed(() =>
  props.msg.content ? DOMPurify.sanitize(md.render(props.msg.content)) : '',
)

const showTypingDots = computed(() => !props.msg.content && chatStore.isLoading && props.isLast)

const showCursor = computed(() => !!props.msg.content && chatStore.isLoading && props.isLast)

const showVersionTabs = computed(() => (props.msg.versionChoices?.length ?? 0) > 1)

const currentVersionChoiceIndex = computed(() => {
  const choices = props.msg.versionChoices ?? []
  if (choices.length === 0) {
    return -1
  }
  const selectedIndex = choices.findIndex((choice) => choice.nodeId === props.msg.selectedVersionId)
  return selectedIndex >= 0 ? selectedIndex : 0
})

const currentVersionDisplay = computed(() => {
  if (currentVersionChoiceIndex.value < 0) {
    return '1 / 1'
  }
  return `${currentVersionChoiceIndex.value + 1} / ${props.msg.versionChoices?.length ?? 1}`
})

const canGoToPreviousVersion = computed(
  () => showVersionTabs.value && currentVersionChoiceIndex.value > 0 && !chatStore.isLoading,
)

const canGoToNextVersion = computed(
  () =>
    showVersionTabs.value &&
    currentVersionChoiceIndex.value >= 0 &&
    currentVersionChoiceIndex.value < (props.msg.versionChoices?.length ?? 1) - 1 &&
    !chatStore.isLoading,
)

const canEditMessage = computed(() => !!props.msg.canEdit && !chatStore.isLoading)

const canRetryMessage = computed(() => !!props.msg.canRetry && !chatStore.isLoading)
const isDebugEnabled = computed(() => settingsStore.llmSettings.debug_mode)

watch(
  () => props.msg.content,
  (content) => {
    if (!isEditing.value) {
      draftContent.value = content
    }
  },
)

function startEditing(): void {
  draftContent.value = props.msg.content
  isEditing.value = true
}

function cancelEditing(): void {
  draftContent.value = props.msg.content
  isEditing.value = false
}

async function saveEdit(): Promise<void> {
  const content = draftContent.value.trim()
  if (!props.msg.nodeId || !content || content === props.msg.content) {
    isEditing.value = false
    return
  }
  await chatStore.editMessage(props.msg.nodeId, content, locale.value)
  isEditing.value = false
}

async function switchVersion(nodeId: string): Promise<void> {
  if (!props.msg.versionGroupId || nodeId === props.msg.selectedVersionId) {
    return
  }
  await chatStore.selectVersion(props.msg.versionGroupId, nodeId)
}

async function switchRelativeVersion(offset: -1 | 1): Promise<void> {
  const choices = props.msg.versionChoices ?? []
  const nextIndex = currentVersionChoiceIndex.value + offset
  const nextChoice = choices[nextIndex]
  if (!nextChoice) {
    return
  }
  await switchVersion(nextChoice.nodeId)
}

async function retryMessage(): Promise<void> {
  if (!props.msg.nodeId) {
    return
  }
  await chatStore.retryMessage(props.msg.nodeId, locale.value)
}
</script>

<template>
  <div class="flex flex-col" :class="msg.role === 'user' ? 'items-end' : 'items-start'">
    <div
      v-if="showVersionTabs"
      class="mb-2 flex max-w-[72%] items-center gap-2"
      :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
    >
      <button
        type="button"
        class="inline-flex h-7 w-7 items-center justify-center rounded-full border text-gray-600 transition-colors"
        :class="
          canGoToPreviousVersion
            ? 'border-gray-200 bg-white hover:border-blue-300 hover:text-blue-700'
            : 'cursor-not-allowed border-gray-100 bg-gray-50 text-gray-300'
        "
        :aria-label="t('chat.previousVersion')"
        :disabled="!canGoToPreviousVersion"
        data-testid="version-prev"
        @click="switchRelativeVersion(-1)"
      >
        <ChevronLeft class="h-3.5 w-3.5" />
      </button>
      <div
        class="min-w-16 rounded-full border border-gray-200 bg-white px-3 py-1 text-center text-xs font-semibold text-gray-700"
        data-testid="version-indicator"
      >
        {{ currentVersionDisplay }}
      </div>
      <button
        type="button"
        class="inline-flex h-7 w-7 items-center justify-center rounded-full border text-gray-600 transition-colors"
        :class="
          canGoToNextVersion
            ? 'border-gray-200 bg-white hover:border-blue-300 hover:text-blue-700'
            : 'cursor-not-allowed border-gray-100 bg-gray-50 text-gray-300'
        "
        :aria-label="t('chat.nextVersion')"
        :disabled="!canGoToNextVersion"
        data-testid="version-next"
        @click="switchRelativeVersion(1)"
      >
        <ChevronRight class="h-3.5 w-3.5" />
      </button>
    </div>

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
      :debug-enabled="isDebugEnabled"
      class="mb-2 w-full max-w-[72%]"
    />

    <!-- Message bubble -->
    <div
      data-testid="message-bubble"
      class="max-w-[72%] px-6 py-4 text-[15px] leading-7"
      :class="
        isEditing && msg.role === 'user'
          ? 'bg-slate-50 border border-slate-200 text-slate-900 rounded-2xl shadow-md'
          : msg.role === 'user'
            ? 'bg-blue-600 text-white rounded-2xl rounded-tr-sm shadow-sm'
            : msg.role === 'system'
              ? 'bg-amber-50 border border-amber-200 text-amber-950 rounded-2xl rounded-tl-sm shadow-sm'
              : 'bg-white border border-gray-100 shadow-sm text-gray-800 rounded-2xl rounded-tl-sm'
      "
    >
      <template v-if="isEditing">
        <textarea
          v-model="draftContent"
          class="min-h-28 w-full resize-y rounded-xl border border-slate-300 bg-white px-3 py-2 text-[15px] leading-7 text-slate-900 outline-none ring-0"
        />
        <div class="mt-3 flex items-center justify-end gap-2">
          <button
            type="button"
            class="inline-flex items-center gap-1 rounded-full border border-gray-200 px-3 py-1.5 text-sm text-gray-600 transition-colors hover:border-gray-300 hover:text-gray-800"
            @click="cancelEditing"
          >
            <X class="h-4 w-4" />
            {{ t('chat.cancelEdit') }}
          </button>
          <button
            type="button"
            class="inline-flex items-center gap-1 rounded-full bg-slate-900 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-slate-700"
            @click="saveEdit"
          >
            <Check class="h-4 w-4" />
            {{ t('chat.saveEdit') }}
          </button>
        </div>
      </template>
      <template v-if="msg.role === 'user'">
        <div v-if="!isEditing" class="whitespace-pre-wrap leading-7 [word-break:break-word]">
          {{ msg.content }}
        </div>
      </template>
      <template v-else-if="msg.role === 'system'">
        <div class="whitespace-pre-wrap text-sm leading-6 [word-break:break-word]">
          {{ msg.content }}
        </div>
      </template>
      <template v-else>
        <div
          v-if="renderedContent && !isEditing"
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
          v-if="showCursor && !isEditing"
          class="inline-block w-1.5 h-[1em] bg-blue-500 animate-pulse ml-0.5 align-middle"
        />
      </template>
    </div>

    <div
      v-if="msg.nodeId && (canEditMessage || canRetryMessage) && !isEditing"
      class="mt-2 flex max-w-[72%] items-center gap-2 px-1"
      :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
    >
      <button
        v-if="canEditMessage"
        type="button"
        class="inline-flex items-center gap-1 rounded-full border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-600 transition-colors hover:border-blue-300 hover:text-blue-700"
        @click="startEditing"
      >
        <Pencil class="h-3.5 w-3.5" />
        {{ t('chat.editMessage') }}
      </button>
      <button
        v-if="canRetryMessage"
        type="button"
        class="inline-flex items-center gap-1 rounded-full border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-600 transition-colors hover:border-blue-300 hover:text-blue-700"
        @click="retryMessage"
      >
        <RotateCcw class="h-3.5 w-3.5" />
        {{ t('chat.retryMessage') }}
      </button>
    </div>

    <p
      v-if="msg.role === 'assistant' && msg.status === MESSAGE_STATUSES.INTERRUPTED"
      class="mt-2 px-2 text-sm text-gray-500"
    >
      {{ t('chat.interruptedHint') }}
    </p>
    <p
      v-else-if="msg.role === 'assistant' && msg.status === MESSAGE_STATUSES.FAILED"
      class="mt-2 px-2 text-sm text-red-600"
    >
      {{ t('chat.failedHint') }}
    </p>
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
