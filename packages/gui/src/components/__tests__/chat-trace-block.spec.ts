import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ChatTraceBlock from '@/components/chat/ChatTraceBlock.vue'
import { useSettingsStore } from '@/stores/settings'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string | number>) => {
      if (key === 'chat.providerNone') {
        return 'No Provider'
      }
      if (key === 'chat.trace.providerSwitched') {
        return `${params?.failed} failed, switched from ${params?.from} to ${params?.to}`
      }
      if (key === 'chat.trace.providerSwitchedTo') {
        return `Switched to ${params?.to}`
      }
      if (key === 'chat.trace.completed') {
        return `Trace (${params?.count})`
      }
      return key
    },
  }),
  createI18n: () => ({
    global: {
      locale: {
        value: 'en',
      },
    },
  }),
}))

describe('ChatTraceBlock', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders provider switch steps with provider names and reason details', () => {
    const settingsStore = useSettingsStore()
    settingsStore.llmSettings = {
      temperature: 0,
      max_iterations: 10,
      system_prompt: 'prompt',
      debug_mode: false,
      providers: [
        {
          id: 'primary',
          name: 'Primary GPT',
          priority: 0,
          base_url: 'https://primary.example.com',
          api_key: 'secret',
          model: 'gpt-4.1',
          enabled: true,
        },
        {
          id: 'secondary',
          name: 'Backup GPT',
          priority: 1,
          base_url: 'https://backup.example.com',
          api_key: 'secret',
          model: 'gpt-4.1-mini',
          enabled: true,
        },
      ],
    }

    const wrapper = mount(ChatTraceBlock, {
      props: {
        steps: [
          {
            type: 'provider_switch',
            fromProviderId: 'primary',
            toProviderId: 'secondary',
            content: 'upstream timeout',
          },
        ],
        loopActive: false,
        debugEnabled: false,
      },
    })

    expect(wrapper.text()).toContain('Primary GPT failed, switched from Primary GPT to Backup GPT')
    expect(wrapper.text()).toContain('upstream timeout')
  })

  it('hides tool input and output bodies until debug mode is enabled', () => {
    const wrapper = mount(ChatTraceBlock, {
      props: {
        steps: [
          {
            type: 'tool_start',
            name: 'lookup_course',
            input: { keyword: 'CS304' },
          },
          {
            type: 'tool_end',
            name: 'lookup_course',
            output: 'Found 1 course',
          },
        ],
        loopActive: false,
        debugEnabled: false,
      },
    })

    expect(wrapper.text()).toContain('lookup_course')
    expect(wrapper.text()).not.toContain('CS304')
    expect(wrapper.text()).not.toContain('Found 1 course')
  })

  it('shows expandable tool input and output when debug mode is enabled', () => {
    const wrapper = mount(ChatTraceBlock, {
      props: {
        steps: [
          {
            type: 'tool_start',
            name: 'lookup_course',
            input: { keyword: 'CS304' },
          },
          {
            type: 'tool_end',
            name: 'lookup_course',
            output: 'Found 1 course',
          },
        ],
        loopActive: false,
        debugEnabled: true,
      },
    })

    expect(wrapper.text()).toContain('chat.trace.toolInputDetails')
    expect(wrapper.text()).toContain('CS304')
    expect(wrapper.text()).toContain('chat.trace.toolOutputDetails')
    expect(wrapper.text()).toContain('Found 1 course')
  })
})
