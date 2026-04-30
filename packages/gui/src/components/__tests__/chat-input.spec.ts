/**
 * Unit tests for ChatInputBox logic utilities.
 * Tests the mention detection and IME-safe keyboard handling logic
 * and the recent-skill UI behavior around the full component.
 */
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, afterEach, vi } from 'vitest'
import { describe, it, expect } from 'vitest'
import ChatInputBox from '@/components/chat/ChatInputBox.vue'
import SessionSidebar from '@/components/SessionSidebar.vue'
import { useChatStore } from '@/stores/chat'
import { useSettingsStore } from '@/stores/settings'

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

// ---- Extracted pure logic (mirrors ChatInputBox.vue) ----

function isValidMentionAt(text: string, atIndex: number): boolean {
  if (atIndex === 0) return true
  const preceding = text[atIndex - 1]
  return preceding === ' ' || preceding === '\n'
}

function findMentionAtIndex(text: string): number {
  let idx = text.lastIndexOf('@')
  while (idx >= 0) {
    if (isValidMentionAt(text, idx)) return idx
    idx = text.lastIndexOf('@', idx - 1)
  }
  return -1
}

function shouldSendOnEnter(e: { key: string; shiftKey: boolean; isComposing: boolean }): boolean {
  return e.key === 'Enter' && !e.shiftKey && !e.isComposing
}

function createSkill(id: string, name: string, icon: string) {
  return {
    id,
    name,
    description: `${name} description`,
    system_prompt: '',
    icon,
    color: '#000',
  }
}

function createProvider() {
  return {
    id: 'provider-a',
    name: 'Provider A',
    enabled: true,
    priority: 1,
    base_url: 'https://example.test',
    api_key: 'test-key',
    model: 'test-model',
  }
}

// ---- Tests ----

beforeEach(() => {
  setActivePinia(createPinia())
  document.cookie = 'recent_skills=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
})

afterEach(() => {
  document.cookie = 'recent_skills=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
})

describe('findMentionAtIndex', () => {
  it('detects @ at start of text', () => {
    expect(findMentionAtIndex('@skill')).toBe(0)
  })

  it('detects @ after a space', () => {
    expect(findMentionAtIndex('hello @skill')).toBe(6)
  })

  it('detects @ after a newline', () => {
    expect(findMentionAtIndex('hello\n@skill')).toBe(6)
  })

  it('does NOT trigger on email address', () => {
    expect(findMentionAtIndex('user@gmail.com')).toBe(-1)
  })

  it('does NOT trigger when @ is mid-word', () => {
    expect(findMentionAtIndex('abc@def')).toBe(-1)
  })

  it('returns -1 when no @ present', () => {
    expect(findMentionAtIndex('hello world')).toBe(-1)
  })

  it('returns valid @ when mixed with invalid ones', () => {
    // "email@test.com @skill" — only the second @ after space is valid
    const text = 'email@test.com @skill'
    const idx = findMentionAtIndex(text)
    expect(idx).toBe(15)
  })

  it('returns -1 for empty string', () => {
    expect(findMentionAtIndex('')).toBe(-1)
  })

  it('handles single @ at end of text', () => {
    expect(findMentionAtIndex('@')).toBe(0)
  })

  it('handles @ preceded by newline at beginning', () => {
    expect(findMentionAtIndex('\n@skill')).toBe(1)
  })
})

describe('shouldSendOnEnter (IME guard)', () => {
  it('returns true for plain Enter', () => {
    expect(shouldSendOnEnter({ key: 'Enter', shiftKey: false, isComposing: false })).toBe(true)
  })

  it('returns false when Shift+Enter (newline)', () => {
    expect(shouldSendOnEnter({ key: 'Enter', shiftKey: true, isComposing: false })).toBe(false)
  })

  it('returns false when isComposing (IME active — e.g. Chinese input)', () => {
    expect(shouldSendOnEnter({ key: 'Enter', shiftKey: false, isComposing: true })).toBe(false)
  })

  it('returns false for non-Enter key', () => {
    expect(shouldSendOnEnter({ key: 'a', shiftKey: false, isComposing: false })).toBe(false)
  })

  it('returns false when both shiftKey and isComposing', () => {
    expect(shouldSendOnEnter({ key: 'Enter', shiftKey: true, isComposing: true })).toBe(false)
  })
})

