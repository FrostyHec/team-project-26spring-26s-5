<script setup lang="ts">
import { ref, nextTick, watch, computed, onMounted } from 'vue'
import {
  Send,
  Paperclip,
  PanelRightOpen,
  PanelRightClose,
  CheckCircle2,
  Loader2,
  AlertCircle,
  ChevronDown,
  Bot,
  User,
} from 'lucide-vue-next'
import { useChatStore, type ChatMessage, type TraceStep } from '@/stores/chat'

const chatStore = useChatStore()
const inputText = ref('')
const messagesEnd = ref<HTMLElement | null>(null)
const showSkillMenu = ref(false)
const inputRef = ref<HTMLTextAreaElement | null>(null)

const emit = defineEmits<{
  (e: 'toggleWorkspace'): void
}>()

// Auto-scroll
watch(
  () => chatStore.messages,
  async () => {
    await nextTick()
    messagesEnd.value?.scrollIntoView({ behavior: 'smooth' })
  },
  { deep: true },
)

onMounted(() => {
  chatStore.loadSkills()
})

/** Detect @ mention and show skill menu. */
function handleInput() {
  const text = inputText.value
  const lastAt = text.lastIndexOf('@')
  if (lastAt >= 0 && lastAt === text.length - 1) {
    showSkillMenu.value = true
  } else if (lastAt >= 0) {
    const afterAt = text.slice(lastAt + 1)
    showSkillMenu.value = !afterAt.includes(' ')
  } else {
    showSkillMenu.value = false
  }
}

/** Filter skills for @mention autocomplete. */
const filteredSkills = computed(() => {
  const text = inputText.value
  const lastAt = text.lastIndexOf('@')
  if (lastAt < 0) return chatStore.skills
  const query = text.slice(lastAt + 1).toLowerCase()
  return chatStore.skills.filter(
    (s) => s.name.toLowerCase().includes(query) || s.id.toLowerCase().includes(query),
  )
})

/** Select a skill from @mention dropdown. */
function selectSkill(skillId: string, skillName: string) {
  const text = inputText.value
  const lastAt = text.lastIndexOf('@')
  if (lastAt >= 0) {
    inputText.value = text.slice(0, lastAt) + `@${skillName} `
  }
  showSkillMenu.value = false
  // Set the skill for the current session
  if (chatStore.activeSession) {
    chatStore.activeSession.skill = skillId
  }
  inputRef.value?.focus()
}

async function handleSend() {
  if (!inputText.value.trim() || chatStore.isLoading) return
  const msg = inputText.value
  inputText.value = ''
  showSkillMenu.value = false
  await chatStore.sendMessage(msg)
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
  if (e.key === 'Escape') {
    showSkillMenu.value = false
  }
}

/** Format trace step for display. */
function traceIcon(step: TraceStep): string {
  switch (step.type) {
    case 'loop_start':
      return '▶'
    case 'thinking':
      return '💭'
    case 'tool_start':
      return '🔧'
    case 'tool_end':
      return '✅'
    case 'loop_end':
      return '■'
    case 'approval_request':
      return '⚠️'
    case 'widget_display':
      return '📊'
    default:
      return '•'
  }
}

/** Quick skill pills for the input area. */
const quickSkills = computed(() => {
  return chatStore.skills.slice(0, 3)
})
</script>

