import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import DeadlineAlarmSettings from '../DeadlineAlarmSettings.vue'
import ExtensionServiceSettings from '../ExtensionServiceSettings.vue'
import { useAlarmStore } from '@/stores/alarm'
import { useChatStore } from '@/stores/chat'
import { useSettingsStore } from '@/stores/settings'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
  createI18n: () => ({
    global: {
      locale: {
        value: 'en',
      },
    },
  }),
}))

describe('settings section error UX', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('shows the shared error dialog in deadline alarm settings', async () => {
    const alarmStore = useAlarmStore()
    alarmStore.fetchAlarmSettings = vi.fn().mockResolvedValue(undefined)

    const wrapper = mount(DeadlineAlarmSettings)

    alarmStore.error = 'Alarm save failed'
    await nextTick()

    expect(wrapper.text()).toContain('settings.saveErrorTitle')
    expect(wrapper.text()).toContain('Alarm save failed')
  })

  it('shows provider id as read-only text instead of an editable input', async () => {
    const settingsStore = useSettingsStore()
    settingsStore.llmSettings = {
      temperature: 0,
      max_iterations: 10,
      system_prompt: 'prompt',
      debug_mode: false,
      providers: [
        {
          id: 'provider_1',
          name: 'Primary',
          priority: 0,
          base_url: '',
          api_key: 'secret',
          model: 'gpt-4.1',
          enabled: true,
        },
      ],
    }

    const wrapper = mount(ExtensionServiceSettings)
    await nextTick()

    expect(wrapper.text()).toContain('settings.extension.providerIdLabel: provider_1')
    expect(
      wrapper.findAll('input').some((candidate) => {
        return (candidate.element as HTMLInputElement).value === 'provider_1'
      }),
    ).toBe(false)
  })

  it('normalizes duplicate provider ids while keeping row removal stable', async () => {
    const settingsStore = useSettingsStore()
    settingsStore.llmSettings = {
      temperature: 0,
      max_iterations: 10,
      system_prompt: 'prompt',
      debug_mode: false,
      providers: [
        {
          id: 'duplicate_id',
          name: 'Primary',
          priority: 0,
          base_url: '',
          api_key: 'secret',
          model: 'gpt-4.1',
          enabled: true,
        },
        {
          id: 'duplicate_id',
          name: 'Backup',
          priority: 1,
          base_url: '',
          api_key: 'secret',
          model: 'gpt-4.1-mini',
          enabled: true,
        },
      ],
    }

    const wrapper = mount(ExtensionServiceSettings)
    await nextTick()

    expect(wrapper.text()).toContain('Primary')
    expect(wrapper.text()).toContain('Backup')
    expect(wrapper.text()).toContain('settings.extension.providerIdLabel: duplicate_id')
    expect(wrapper.text()).toContain('settings.extension.providerIdLabel: provider_2')

    const removeButtons = wrapper
      .findAll('button')
      .filter((candidate) => candidate.text() === 'common.remove')

    expect(removeButtons).toHaveLength(2)

    const backupRemoveButton = removeButtons[1]
    expect(backupRemoveButton).toBeDefined()
    if (!backupRemoveButton) {
      throw new Error('Expected a remove button for the duplicate provider row')
    }

    await backupRemoveButton.trigger('click')
    await nextTick()

    expect(wrapper.text()).toContain('Primary')
    expect(wrapper.text()).not.toContain('Backup')
  })

  it('keeps provider cards collapsed until edit is requested', async () => {
    const settingsStore = useSettingsStore()
    settingsStore.llmSettings = {
      temperature: 0,
      max_iterations: 10,
      system_prompt: 'prompt',
      debug_mode: false,
      providers: [
        {
          id: 'provider_1',
          name: 'Primary',
          priority: 0,
          base_url: 'https://api.example.com',
          api_key: 'secret',
          model: 'gpt-4.1',
          enabled: true,
        },
      ],
    }

    const wrapper = mount(ExtensionServiceSettings)
    await nextTick()

    expect(wrapper.text()).not.toContain('settings.extension.providerPriorityAutoHint')
    expect(
      wrapper.findAll('input').some((candidate) => {
        return (candidate.element as HTMLInputElement).value === 'https://api.example.com'
      }),
    ).toBe(false)

    const editButton = wrapper
      .findAll('button')
      .find((candidate) => candidate.text().includes('settings.extension.editProvider'))
    expect(editButton).toBeDefined()
    if (!editButton) {
      throw new Error('Expected provider edit button to be rendered')
    }

    await editButton.trigger('click')
    await nextTick()

    expect(wrapper.text()).toContain('settings.extension.providerPriorityAutoHint')
    expect(
      wrapper.findAll('input').some((candidate) => {
        return (candidate.element as HTMLInputElement).value === 'https://api.example.com'
      }),
    ).toBe(true)
  })

  it('updates fallback mode from extension settings', async () => {
    const chatStore = useChatStore()
    chatStore.fallbackMode = 'manual'
    const updatePreferences = vi
      .spyOn(chatStore, 'updateActiveSessionPreferences')
      .mockImplementation(async (request) => {
        if (request.fallback_mode) {
          chatStore.fallbackMode = request.fallback_mode
        }
      })

    const wrapper = mount(ExtensionServiceSettings)

    await wrapper.get('[data-testid="fallback-mode-auto"]').trigger('click')
    await nextTick()

    expect(updatePreferences).toHaveBeenCalledWith({ fallback_mode: 'auto' })
    expect(chatStore.fallbackMode).toBe('auto')
  })
})
