import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import ChatMessageList from '@/components/chat/ChatMessageList.vue'
import { useChatStore } from '@/stores/chat'
import { useSettingsStore } from '@/stores/settings'
import { MESSAGE_ROLES } from '@/stores/chatConstants'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
    locale: { value: 'en' },
  }),
  createI18n: () => ({
    global: {
      locale: {
        value: 'en',
      },
    },
  }),
}))

describe('ChatMessageList', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('prepends the active skill system prompt only when debug mode is enabled', () => {
    const chatStore = useChatStore()
    const settingsStore = useSettingsStore()

    settingsStore.llmSettings = {
      temperature: 0,
      max_iterations: 10,
      system_prompt: 'Default system prompt',
      debug_mode: true,
      providers: [],
    }

    chatStore.skills = [
      {
        id: 'deadline_manager',
        name: 'Deadline Manager',
        description: 'Handles deadlines',
        system_prompt: 'Skill-specific prompt',
        icon: 'clock',
        color: 'blue',
      },
    ]
    chatStore.sessions = [
      {
        id: 'session-1',
        title: 'New Chat',
        skill: 'deadline_manager',
        messages: [
          {
            id: 'assistant-1',
            role: MESSAGE_ROLES.ASSISTANT,
            content: 'Assistant reply',
            timestamp: new Date('2026-04-25T00:00:00Z'),
          },
        ],
        visiblePath: [],
        versionGroups: [],
        nodeMap: {},
        createdAt: new Date('2026-04-25T00:00:00Z'),
        updatedAt: new Date('2026-04-25T00:00:00Z'),
      },
    ]
    chatStore.activeSessionId = 'session-1'

    const wrapper = mount(ChatMessageList, {
      global: {
        stubs: {
          ChatMessageBubble: {
            props: ['msg'],
            template: '<div class="bubble">{{ msg.role }}::{{ msg.content }}</div>',
          },
        },
      },
    })

    const bubbles = wrapper.findAll('.bubble')
    expect(bubbles).toHaveLength(2)
    expect(bubbles[0]?.text()).toContain('system::Deadline Manager')
    expect(bubbles[0]?.text()).toContain('Skill-specific prompt')
    expect(bubbles[1]?.text()).toContain('assistant::Assistant reply')
  })

  it('keeps system prompts hidden when debug mode is disabled', () => {
    const chatStore = useChatStore()
    const settingsStore = useSettingsStore()

    settingsStore.llmSettings = {
      temperature: 0,
      max_iterations: 10,
      system_prompt: 'Default system prompt',
      debug_mode: false,
      providers: [],
    }

    chatStore.sessions = [
      {
        id: 'session-1',
        title: 'New Chat',
        messages: [
          {
            id: 'assistant-1',
            role: MESSAGE_ROLES.ASSISTANT,
            content: 'Assistant reply',
            timestamp: new Date('2026-04-25T00:00:00Z'),
          },
        ],
        visiblePath: [],
        versionGroups: [],
        nodeMap: {},
        createdAt: new Date('2026-04-25T00:00:00Z'),
        updatedAt: new Date('2026-04-25T00:00:00Z'),
      },
    ]
    chatStore.activeSessionId = 'session-1'

    const wrapper = mount(ChatMessageList, {
      global: {
        stubs: {
          ChatMessageBubble: {
            props: ['msg'],
            template: '<div class="bubble">{{ msg.role }}::{{ msg.content }}</div>',
          },
        },
      },
    })

    const bubbles = wrapper.findAll('.bubble')
    expect(bubbles).toHaveLength(1)
    expect(bubbles[0]?.text()).toContain('assistant::Assistant reply')
  })
})
