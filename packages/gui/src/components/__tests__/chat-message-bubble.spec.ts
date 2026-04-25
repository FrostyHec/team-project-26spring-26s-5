import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import ChatMessageBubble from '@/components/chat/ChatMessageBubble.vue'
import { useChatStore } from '@/stores/chat'
import { useSettingsStore } from '@/stores/settings'
import { MESSAGE_ROLES } from '@/stores/chatConstants'
import type { ChatMessage } from '@/stores/chatTypes'

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

function buildMessage(selectedVersionId: string): ChatMessage {
  return {
    id: 'msg-1',
    role: MESSAGE_ROLES.ASSISTANT,
    content: 'Versioned answer',
    nodeId: selectedVersionId,
    versionGroupId: 'group-1',
    selectedVersionId,
    versionChoices: [
      { nodeId: 'node-1', role: 'ai', versionIndex: 0, sourceKind: 'initial' },
      { nodeId: 'node-2', role: 'ai', versionIndex: 1, sourceKind: 'retry' },
      { nodeId: 'node-3', role: 'ai', versionIndex: 2, sourceKind: 'retry' },
    ],
    canEdit: true,
    canRetry: true,
    timestamp: new Date('2026-04-25T00:00:00Z'),
  }
}

function buildUserMessage(): ChatMessage {
  return {
    id: 'user-1',
    role: MESSAGE_ROLES.USER,
    content: 'Original user message',
    nodeId: 'user-node-1',
    canEdit: true,
    timestamp: new Date('2026-04-25T00:00:00Z'),
  }
}

describe('ChatMessageBubble', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const settingsStore = useSettingsStore()
    settingsStore.llmSettings.debug_mode = false
  })

  it('renders pager-style version controls and switches to adjacent versions', async () => {
    const store = useChatStore()
    store.selectVersion = vi.fn().mockResolvedValue(undefined)

    const wrapper = mount(ChatMessageBubble, {
      props: {
        msg: buildMessage('node-2'),
        isLast: false,
      },
      global: {
        stubs: {
          ChatToolBadges: true,
          ChatTraceBlock: true,
        },
      },
    })

    expect(wrapper.get('[data-testid="version-indicator"]').text()).toBe('2 / 3')

    await wrapper.get('[data-testid="version-prev"]').trigger('click')
    expect(store.selectVersion).toHaveBeenCalledWith('group-1', 'node-1')

    await wrapper.get('[data-testid="version-next"]').trigger('click')
    expect(store.selectVersion).toHaveBeenCalledWith('group-1', 'node-3')
  })

  it('disables pager buttons at version boundaries', () => {
    const store = useChatStore()
    store.selectVersion = vi.fn().mockResolvedValue(undefined)

    const wrapper = mount(ChatMessageBubble, {
      props: {
        msg: buildMessage('node-1'),
        isLast: false,
      },
      global: {
        stubs: {
          ChatToolBadges: true,
          ChatTraceBlock: true,
        },
      },
    })

    expect(
      (wrapper.get('[data-testid="version-prev"]').element as HTMLButtonElement).disabled,
    ).toBe(true)
    expect(
      (wrapper.get('[data-testid="version-next"]').element as HTMLButtonElement).disabled,
    ).toBe(false)
  })

  it('switches user messages to a neutral editing surface', async () => {
    const store = useChatStore()
    store.editMessage = vi.fn().mockResolvedValue(undefined)

    const wrapper = mount(ChatMessageBubble, {
      props: {
        msg: buildUserMessage(),
        isLast: false,
      },
      global: {
        stubs: {
          ChatToolBadges: true,
          ChatTraceBlock: true,
        },
      },
    })

    await wrapper.get('button').trigger('click')

    expect(wrapper.get('[data-testid="message-bubble"]').classes()).toContain('bg-slate-50')
    expect(wrapper.get('[data-testid="message-bubble"]').classes()).toContain('border')
    expect(wrapper.find('textarea').exists()).toBe(true)
    expect(wrapper.text()).toContain('chat.saveEdit')
  })

  it('renders synthetic system messages with the system bubble styling', () => {
    const wrapper = mount(ChatMessageBubble, {
      props: {
        msg: {
          id: 'system-1',
          role: MESSAGE_ROLES.SYSTEM,
          content: 'System prompt content',
          timestamp: new Date('2026-04-25T00:00:00Z'),
        },
        isLast: false,
      },
      global: {
        stubs: {
          ChatToolBadges: true,
          ChatTraceBlock: true,
        },
      },
    })

    expect(wrapper.get('[data-testid="message-bubble"]').classes()).toContain('bg-amber-50')
    expect(wrapper.text()).toContain('System prompt content')
  })
})