<template>
  <div class="flex flex-col h-full min-w-[350px]">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-white">
      <div class="flex items-center gap-2">
        <Bot class="w-5 h-5 text-blue-600" />
        <h2 class="text-sm font-semibold text-gray-800">Student Management Agent</h2>
        <span
          class="w-2 h-2 rounded-full"
          :class="chatStore.isConnected ? 'bg-green-400' : 'bg-red-400'"
        />
      </div>
      <button
        class="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 transition-colors"
        @click="emit('toggleWorkspace')"
      >
        <PanelRightClose v-if="chatStore.isWorkspaceOpen" class="w-5 h-5" />
        <PanelRightOpen v-else class="w-5 h-5" />
      </button>
    </div>

    <!-- Messages area -->
    <div class="flex-1 overflow-y-auto px-4 py-4">
      <!-- Empty state -->
      <div
        v-if="chatStore.messages.length === 0"
        class="flex flex-col items-center justify-center h-full text-gray-400"
      >
        <div class="w-16 h-16 rounded-full bg-blue-50 flex items-center justify-center mb-4">
          <Bot class="w-8 h-8 text-blue-400" />
        </div>
        <h3 class="text-lg font-medium text-gray-600 mb-1">Student Management Agent</h3>
        <p class="text-sm text-center max-w-xs">
          Ask about courses, deadlines, campus policies, or use @mention to select a skill.
        </p>
      </div>

      <!-- Message list -->
      <div v-else class="space-y-4">
        <div
          v-for="msg in chatStore.messages"
          :key="msg.id"
          class="flex gap-3"
          :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
        >
          <!-- Avatar -->
          <div
            v-if="msg.role === 'assistant'"
            class="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 bg-blue-100"
          >
            <Bot class="w-4 h-4 text-blue-600" />
          </div>

          <div class="max-w-[75%]" :class="msg.role === 'user' ? 'order-first' : ''">
            <!-- Tool calls summary -->
            <div
              v-if="msg.toolCalls && msg.toolCalls.length > 0 && msg.role === 'assistant'"
              class="mb-2"
            >
              <div
                v-for="(tc, i) in msg.toolCalls"
                :key="i"
                class="inline-flex items-center gap-1.5 px-2.5 py-1 bg-gray-100 rounded-full text-xs text-gray-600 mb-1 mr-1"
              >
                <CheckCircle2 v-if="tc.status === 'completed'" class="w-3.5 h-3.5 text-green-500" />
                <Loader2
                  v-else-if="tc.status === 'running'"
                  class="w-3.5 h-3.5 text-blue-500 animate-spin"
                />
                <AlertCircle v-else class="w-3.5 h-3.5 text-red-500" />
                <span>{{ tc.name }}</span>
              </div>
            </div>

            <!-- ReAct Trace (collapsible) -->
            <details
              v-if="msg.traceSteps && msg.traceSteps.length > 0 && msg.role === 'assistant'"
              class="mb-2"
              :open="msg.loopActive"
            >
              <summary
                class="flex items-center gap-1.5 text-xs text-gray-500 cursor-pointer hover:text-gray-700 select-none"
              >
                <ChevronDown class="w-3.5 h-3.5 transition-transform" />
                {{
                  msg.loopActive
                    ? 'ReAct loop running...'
                    : `ReAct trace (${msg.traceSteps.length} steps)`
                }}
              </summary>
              <div class="mt-1.5 ml-1 pl-3 border-l-2 border-gray-200 space-y-1">
                <div v-for="(step, i) in msg.traceSteps" :key="i" class="text-xs text-gray-500">
                  <span class="mr-1">{{ traceIcon(step) }}</span>
                  <template v-if="step.type === 'thinking'">
                    <span class="text-gray-600">{{ step.content }}</span>
                  </template>
                  <template v-else-if="step.type === 'tool_start'">
                    <span class="font-medium text-gray-700">{{ step.name }}</span>
                    <code class="ml-1 text-xs bg-gray-100 px-1 py-0.5 rounded">
                      {{ JSON.stringify(step.input) }}
                    </code>
                  </template>
                  <template v-else-if="step.type === 'tool_end'">
                    <span class="text-green-600">Result:</span>
                    <code class="ml-1 text-xs bg-gray-100 px-1 py-0.5 rounded">
                      {{ step.output?.slice(0, 200) }}
                    </code>
                  </template>
                  <template v-else-if="step.type === 'loop_start'">
                    <span class="text-blue-500">ReAct loop started</span>
                  </template>
                  <template v-else-if="step.type === 'loop_end'">
                    <span class="text-blue-500">ReAct loop finished</span>
                  </template>
                  <template v-else-if="step.type === 'approval_request'">
                    <span class="text-amber-600 font-medium">Approval: {{ step.name }}</span>
                  </template>
                  <template v-else-if="step.type === 'widget_display'">
                    <span class="text-purple-600">Widget: {{ step.widgetType }}</span>
                  </template>
                </div>
              </div>
            </details>

            <!-- Message bubble -->
            <div
              class="px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap"
              :class="
                msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-tr-sm'
                  : 'bg-white border border-gray-100 shadow-sm text-gray-800 rounded-tl-sm'
              "
            >
              {{ msg.content }}
              <!-- Typing indicator for empty assistant messages during streaming -->
              <span
                v-if="msg.role === 'assistant' && !msg.content && chatStore.isLoading"
                class="inline-flex gap-1"
              >
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
            </div>
          </div>

          <!-- User avatar -->
          <div
            v-if="msg.role === 'user'"
            class="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 bg-blue-600"
          >
            <User class="w-4 h-4 text-white" />
          </div>
        </div>
      </div>

      <!-- Scroll anchor -->
      <div ref="messagesEnd" />
    </div>

    <!-- Approval dialog overlay -->
    <div
      v-if="chatStore.pendingApproval"
      class="mx-4 mb-2 p-4 bg-amber-50 border border-amber-200 rounded-xl shadow-lg"
    >
      <div class="flex items-start gap-3">
        <AlertCircle class="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
        <div class="flex-1">
          <h4 class="text-sm font-semibold text-gray-800 mb-1">Tool Approval Required</h4>
          <p class="text-xs text-gray-600 mb-2">
            <strong>{{ chatStore.pendingApproval.toolName }}</strong>
          </p>
          <code
            class="block text-xs bg-white p-2 rounded border border-amber-100 mb-3 max-h-20 overflow-auto"
          >
            {{ JSON.stringify(chatStore.pendingApproval.toolArgs, null, 2) }}
          </code>
          <div class="flex gap-2">
            <button
              class="px-3 py-1.5 bg-green-600 text-white text-xs rounded-lg hover:bg-green-700 transition-colors"
              @click="chatStore.respondToApproval(true)"
            >
              ✅ Approve
            </button>
            <button
              class="px-3 py-1.5 bg-red-600 text-white text-xs rounded-lg hover:bg-red-700 transition-colors"
              @click="chatStore.respondToApproval(false)"
            >
              ❌ Reject
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Error bar -->
    <div
      v-if="chatStore.error"
      class="mx-4 mb-2 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-center gap-2"
    >
      <AlertCircle class="w-4 h-4 flex-shrink-0" />
      {{ chatStore.error }}
    </div>

    <!-- Input area -->
    <div class="px-4 pb-4 pt-2">
      <!-- Skill pills -->
      <div v-if="quickSkills.length > 0" class="flex gap-1.5 mb-2">
        <button
          v-for="skill in quickSkills"
          :key="skill.id"
          class="text-xs px-2.5 py-1 rounded-full border transition-colors hover:shadow-sm"
          :class="
            chatStore.activeSession?.skill === skill.id
              ? 'bg-blue-100 border-blue-300 text-blue-700'
              : 'bg-white border-gray-200 text-gray-600 hover:border-blue-300 hover:text-blue-600'
          "
          @click="selectSkill(skill.id, skill.name)"
        >
          @{{ skill.name }}
        </button>
      </div>

      <!-- Input box -->
      <div
        class="relative flex items-end gap-2 border border-gray-300 rounded-xl shadow-sm focus-within:ring-2 focus-within:ring-blue-100 focus-within:border-blue-400 transition-all bg-white"
      >
        <!-- @mention dropdown -->
        <div
          v-if="showSkillMenu && filteredSkills.length > 0"
          class="absolute bottom-full left-0 right-0 mb-1 bg-white border border-gray-200 rounded-lg shadow-lg z-10 max-h-48 overflow-y-auto"
        >
          <button
            v-for="skill in filteredSkills"
            :key="skill.id"
            class="w-full text-left px-3 py-2 text-sm hover:bg-blue-50 transition-colors flex items-center gap-2"
            @click="selectSkill(skill.id, skill.name)"
          >
            <span>{{ skill.icon }}</span>
            <span class="font-medium">{{ skill.name }}</span>
            <span class="text-xs text-gray-400 ml-auto">{{ skill.description?.slice(0, 40) }}</span>
          </button>
        </div>

        <button class="p-2.5 text-gray-400 hover:text-gray-600 transition-colors flex-shrink-0">
          <Paperclip class="w-5 h-5" />
        </button>

        <textarea
          ref="inputRef"
          v-model="inputText"
          placeholder="Message Agent... (Type '@' to select a skill)"
          rows="1"
          class="flex-1 py-2.5 text-sm resize-none outline-none bg-transparent max-h-32"
          :disabled="chatStore.isLoading"
          @input="handleInput"
          @keydown="handleKeydown"
        />

        <button
          class="p-2.5 text-white bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 rounded-lg m-1 transition-colors flex-shrink-0"
          :disabled="!inputText.trim() || chatStore.isLoading"
          @click="handleSend"
        >
          <Send class="w-4 h-4" />
        </button>
      </div>
    </div>
  </div>
</template>
