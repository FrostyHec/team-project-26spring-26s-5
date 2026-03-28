<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { Send, Paperclip } from 'lucide-vue-next'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()

const inputText = ref('')
const inputRef = ref<HTMLTextAreaElement | null>(null)
const showSkillMenu = ref(false)

/** Quick skill pills (first 3 skills). */
const quickSkills = computed(() => chatStore.skills.slice(0, 3))

/**
 * Determine if the `@` at position `atIndex` in `text` is a valid mention trigger.
 * A valid mention trigger is either at position 0 (line start) or preceded by
 * a whitespace character — this prevents email addresses from triggering the menu.
 */
function isValidMentionAt(text: string, atIndex: number): boolean {
  if (atIndex === 0) return true
  const preceding = text[atIndex - 1]
  return preceding === ' ' || preceding === '\n'
}

/** Find the last valid `@` position for mention detection. */
function findMentionAtIndex(text: string): number {
  let idx = text.lastIndexOf('@')
  while (idx >= 0) {
    if (isValidMentionAt(text, idx)) return idx
    idx = text.lastIndexOf('@', idx - 1)
  }
  return -1
}

/** Skills filtered by the current @mention query. */
const filteredSkills = computed(() => {
  const atIdx = findMentionAtIndex(inputText.value)
  if (atIdx < 0) return chatStore.skills
  const query = inputText.value.slice(atIdx + 1).toLowerCase()
  return chatStore.skills.filter(
    (s) => s.name.toLowerCase().includes(query) || s.id.toLowerCase().includes(query),
  )
})

/**
 * Handle textarea input: update @mention menu visibility and auto-resize.
 * T3.2: Dynamically adjust textarea height (max 160px).
 * T3.3: Only trigger @mention on line-start or post-space `@`.
 */
function handleInput(e: Event) {
  // Auto-resize textarea
  const target = e.target as HTMLTextAreaElement
  target.style.height = 'auto'
  target.style.height = `${Math.min(target.scrollHeight, 160)}px`

  // Update mention menu
  const text = inputText.value
  const atIdx = findMentionAtIndex(text)
  if (atIdx >= 0) {
    const afterAt = text.slice(atIdx + 1)
    showSkillMenu.value = !afterAt.includes(' ') && !afterAt.includes('\n')
  } else {
    showSkillMenu.value = false
  }
}

/** Select a skill from the @mention dropdown or quick pill. */
function selectSkill(skillId: string, skillName: string) {
  const text = inputText.value
  const atIdx = findMentionAtIndex(text)
  if (atIdx >= 0) {
    inputText.value = text.slice(0, atIdx) + `@${skillName} `
  } else {
    inputText.value = `@${skillName} ` + text
  }
  showSkillMenu.value = false
  if (!chatStore.activeSessionId) {
    chatStore.newSession(skillId)
  } else if (chatStore.activeSession) {
    chatStore.activeSession.skill = skillId
  }
  nextTick(() => inputRef.value?.focus())
}

async function handleSend() {
  if (!inputText.value.trim() || chatStore.isLoading) return
  const msg = inputText.value
  inputText.value = ''
  showSkillMenu.value = false
  // Reset textarea height
  if (inputRef.value) inputRef.value.style.height = 'auto'
  await chatStore.sendMessage(msg)
}

/**
 * T3.1: Guard against IME composition — do NOT send on Enter during composition.
 */
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    handleSend()
  }
  if (e.key === 'Escape') {
    showSkillMenu.value = false
  }
}
</script>

<template>
  <div class="p-5 bg-white border-t border-gray-100 flex-shrink-0">
    <div class="relative mx-auto w-full max-w-[920px]">
      <!-- @mention dropdown -->
      <div
        v-if="showSkillMenu && filteredSkills.length > 0"
        class="absolute bottom-full left-0 right-0 mb-2 bg-white border border-gray-200 rounded-xl shadow-lg z-20 max-h-56 overflow-y-auto p-1.5"
      >
        <button
          v-for="skill in filteredSkills"
          :key="skill.id"
          class="w-full text-left px-3 py-2.5 rounded-lg text-sm hover:bg-gray-50 transition-colors flex items-center gap-3"
          @click="selectSkill(skill.id, skill.name)"
        >
          <span class="text-lg shrink-0">{{ skill.icon }}</span>
          <div class="flex flex-col flex-1 min-w-0">
            <span class="font-medium text-gray-800 text-sm">{{ skill.name }}</span>
            <span class="text-xs text-gray-500 truncate">{{ skill.description }}</span>
          </div>
        </button>
      </div>

      <!-- Input composite -->
      <div
        class="flex items-end border border-gray-300 rounded-xl shadow-sm focus-within:ring-2 focus-within:ring-blue-100 focus-within:border-blue-400 transition-all duration-200 bg-gray-50/50 px-1 py-1"
      >
        <!-- Paperclip / Attach -->
        <button
          class="p-3.5 text-gray-400 hover:text-blue-500 transition-colors duration-150 flex-shrink-0 cursor-pointer"
          title="Attach file"
        >
          <Paperclip class="w-5 h-5" />
        </button>

        <!-- Text input -->
        <textarea
          ref="inputRef"
          v-model="inputText"
          placeholder="Message Agent... (Type '@' to invoke a skill)"
          rows="1"
          class="flex-1 py-4 bg-transparent border-none focus:ring-0 resize-none outline-none text-[15px] leading-7 min-h-[52px] max-h-36 text-gray-800 placeholder:text-gray-400"
          :disabled="chatStore.isLoading"
          @input="handleInput"
          @keydown="handleKeydown"
        />

        <!-- Send button -->
        <button
          class="p-2.5 m-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-200 disabled:text-gray-400 transition-colors duration-150 shadow-sm flex-shrink-0 cursor-pointer"
          :disabled="!inputText.trim() || chatStore.isLoading"
          @click="handleSend"
        >
          <Send class="w-[18px] h-[18px]" />
        </button>
      </div>
    </div>

    <!-- Skill Suggestions -->
    <div
      v-if="quickSkills.length > 0"
      class="mt-2.5 flex items-center gap-2 px-1 flex-wrap mx-auto w-full max-w-[920px]"
    >
      <span class="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Skills:</span>
      <button
        v-for="skill in quickSkills"
        :key="skill.id"
        class="text-[10px] font-semibold px-2.5 py-1 rounded-full transition-colors duration-150 cursor-pointer"
        :class="
          chatStore.activeSession?.skill === skill.id
            ? 'bg-blue-600 text-white'
            : 'text-blue-600 bg-blue-50 hover:bg-blue-100'
        "
        @click="selectSkill(skill.id, skill.name)"
      >
        @{{ skill.name }}
      </button>
    </div>
  </div>
</template>
