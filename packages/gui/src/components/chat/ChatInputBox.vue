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
  <div
    class="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-white via-white to-transparent pt-10"
  >
    <div class="max-w-4xl mx-auto w-full">
      <!-- Quick skill pills -->
      <div v-if="quickSkills.length > 0" class="flex flex-wrap gap-2 mb-3">
        <button
          v-for="skill in quickSkills"
          :key="skill.id"
          class="text-[13px] px-3 py-1.5 rounded-full border transition-all duration-200 transform hover:-translate-y-0.5 shadow-sm"
          :class="
            chatStore.activeSession?.skill === skill.id
              ? 'bg-blue-600 border-blue-600 text-white shadow-md'
              : 'bg-white border-slate-200 text-slate-600 hover:border-blue-300 hover:text-blue-600 hover:shadow'
          "
          @click="selectSkill(skill.id, skill.name)"
        >
          @{{ skill.name }}
        </button>
      </div>

      <!-- Input box -->
      <div
        class="relative flex items-end gap-2 border border-slate-300 rounded-2xl shadow-lg hover:border-slate-400 focus-within:ring-4 focus-within:ring-blue-100 focus-within:border-blue-500 transition-all bg-white"
      >
        <!-- @mention dropdown -->
        <div
          v-if="showSkillMenu && filteredSkills.length > 0"
          class="absolute bottom-full left-0 right-0 mb-3 bg-white border border-slate-200 rounded-xl shadow-2xl z-20 max-h-64 overflow-y-auto w-full p-2"
        >
          <button
            v-for="skill in filteredSkills"
            :key="skill.id"
            class="w-full text-left px-4 py-3 rounded-lg text-sm hover:bg-slate-50 transition-colors flex items-center gap-3"
            @click="selectSkill(skill.id, skill.name)"
          >
            <span class="text-xl shrink-0">{{ skill.icon }}</span>
            <div class="flex flex-col flex-1 min-w-0">
              <span class="font-semibold text-slate-800">{{ skill.name }}</span>
              <span class="text-xs text-slate-500 truncate">{{ skill.description }}</span>
            </div>
          </button>
        </div>

        <button
          class="p-4 text-slate-400 hover:text-blue-600 transition-colors flex-shrink-0"
          title="Attach file"
        >
          <Paperclip class="w-5 h-5" />
        </button>

        <textarea
          ref="inputRef"
          v-model="inputText"
          placeholder="Message Student Agent... (Type '@' to mention a specific skill)"
          rows="1"
          class="flex-1 py-4 text-[15px] resize-none outline-none bg-transparent max-h-40 text-slate-800 placeholder:text-slate-400"
          :disabled="chatStore.isLoading"
          @input="handleInput"
          @keydown="handleKeydown"
        />

        <button
          class="p-3 text-white bg-blue-600 hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-400 rounded-xl m-2 transition-all flex-shrink-0 active:scale-95 shadow-sm"
          :disabled="!inputText.trim() || chatStore.isLoading"
          @click="handleSend"
        >
          <Send class="w-5 h-5 ml-0.5 mt-0.5" />
        </button>
      </div>

      <div class="text-center mt-2">
        <span class="text-[11px] text-slate-400"
          >AI can make mistakes. Consider verifying important information.</span
        >
      </div>
    </div>
  </div>
</template>
