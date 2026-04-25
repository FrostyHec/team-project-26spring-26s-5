<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Send, Paperclip, Square } from 'lucide-vue-next'
import { useChatStore } from '@/stores/chat'
import { useSettingsStore } from '@/stores/settings'
import MenuDropdown from '@/components/common/MenuDropdown.vue'

const { t, locale } = useI18n()
const chatStore = useChatStore()
const settingsStore = useSettingsStore()

const inputText = ref('')
const inputRef = ref<HTMLTextAreaElement | null>(null)
const showSkillMenu = ref(false)

/** Quick skill pills (first 3 skills). */
const quickSkills = computed(() => chatStore.skills.slice(0, 3))

const providerOptions = computed(() =>
  [...settingsStore.llmSettings.providers]
    .filter((provider) => provider.enabled)
    .sort((left, right) => left.priority - right.priority),
)

const selectedProvider = computed(
  () =>
    providerOptions.value.find((provider) => provider.id === chatStore.selectedProviderId) ?? null,
)

const selectedProviderLabel = computed(
  () => selectedProvider.value?.name || selectedProvider.value?.id || t('chat.providerNone'),
)

onMounted(async () => {
  if (settingsStore.llmSettings.providers.length === 0) {
    await settingsStore.loadLlmSettings()
  }
})

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

function selectProvider(providerId: string, closeDropdown: () => void): void {
  void chatStore.updateActiveSessionPreferences({ selected_provider_id: providerId })
  closeDropdown()
}

async function handleSend() {
  if (!inputText.value.trim() || chatStore.isLoading) return
  const msg = inputText.value
  inputText.value = ''
  showSkillMenu.value = false
  // Reset textarea height
  if (inputRef.value) inputRef.value.style.height = 'auto'
  await chatStore.sendMessage(msg, locale.value)
}

async function handlePrimaryAction() {
  if (chatStore.isLoading) {
    await chatStore.stopStreaming()
    return
  }
  await handleSend()
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
          :title="t('chat.attachFile')"
        >
          <Paperclip class="w-5 h-5" />
        </button>

        <!-- Text input -->
        <textarea
          ref="inputRef"
          v-model="inputText"
          :placeholder="t('chat.inputPlaceholder', { at: '@' })"
          rows="1"
          class="flex-1 py-4 bg-transparent border-none focus:ring-0 resize-none outline-none text-[15px] leading-7 min-h-[52px] max-h-36 text-gray-800 placeholder:text-gray-400"
          @input="handleInput"
          @keydown="handleKeydown"
        />

        <!-- Send button -->
        <button
          class="p-2.5 m-1.5 text-white rounded-lg disabled:bg-gray-200 disabled:text-gray-400 transition-colors duration-150 shadow-sm flex-shrink-0 cursor-pointer"
          :class="
            chatStore.isLoading ? 'bg-rose-600 hover:bg-rose-700' : 'bg-blue-600 hover:bg-blue-700'
          "
          :disabled="!chatStore.isLoading && !inputText.trim()"
          :title="chatStore.isLoading ? t('common.stop') : t('chat.send')"
          @click="handlePrimaryAction"
        >
          <Square v-if="chatStore.isLoading" class="w-[18px] h-[18px]" />
          <Send v-else class="w-[18px] h-[18px]" />
        </button>
      </div>
    </div>

    <div class="mt-2.5 mx-auto flex w-full max-w-[920px] flex-wrap items-center gap-2 px-1">
      <div class="mr-2 flex items-center gap-2">
        <span class="text-[10px] font-semibold uppercase tracking-wider text-gray-400"
          >{{ t('chat.providerLabel') }}:</span
        >
        <MenuDropdown
          v-if="providerOptions.length > 0"
          :label="selectedProviderLabel"
          button-class="border border-gray-200 bg-white px-2.5 py-1 text-[11px] font-semibold shadow-sm hover:border-blue-300"
          menu-class="min-w-[12rem]"
          menu-placement="top"
        >
          <template #label>
            <span :class="selectedProvider ? 'text-gray-700' : 'text-red-600'">
              {{ selectedProviderLabel }}
            </span>
          </template>
          <template #default="{ closeDropdown }">
            <button
              v-for="provider in providerOptions"
              :key="provider.id"
              class="w-full px-3 py-2 text-left text-sm transition-colors"
              :class="
                chatStore.selectedProviderId === provider.id
                  ? 'bg-blue-50 font-medium text-blue-600'
                  : 'text-gray-700 hover:bg-gray-50'
              "
              @click="selectProvider(provider.id, closeDropdown)"
            >
              {{ provider.name || provider.id }}
            </button>
          </template>
        </MenuDropdown>
        <span
          v-else
          class="rounded-full border border-red-200 bg-red-50 px-2.5 py-1 text-[11px] font-semibold text-red-600"
        >
          {{ t('chat.providerNone') }}
        </span>
      </div>

      <template v-if="quickSkills.length > 0">
        <span class="text-[10px] font-semibold uppercase tracking-wider text-gray-400"
          >{{ t('chat.skills') }}:</span
        >
        <button
          v-for="skill in quickSkills"
          :key="skill.id"
          class="rounded-full px-2.5 py-1 text-[10px] font-semibold transition-colors duration-150 cursor-pointer"
          :class="
            chatStore.activeSession?.skill === skill.id
              ? 'bg-blue-600 text-white'
              : 'bg-blue-50 text-blue-600 hover:bg-blue-100'
          "
          @click="selectSkill(skill.id, skill.name)"
        >
          @{{ skill.name }}
        </button>
      </template>
    </div>
  </div>
</template>