describe('ChatInputBox skill UI', () => {
  it('prioritizes recent skills from cookies for quick access', async () => {
    document.cookie = 'recent_skills=policy_search,email_assistant; path=/'

    const chatStore = useChatStore()
    const settingsStore = useSettingsStore()

    chatStore.skills = [
      createSkill('general', 'General Assistant', 'MessageSquare'),
      createSkill('deadline_manager', 'Deadline Manager', 'Calendar'),
      createSkill('policy_search', 'Policy Search', 'Search'),
      createSkill('email_assistant', 'Email Assistant', 'Mail'),
    ]
    settingsStore.llmSettings = {
      temperature: 0,
      max_iterations: 10,
      system_prompt: '',
      debug_mode: false,
      providers: [createProvider()],
    }

    const wrapper = mount(ChatInputBox, {
      global: {
        stubs: {
          MenuDropdown: {
            props: ['label'],
            template: '<div><slot name="label" /><slot :closeDropdown="() => {}" /></div>',
          },
        },
      },
    })

    const quickSkills = wrapper.findAll('[data-testid="quick-skill-pill"]')
    expect(quickSkills).toHaveLength(3)
    expect(quickSkills[0]?.text()).toContain('@Policy Search')
    expect(quickSkills[1]?.text()).toContain('@Email Assistant')
    expect(quickSkills[2]?.text()).toContain('@General Assistant')
    expect(wrapper.text()).not.toContain('chat.attachFile')
    expect(wrapper.find('textarea').classes()).toContain('pl-3')
  })

  it('parses recent skills cookies even when semicolons have no spaces', async () => {
    const originalCookie = Object.getOwnPropertyDescriptor(document, 'cookie')
    Object.defineProperty(document, 'cookie', {
      configurable: true,
      get: () => 'session_id=abc123;recent_skills=policy_search,email_assistant',
      set: () => undefined,
    })

    const chatStore = useChatStore()
    const settingsStore = useSettingsStore()

    chatStore.skills = [
      createSkill('general', 'General Assistant', 'MessageSquare'),
      createSkill('policy_search', 'Policy Search', 'Search'),
      createSkill('email_assistant', 'Email Assistant', 'Mail'),
    ]
    settingsStore.llmSettings = {
      temperature: 0,
      max_iterations: 10,
      system_prompt: '',
      debug_mode: false,
      providers: [createProvider()],
    }

    const wrapper = mount(ChatInputBox, {
      global: {
        stubs: {
          MenuDropdown: {
            props: ['label'],
            template: '<div><slot name="label" /><slot :closeDropdown="() => {}" /></div>',
          },
        },
      },
    })

    const quickSkills = wrapper.findAll('[data-testid="quick-skill-pill"]')
    expect(quickSkills).toHaveLength(3)
    expect(quickSkills[0]?.text()).toContain('@Policy Search')
    expect(quickSkills[1]?.text()).toContain('@Email Assistant')

    if (originalCookie) {
      Object.defineProperty(document, 'cookie', originalCookie)
    }
  })

  it('renders a lucide skill icon instead of raw icon text in the mention menu', async () => {
    const chatStore = useChatStore()
    const settingsStore = useSettingsStore()

    chatStore.skills = [createSkill('campus_news', 'Campus News', 'Newspaper')]
    settingsStore.llmSettings = {
      temperature: 0,
      max_iterations: 10,
      system_prompt: '',
      debug_mode: false,
      providers: [createProvider()],
    }

    const wrapper = mount(ChatInputBox, {
      global: {
        stubs: {
          MenuDropdown: {
            props: ['label'],
            template: '<div><slot name="label" /><slot :closeDropdown="() => {}" /></div>',
          },
        },
      },
    })

    const textarea = wrapper.find('textarea')
    await textarea.setValue('@camp')

    const icon = wrapper.find('[data-testid="skill-menu-icon"] svg')
    expect(wrapper.find('[data-testid="skill-menu"]').exists()).toBe(true)
    expect(icon.exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Newspaper')
  })
})

describe('SessionSidebar footer', () => {
  it('hides the unsupported user profile block while keeping settings access', () => {
    const wrapper = mount(SessionSidebar, {
      props: { collapsed: false },
    })

    expect(wrapper.text()).not.toContain('sidebar.userProfile')
    expect(wrapper.find('[data-testid="settings-btn"]').exists()).toBe(true)
  })

  it('renders the sidebar toggle button in the session management area', () => {
    const wrapper = mount(SessionSidebar, {
      props: { collapsed: false },
    })

    const toggleButton = wrapper.find('[data-testid="sidebar-toggle-btn"]')
    expect(toggleButton.exists()).toBe(true)
    expect(toggleButton.attributes('title')).toBe('chat.toggleSidebar')
  })
})
